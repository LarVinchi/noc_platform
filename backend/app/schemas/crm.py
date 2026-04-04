from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from uuid import UUID
from datetime import datetime

# 1. Base Schema (Shared attributes)
class CustomerBase(BaseModel):
    customer_type: str
    customer_name: str
    service_id_code: str
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None

# 2. Response Schema (What we send back to the frontend)
class CustomerResponse(CustomerBase):
    customer_id: UUID
    created_at: datetime

    # This tells Pydantic to read data directly from our SQLAlchemy models
    model_config = ConfigDict(from_attributes=True)