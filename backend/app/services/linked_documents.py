"""Freshness is a local-collector observation, not a Microsoft Graph ACL assertion."""
import datetime as dt
import hashlib
import json
from app.core.config import settings
from app.models.linked_documents import LinkedCollection, LinkedRevision


def utc(value):
    return value.replace(tzinfo=dt.timezone.utc) if value.tzinfo is None else value.astimezone(dt.timezone.utc)


def digest(chunks):
    return hashlib.sha256(json.dumps(chunks,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def linked(db,version):
    if not version.storage_key.startswith('linked/') or not settings.LINKED_DOCUMENTS_ENABLED:
        return None
    return db.get(LinkedRevision,version.version_id)


def usable(db,version):
    if not version.storage_key.startswith('linked/'):
        return True
    row=linked(db,version)
    collection=db.get(LinkedCollection,row.collection_id) if row else None
    return bool(row and collection and collection.enabled and row.available and row.chunks
        and 0 <= (dt.datetime.now(dt.timezone.utc)-utc(row.observed_at)).total_seconds() <= collection.freshness_seconds)
