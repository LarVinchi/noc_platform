import datetime as dt
import hashlib
from io import BytesIO
import json

import pytest

from app.services.energy_file_push import read_delivery


def envelope(content=b'workbook', **overrides):
    header = {'size': len(content), 'sha256': hashlib.sha256(content).hexdigest(),
              'modified_at': '2026-07-04T12:00:00+00:00', **overrides}
    return json.dumps(header).encode() + b'\n' + content


def test_exact_delivery_and_timezone():
    content, modified = read_delivery(BytesIO(envelope()))
    assert content == b'workbook'
    assert modified == dt.datetime(2026, 7, 4, 12, tzinfo=dt.timezone.utc)


@pytest.mark.parametrize('payload', [
    b'{}', b'x' * 2049 + b'\n', b'[]\n',
    envelope(size=True), envelope(size=10 * 1024 * 1024 + 1),
    envelope(sha256='0' * 64), envelope()[:-1], envelope() + b'x',
    envelope(modified_at='2026-07-04T12:00:00'),
    envelope(modified_at='2999-01-01T00:00:00Z'), envelope(modified_at=None),
])
def test_bad_delivery_is_rejected(payload):
    with pytest.raises(ValueError):
        read_delivery(BytesIO(payload))
