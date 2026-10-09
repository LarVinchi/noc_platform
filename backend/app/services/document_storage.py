"""Private filesystem adapter. Filenames never determine storage paths."""
import hashlib
import os
import re
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from fastapi import HTTPException
from app.core.config import settings

MAX_BYTES = 20 * 1024 * 1024
MEDIA = {'.pdf':'application/pdf','.docx':'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
         '.xlsx':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','.csv':'text/csv','.txt':'text/plain',
         '.jpg':'image/jpeg','.jpeg':'image/jpeg','.png':'image/png'}


def root():
    location = Path(settings.DOCUMENT_STORAGE_ROOT).resolve()
    static = Path('static').resolve()
    if location == static or static in location.parents:
        raise HTTPException(503,'Private document storage must be outside the static directory')
    location.mkdir(parents=True,exist_ok=True,mode=0o700)
    return location


def stored_path(key):
    # Only generated keys are accepted, even if database metadata is compromised.
    if not re.fullmatch(r'originals/[0-9a-f-]{36}/[0-9a-f-]{36}/source\.(pdf|docx|xlsx|csv|txt|jpg|jpeg|png)',key):
        raise HTTPException(503,'Invalid private storage reference')
    location = root()
    target = (location/key).resolve()
    if location not in target.parents:
        raise HTTPException(503,'Invalid private storage reference')
    return target


def validate(path, extension):
    try:
        head = path.read_bytes()[:16]
        if extension == '.pdf':
            if not head.startswith(b'%PDF-'):
                raise ValueError('Not a PDF')
            from pypdf import PdfReader
            reader = PdfReader(path,strict=True)
            if reader.is_encrypted or not 0 < len(reader.pages) <= 500:
                raise ValueError('Encrypted or oversized PDF')
            catalog = reader.trailer['/Root']
            names = catalog.get('/Names')
            names = names.get_object() if names else {}
            if '/OpenAction' in catalog or '/AA' in catalog or '/JavaScript' in names or '/EmbeddedFiles' in names:
                raise ValueError('PDF actions or attachments are not supported')
        elif extension in {'.docx','.xlsx'}:
            required = 'word/document.xml' if extension == '.docx' else 'xl/workbook.xml'
            with zipfile.ZipFile(path) as archive:
                entries = archive.infolist()
                if len(entries)>2000 or sum(info.file_size for info in entries)>100*1024*1024:
                    raise ValueError('Office archive exceeds limits')
                for info in entries:
                    if info.flag_bits & 1 or info.file_size/max(info.compress_size,1)>200 or 'vbaproject' in info.filename.lower():
                        raise ValueError('Encrypted, macro-enabled or excessive compression')
                    if info.filename.startswith('/') or '..' in Path(info.filename.replace('\\','/')).parts:
                        raise ValueError('Unsafe archive entry')
                for name in ('[Content_Types].xml',required):
                    content = archive.read(name)
                    if b'<!DOCTYPE' in content.upper() or b'<!ENTITY' in content.upper():
                        raise ValueError('Unsafe XML')
                    parsed = ET.fromstring(content)
                    if name=='[Content_Types].xml' and b'macroenabled' in content.lower():
                        raise ValueError('Macro content types are not supported')
                    if name==required and parsed.tag != ('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}document' if extension=='.docx' else '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}workbook'):
                        raise ValueError('Unexpected Office document root')
        elif extension in {'.csv','.txt'}:
            content = path.read_bytes().decode('utf-8-sig')
            if '\x00' in content:
                raise ValueError('Binary text')
        elif extension in {'.jpg','.jpeg','.png'}:
            from PIL import Image
            with Image.open(path) as picture:
                if picture.format != ('PNG' if extension=='.png' else 'JPEG') or picture.width*picture.height>40_000_000:
                    raise ValueError('Unexpected image format or dimensions')
                picture.verify()
    except Exception as exc:
        raise HTTPException(422,'File content is invalid, encrypted or outside supported format limits') from exc


def stage(upload):
    filename = (upload.filename or '').replace('\\','/').split('/')[-1]
    filename = ''.join(char for char in filename if ord(char)>=32 and ord(char)!=127)
    extension = Path(filename).suffix.lower()
    if extension not in MEDIA or not filename or len(filename)>240:
        raise HTTPException(422,'Supported files: PDF, DOCX, XLSX, UTF-8 CSV/TXT, JPEG and PNG; maximum filename 240 characters')
    incoming = root()/'.incoming'
    incoming.mkdir(exist_ok=True,mode=0o700)
    descriptor, name = tempfile.mkstemp(dir=incoming)
    path = Path(name)
    digest = hashlib.sha256(); size = 0
    try:
        with os.fdopen(descriptor,'wb') as output:
            while chunk := upload.file.read(65536):
                size += len(chunk)
                if size>MAX_BYTES:
                    raise HTTPException(413,'Document limit is 20 MB')
                output.write(chunk); digest.update(chunk)
        if size==0:
            raise HTTPException(422,'Empty documents are not supported')
        validate(path,extension)
        return path,filename,extension,size,digest.hexdigest()
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def publish(staged, document_id, version_id, extension):
    key = f'originals/{document_id}/{version_id}/source{extension}'
    target = stored_path(key)
    target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    # UUID-addressed immutable object; never replace an existing revision.
    os.link(staged,target)
    return key


def verified_path(version):
    path = stored_path(version.storage_key)
    try:
        if path.stat().st_size != version.byte_size:
            raise ValueError('Size mismatch')
        with path.open('rb') as source:
            digest = hashlib.file_digest(source,'sha256').hexdigest()
        if digest != version.sha256:
            raise ValueError('Checksum mismatch')
    except (OSError,ValueError) as exc:
        raise HTTPException(503,'Document storage is unavailable or integrity verification failed') from exc
    return path
