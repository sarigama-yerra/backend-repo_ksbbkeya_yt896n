"""
Database Schemas for Automotive Dealership & Service System

Each Pydantic model maps to a MongoDB collection. Collection name is the lowercase
class name by convention.

This system covers modules: Service, Parts, Sales, Accounting, and Admin (Users & Permissions).
"""
from typing import List, Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime

# =============== ADMIN / USERS ==================
class Role(BaseModel):
    name: str = Field(..., description="Role name (e.g., admin, cashier, service_advisor)")
    permissions: List[str] = Field(default_factory=list, description="Permission codes")
    description: Optional[str] = None

class User(BaseModel):
    username: str
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    password_hash: str
    roles: List[str] = Field(default_factory=list)
    is_active: bool = True
    locale: Literal["en", "ar"] = "en"

# =============== MASTER DATA ==================
class Customer(BaseModel):
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    national_id: Optional[str] = None
    address: Optional[str] = None

class Vendor(BaseModel):
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    vat_number: Optional[str] = None
    address: Optional[str] = None

class Vehicle(BaseModel):
    vin: str = Field(..., min_length=5)
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    color: Optional[str] = None
    mileage: Optional[int] = None
    location: Optional[str] = Field(None, description="Showroom or yard")
    status: Literal["in_stock", "reserved", "sold", "in_service"] = "in_stock"
    owner_customer_id: Optional[str] = None  # for service cars
    purchase_vendor_id: Optional[str] = None  # for sales cars

class Part(BaseModel):
    sku: str = Field(..., description="Barcode / SKU")
    name: str
    make: Optional[str] = None
    model_compatibility: List[str] = Field(default_factory=list)
    bin_location: Optional[str] = None
    cost: float = 0.0
    price: float = 0.0
    stock: int = 0
    uom: str = "pcs"

class Technician(BaseModel):
    name: str
    code: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    is_available: bool = True

# =============== SERVICE ==================
class LaborItem(BaseModel):
    code: str
    description: str
    flat_hours: float = 0.0
    rate: float = 0.0
    discount: float = 0.0  # absolute amount

class PartItem(BaseModel):
    part_id: str
    name: Optional[str] = None
    quantity: int = 1
    price: float = 0.0
    discount: float = 0.0

class MaterialItem(BaseModel):
    description: str
    cost: float = 0.0

class OutsideWorkItem(BaseModel):
    description: str
    vendor_id: Optional[str] = None
    cost: float = 0.0

class PartsRequest(BaseModel):
    job_card_id: str
    items: List[PartItem]
    status: Literal["requested", "approved", "supplied", "rejected"] = "requested"

class JobCard(BaseModel):
    vehicle_id: str
    customer_id: str
    advisor_id: Optional[str] = None
    technician_ids: List[str] = Field(default_factory=list)
    complaint_notes: Optional[str] = None
    check_notes: Optional[str] = None
    labor: List[LaborItem] = Field(default_factory=list)
    parts: List[PartItem] = Field(default_factory=list)
    materials: List[MaterialItem] = Field(default_factory=list)
    outside: List[OutsideWorkItem] = Field(default_factory=list)
    status: Literal["open", "in_progress", "waiting_parts", "ready", "invoiced", "closed"] = "open"
    vat_rate: float = 0.15

# =============== SALES ==================
class VehiclePurchase(BaseModel):
    vendor_id: str
    vehicle_id: str
    purchase_price: float
    date: Optional[datetime] = None

class QuotationItem(BaseModel):
    item_type: Literal["vehicle", "part", "labor", "material", "outside"]
    ref_id: Optional[str] = None
    description: Optional[str] = None
    quantity: int = 1
    unit_price: float = 0.0
    discount: float = 0.0

class Quotation(BaseModel):
    customer_id: str
    items: List[QuotationItem]
    vat_rate: float = 0.15
    status: Literal["draft", "sent", "accepted", "rejected", "invoiced"] = "draft"

class Invoice(BaseModel):
    source: Literal["job_card", "parts", "vehicle", "quotation"]
    source_id: Optional[str] = None
    customer_id: str
    items: List[QuotationItem]
    vat_rate: float = 0.15
    status: Literal["pending", "paid", "cancelled"] = "pending"
    cashier_id: Optional[str] = None

# =============== PARTS / INVENTORY ==================
class InventoryMovement(BaseModel):
    part_id: str
    movement_type: Literal["in", "out", "adjust"]
    quantity: int
    reference: Optional[str] = None
    note: Optional[str] = None

# =============== ACCOUNTING ==================
class Account(BaseModel):
    code: str
    name: str
    type: Literal["asset", "liability", "equity", "revenue", "expense"]

class JournalEntryLine(BaseModel):
    account_code: str
    debit: float = 0.0
    credit: float = 0.0
    description: Optional[str] = None

class JournalEntry(BaseModel):
    date: datetime
    lines: List[JournalEntryLine]
    description: Optional[str] = None

