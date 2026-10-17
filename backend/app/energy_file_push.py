"""Fixed SSH receiver entry point: stdin is a delivery, stdout is an acknowledgement."""
import json
import sys
from uuid import uuid4

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.security import actor_context
from app.models.provisioning import ServiceOrder  # noqa: F401 -- register FK target
from app.services.energy_file_push import (
    WORKER, configuration_errors, publish, read_delivery, read_header, request_token, poll_delivery,
)
from app.services.energy_import import InvalidEnergyWorkbook
from app.services.energy_onedrive import SyncFailure


def main():
    if not settings.ENERGY_FILE_PUSH_ENABLED or configuration_errors():
        print('File delivery is disabled or conflicts with Graph synchronization', file=sys.stderr)
        return 1
    token = actor_context.set({'id': WORKER, 'verified': False, 'roles': [], 'request_id': str(uuid4())})
    try:
        header = read_header(sys.stdin.buffer)
        operation = header.get('operation', 'upload')
        if operation == 'poll':
            if sys.stdin.buffer.read(1):
                raise ValueError('Unexpected polling payload')
            with SessionLocal() as db:
                result = poll_delivery(db)
        elif operation == 'upload':
            acknowledged = request_token(header)
            content, modified = read_delivery(sys.stdin.buffer, header)
            with SessionLocal() as db:
                result = publish(db, content, modified, acknowledged_request=acknowledged)
        else:
            raise ValueError('Unsupported operation')
        print(json.dumps(result))
        return 0
    except (InvalidEnergyWorkbook, ValueError, SyncFailure):
        print('Workbook delivery rejected; last valid dataset retained. Check format, checksum and source timestamp.', file=sys.stderr)
        return 1
    except Exception as error:
        print(f'Workbook delivery failed ({type(error).__name__}); last valid dataset retained', file=sys.stderr)
        return 1
    finally:
        actor_context.reset(token)


if __name__ == '__main__':
    sys.exit(main())
