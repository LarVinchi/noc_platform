"""One bounded validation contract for uploads and downloaded workbook snapshots."""
from io import BytesIO
from zipfile import ZipFile
from app.services.energy_reporting import read_records

MAX_WORKBOOK_BYTES = 10 * 1024 * 1024


class InvalidEnergyWorkbook(ValueError):
    pass


def parse_workbook(content):
    if len(content) > MAX_WORKBOOK_BYTES:
        raise InvalidEnergyWorkbook('Workbook exceeds the 10 MB import limit')
    try:
        with ZipFile(BytesIO(content)) as archive:
            entries = archive.infolist()
            if len(entries) > 2000 or sum(item.file_size for item in entries) > 40 * 1024 * 1024:
                raise ValueError('Expanded workbook too large')
        records = read_records(BytesIO(content))
        if not records or len(records) > 50000:
            raise ValueError('Expected recognized RawData records')
        return records
    except Exception as error:
        raise InvalidEnergyWorkbook('Invalid tracker: check RawData headers, timestamps and workbook size') from error
