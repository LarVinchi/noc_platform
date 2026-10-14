import io
import zipfile
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_ftth_intake_api import api, REQUEST, pytestmark  # noqa: F401


@pytest.fixture(autouse=True)
def private_storage(tmp_path,monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings,'DOCUMENT_STORAGE_ROOT',str(tmp_path/'documents'))


def upload(client,**extra):
    response = client.post('/api/documents',data={'title':'Source regression','document_type':'knowledge','note':'Original reviewed source location',**extra},files={'file':('source.txt',b'Operational source evidence','text/plain')})
    assert response.status_code==200,response.text
    return response.json()


def test_immutable_revisions_duplicate_content_and_verified_download(api):
    client,db = api
    record = upload(client)
    identifier = record['document_id']; version = record['latest_version']
    assert 'storage_key' not in version and record['rag_state']=='Not indexed'
    path = f"/api/documents/{identifier}/versions/{version['version_id']}/download"
    result = client.get(path)
    assert result.content==b'Operational source evidence'
    assert 'attachment' in result.headers['content-disposition'] and result.headers['cache-control']=='private, no-store'
    repeat = client.post(f'/api/documents/{identifier}/versions',data={'note':'Retry same source'},files={'file':('retry.txt',result.content)})
    assert repeat.json()['outcome']=='already_current'
    changed = client.post(f'/api/documents/{identifier}/versions',data={'note':'Corrected source'},files={'file':('source.txt',b'Corrected operational evidence')})
    assert changed.status_code==200 and changed.json()['version']['revision']==2
    assert len(client.get(f'/api/documents/{identifier}').json()['versions'])==2
    assert client.get(path).content==result.content
    with pytest.raises(DBAPIError),db.begin_nested():
        db.execute(text('UPDATE document_versions SET sha256=\'tampered\' WHERE version_id=:id'),{'id':version['version_id']})
    events = client.get('/api/audit/',params={'entity_id':version['version_id']}).json()['items']
    assert events and events[0]['actor_id']=='local-preview'


def test_private_catalogue_download_permissions_and_sharing_revocation(api,monkeypatch):
    client,_ = api
    record = upload(client)
    identifier = record['document_id']; version = record['latest_version']['version_id']
    from app.core import security
    monkeypatch.setattr(security,'auth_configuration',lambda:{'configured':True,'mode':'entra'})
    actor = {'id':'different-viewer','verified':True,'roles':['NOC.Viewer']}
    monkeypatch.setattr(security,'validate_token',lambda token:actor.copy())
    headers={'authorization':'Bearer test'}
    assert identifier not in [value['document_id'] for value in client.get('/api/documents',headers=headers).json()['items']]
    assert client.get(f'/api/documents/{identifier}',headers=headers).status_code==404
    assert client.get(f'/api/documents/{identifier}/versions/{version}/download',headers=headers).status_code==404
    actor['roles']=['NOC.Admin']
    assert client.patch(f'/api/documents/{identifier}/sharing',json={'visibility':'noc'},headers=headers).status_code==200
    actor['roles']=['NOC.Viewer']
    assert client.get(f'/api/documents/{identifier}',headers=headers).status_code==200
    assert client.post('/api/documents',headers=headers).status_code==403
    actor['roles']=['NOC.Operator']
    assert client.post(f'/api/documents/{identifier}/versions',headers=headers,data={'note':'Unauthorized revision'},files={'file':('source.txt',b'Changed text')}).status_code==403
    assert client.patch(f'/api/documents/{identifier}/sharing',headers=headers,json={'visibility':'private'}).status_code==403
    actor['roles']=['NOC.Admin']
    client.patch(f'/api/documents/{identifier}/sharing',headers=headers,json={'visibility':'private'})
    actor['roles']=['NOC.Viewer']
    assert client.get(f'/api/documents/{identifier}/versions/{version}/download',headers=headers).status_code==404


@pytest.mark.parametrize('name,content,status',[
    ('fake.pdf',b'Not a PDF',422),('script.html',b'<script>bad</script>',422),('empty.txt',b'',422),
    ('binary.csv',b'hello\x00binary',422),('too-large.txt',b'x'*(20*1024*1024+1),413),
])
def test_invalid_uploads_leave_no_catalogue_or_staged_file(api,name,content,status):
    client,db = api
    from app.models.documents import Document
    from app.core.config import settings
    from pathlib import Path
    before = db.query(Document).count()
    result = client.post('/api/documents',data={'title':'Invalid source','document_type':'knowledge','note':'Invalid upload test'},files={'file':(name,content)})
    assert result.status_code==status,result.text
    db.rollback()
    assert db.query(Document).count()==before
    assert not list(Path(settings.DOCUMENT_STORAGE_ROOT).rglob('source.*'))
    assert not list((Path(settings.DOCUMENT_STORAGE_ROOT)/'.incoming').glob('*'))


def test_upload_links_sanitized_name_and_storage_integrity(api):
    client,_ = api
    from app.core.config import settings
    from pathlib import Path
    order_data = client.post('/api/provisioning/intake/preview',json={'raw_text':REQUEST}).json()['order']
    order = client.post('/api/provisioning/',json=order_data).json()
    record = upload(client,order_id=order['order_id'])
    assert record['order_id']==order['order_id']
    invalid = client.post('/api/documents',data={'title':'Bad link','document_type':'knowledge','note':'Missing linked order','order_id':'00000000-0000-0000-0000-000000000000'},files={'file':('source.txt',b'Text')})
    assert invalid.status_code==422
    changed = client.post(f"/api/documents/{record['document_id']}/versions",data={'note':'Path filename test'},files={'file':('../../escape.txt',b'Traversal is a filename only')})
    assert changed.json()['version']['original_filename']=='escape.txt'
    version = record['latest_version']
    source = next(Path(settings.DOCUMENT_STORAGE_ROOT).rglob(f"{version['version_id']}/source.txt"))
    source.write_bytes(b'Tampered storage')
    assert client.get(f"/api/documents/{record['document_id']}/versions/{version['version_id']}/download").status_code==503


def test_valid_pdf_office_and_image_formats(api):
    client,_ = api
    from pypdf import PdfWriter
    from PIL import Image
    pdf = io.BytesIO(); writer=PdfWriter(); writer.add_blank_page(width=100,height=100); writer.write(pdf)
    image = io.BytesIO(); Image.new('RGB',(10,10)).save(image,format='PNG')
    files = [('source.pdf',pdf.getvalue()),('photo.png',image.getvalue())]
    for extension,part,xml in [('docx','word/document.xml',b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body/></w:document>'),('xlsx','xl/workbook.xml',b'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"/>')]:
        output=io.BytesIO()
        with zipfile.ZipFile(output,'w') as archive:
            archive.writestr('[Content_Types].xml','<Types/>'); archive.writestr(part,xml)
        files.append((f'source.{extension}',output.getvalue()))
    for name,content in files:
        result=client.post('/api/documents',data={'title':name,'document_type':'knowledge','note':'Supported format test'},files={'file':(name,content)})
        assert result.status_code==200,result.text
