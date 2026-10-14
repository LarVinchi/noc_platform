from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from typing import Optional
from datetime import datetime
from uuid import UUID
from app.models.provisioning import ServiceCategory, WorkflowStage, ISPType
import re

# --- NEW: Schema for Installation Metrics ---
class InstallMetricsResponse(BaseModel):
    id: int
    flexscan_result_dbm: Optional[float] = None
    checklist_completed: bool
    photo_nap_url: Optional[str] = None
    photo_routing_url: Optional[str] = None
    photo_rosette_url: Optional[str] = None
    photo_flexscan_url: Optional[str] = None
    acceptance_doc_url: Optional[str] = None

    class Config:
        from_attributes = True

class ServiceOrderCreate(BaseModel):
    # Data the manager fills out to create the order
    service_category: ServiceCategory = ServiceCategory.FTTH
    customer_name: str = Field(min_length=1, max_length=300)
    service_address: str = Field(min_length=1, max_length=2000)
    phone_number: Optional[str] = None
    email: Optional[EmailStr] = None
    isp: ISPType
    bandwidth: str = Field(min_length=1, max_length=50)
    fn_number: Optional[str] = Field(default=None, max_length=100)
    work_order_id: Optional[str] = Field(default=None, max_length=100)
    source_status: Optional[str] = Field(default=None, max_length=50)

    @field_validator("customer_name", "service_address", "bandwidth", mode="before")
    @classmethod
    def trim_required(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("fn_number", "work_order_id", mode="before")
    @classmethod
    def normalize_reference(cls, value):
        return value.strip().upper() or None if isinstance(value, str) else value

    @field_validator("email", "phone_number", "source_status", mode="before")
    @classmethod
    def normalize_optional(cls, value):
        return value.strip() or None if isinstance(value, str) else value

    @field_validator("fn_number")
    @classmethod
    def validate_fn(cls, value):
        if value and not re.fullmatch(r"FN\d+", value):
            raise ValueError("FN number must contain FN followed by digits")
        return value

    @field_validator("bandwidth")
    @classmethod
    def validate_bandwidth(cls, value):
        match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(Mbps|Gbps)", value, re.I)
        if not match or float(match[1]) <= 0:
            raise ValueError("Use a positive service package such as 100Mbps")
        return match[1] + ("Mbps" if match[2].lower() == "mbps" else "Gbps")

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, value):
        if value and (not re.fullmatch(r"\+?[\d ()-]+", value) or not 7 <= len(re.sub(r"\D", "", value)) <= 15):
            raise ValueError("Use a phone number containing 7–15 digits")
        return value

class IntakePreviewRequest(BaseModel):
    raw_text: str = Field(min_length=1, max_length=20000)
    isp: ISPType = ISPType.MTNN

class IntakePreviewResponse(BaseModel):
    order: ServiceOrderCreate
    warnings: list[str]

class IntakeCreateRequest(BaseModel):
    raw_text: str = Field(min_length=1, max_length=20000)
    order: ServiceOrderCreate

class ServiceOrderAllocate(BaseModel):
    nap_id: UUID
    drop_cable_id: Optional[UUID] = None
    new_drop_cable_code: Optional[str] = Field(default=None, min_length=1, max_length=100)
    port_number: int = Field(ge=1)
    installer: str = Field(min_length=1, max_length=200)
    planned_install_date: datetime

    @model_validator(mode="after")
    def validate_assignment(self):
        self.installer = self.installer.strip()
        if not self.installer:
            raise ValueError("Installer is required")
        if bool(self.drop_cable_id) == bool(self.new_drop_cable_code):
            raise ValueError("Select an existing drop cable or enter a new cable code")
        if self.planned_install_date.tzinfo is None:
            raise ValueError("Installation date must include its time zone")
        if self.new_drop_cable_code:
            self.new_drop_cable_code = self.new_drop_cable_code.strip().upper()
            if not re.fullmatch(r"[A-Z0-9_-]+", self.new_drop_cable_code):
                raise ValueError("Drop cable code may contain letters, digits, underscores and hyphens")
        return self

class ServiceOrderResponse(BaseModel):
    # Read models preserve legacy values; stricter intake validation is for writes.
    service_category: ServiceCategory
    customer_name: str
    service_address: str
    phone_number: Optional[str] = None
    email: Optional[str] = None
    isp: ISPType
    bandwidth: str
    fn_number: Optional[str] = None
    work_order_id: Optional[str] = None
    source_status: Optional[str] = None
    # Data we send back to the frontend
    order_id: UUID
    service_order_number: Optional[str]
    service_id: Optional[str]
    status: WorkflowStage
    created_at: datetime
    
    # Allocation Fields
    nap_id: Optional[UUID] = None
    drop_cable_id: Optional[UUID] = None
    nap_port: Optional[int] = None
    
    # --- NEW: Added Metrics Field ---
    metrics: Optional[InstallMetricsResponse] = None
    intake_source: Optional[str] = None
    drop_tech_name: Optional[str] = None
    activated_service_id: Optional[UUID] = None
    nap_code: Optional[str] = None
    drop_cable_code: Optional[str] = None
    planned_install_date: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class IntakeCreateResponse(BaseModel):
    outcome: str
    order: ServiceOrderResponse
