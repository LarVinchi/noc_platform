"""Poll saved workbook changes independently of incident escalation."""
import logging
import signal
from threading import Event
from uuid import uuid4
from sqlalchemy.dialects.postgresql import insert
from app.core.db import SessionLocal
from app.core.security import actor_context
from app.models.response import WorkerHeartbeat
from app.models.provisioning import ServiceOrder  # noqa: F401; register standalone worker foreign keys
from app.services.energy_sync import WORKER, run_sync, utcnow

stop = Event()


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    signal.signal(signal.SIGTERM, lambda *args: stop.set())
    signal.signal(signal.SIGINT, lambda *args: stop.set())
    previous = None
    while not stop.is_set():
        actor_context.set({'id': WORKER, 'verified': False, 'request_id': str(uuid4())})
        try:
            with SessionLocal() as db:
                outcome = run_sync(db)
                heartbeat = insert(WorkerHeartbeat).values(worker_name=WORKER, updated_at=utcnow())
                db.execute(heartbeat.on_conflict_do_update(index_elements=['worker_name'], set_={'updated_at': heartbeat.excluded.updated_at}))
                db.commit()
                if outcome not in {'waiting', 'disabled', 'busy'} or outcome != previous:
                    logging.info('Energy sync cycle: %s', outcome)
                previous = outcome
        except Exception as error:
            # Never log Microsoft responses, exception URLs, tokens or credentials.
            logging.error('Energy sync cycle failed (%s)', type(error).__name__)
        stop.wait(5)


if __name__ == '__main__':
    main()
