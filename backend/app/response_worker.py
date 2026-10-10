"""Run with python -m app.response_worker; no external notification transport."""
import logging
import signal
from threading import Event
from sqlalchemy.dialects.postgresql import insert
from app.core.db import SessionLocal
from app.core.security import actor_context
from app.models.response import WorkerHeartbeat
from app.models.provisioning import ServiceOrder  # Register the activity order foreign key for standalone worker flushes.
from app.services.escalation import run_escalations
from app.services.incident_response import now_utc

stop = Event()


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    signal.signal(signal.SIGTERM, lambda *args: stop.set())
    signal.signal(signal.SIGINT, lambda *args: stop.set())
    actor_context.set({'id': 'response-worker', 'verified': False, 'request_id': ''})
    while not stop.is_set():
        try:
            with SessionLocal() as db:
                count = run_escalations(db)
                heartbeat = insert(WorkerHeartbeat).values(worker_name='response-escalation', updated_at=now_utc())
                db.execute(heartbeat.on_conflict_do_update(index_elements=['worker_name'], set_={'updated_at': heartbeat.excluded.updated_at}))
                db.commit()
                logging.info('Response cycle complete; %d new escalation drafts/events', count)
        except Exception as error:
            logging.error('Response cycle failed (%s); retrying', type(error).__name__)
        stop.wait(30)


if __name__ == '__main__':
    main()
