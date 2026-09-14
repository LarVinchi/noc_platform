from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.incidents import TicketSequence, TICKET_CATEGORY_CODES


def generate_tt_number(db: Session, ticket_category: str) -> str:
    """
    Generates the next ticket number for a given category, in the same
    format as the historical incident log: {CODE}_IM_{DDMMYYYY}_{SEQUENCE}
    e.g. PW_IM_04092026_0515

    ticket_category must be one of: FIBER, POWER, TECHNICAL, MAINTENANCE, OTHER.
    Falls back to OTHER/OT for anything unrecognized rather than failing the
    incident save — a bad category should never block logging an incident.
    """
    code = TICKET_CATEGORY_CODES.get((ticket_category or "").upper(), "OT")

    # SELECT ... FOR UPDATE locks the row so two simultaneous incident saves
    # can never be handed the same sequence number.
    seq_row = db.execute(
        select(TicketSequence).where(TicketSequence.category_code == code).with_for_update()
    ).scalar_one_or_none()

    if seq_row is None:
        seq_row = TicketSequence(category_code=code, last_sequence=0)
        db.add(seq_row)
        db.flush()

    seq_row.last_sequence += 1
    next_seq = seq_row.last_sequence

    date_str = datetime.utcnow().strftime("%d%m%Y")
    return f"{code}_IM_{date_str}_{next_seq:04d}"
