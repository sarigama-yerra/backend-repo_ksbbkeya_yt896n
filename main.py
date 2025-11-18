import os
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import db, create_document, get_documents
from schemas import (
    User, Role, Customer, Vendor, Vehicle, Part, Technician,
    JobCard, PartsRequest, VehiclePurchase,
    Quotation, QuotationItem, Invoice,
    InventoryMovement, Account, JournalEntry, JournalEntryLine, Payment
)
from bson import ObjectId

app = FastAPI(title="Auto DMS Backend", version="0.1.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------- Utilities ---------------------------

def oid(id_str: str):
    try:
        return ObjectId(id_str)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")


def with_id(doc):
    if not doc:
        return doc
    doc["id"] = str(doc.pop("_id"))
    return doc


# --------------------------- Health ---------------------------
@app.get("/")
def read_root():
    return {"message": "Auto DMS API running"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name
            response["connection_status"] = "Connected"
            response["collections"] = db.list_collection_names()[:20]
        else:
            response["database"] = "❌ Not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"
    return response


# --------------------------- Admin / Users ---------------------------
class UserCreate(BaseModel):
    username: str
    full_name: str
    password_hash: str
    email: Optional[str] = None
    phone: Optional[str] = None
    roles: List[str] = []
    locale: str = "en"


@app.post("/api/users")
def create_user(u: UserCreate):
    user = User(
        username=u.username,
        full_name=u.full_name,
        password_hash=u.password_hash,
        email=u.email,
        phone=u.phone,
        roles=u.roles,
        locale=u.locale,
    )
    _id = create_document("user", user)
    return {"id": _id}


@app.get("/api/users")
def list_users(q: Optional[str] = None):
    filt = {}
    if q:
        filt = {"$or": [
            {"username": {"$regex": q, "$options": "i"}},
            {"full_name": {"$regex": q, "$options": "i"}},
            {"email": {"$regex": q, "$options": "i"}},
        ]}
    users = list(db.user.find(filt).limit(100))
    return [with_id(u) for u in users]


# --------------------------- Master Data ---------------------------
@app.post("/api/customers")
def create_customer(c: Customer):
    _id = create_document("customer", c)
    return {"id": _id}


@app.get("/api/customers")
def search_customers(q: Optional[str] = None):
    filt = {}
    if q:
        filt = {"$or": [
            {"name": {"$regex": q, "$options": "i"}},
            {"phone": {"$regex": q, "$options": "i"}},
            {"email": {"$regex": q, "$options": "i"}},
            {"national_id": {"$regex": q, "$options": "i"}},
        ]}
    docs = list(db.customer.find(filt).limit(100))
    return [with_id(d) for d in docs]


@app.post("/api/vendors")
def create_vendor(v: Vendor):
    _id = create_document("vendor", v)
    return {"id": _id}


@app.get("/api/vendors")
def list_vendors(q: Optional[str] = None):
    filt = {"name": {"$regex": q, "$options": "i"}} if q else {}
    docs = list(db.vendor.find(filt).limit(100))
    return [with_id(d) for d in docs]


# --------------------------- Vehicles ---------------------------
class VehicleCreate(BaseModel):
    vin: str
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    color: Optional[str] = None
    mileage: Optional[int] = None
    location: Optional[str] = None
    owner_customer_id: Optional[str] = None
    purchase_vendor_id: Optional[str] = None


@app.post("/api/vehicles")
def register_vehicle(v: VehicleCreate):
    existing = db.vehicle.find_one({"vin": v.vin})
    if existing:
        raise HTTPException(status_code=409, detail="VIN already registered")
    vehicle = Vehicle(
        vin=v.vin, make=v.make, model=v.model, year=v.year, color=v.color,
        mileage=v.mileage, location=v.location, owner_customer_id=v.owner_customer_id,
        purchase_vendor_id=v.purchase_vendor_id
    )
    _id = create_document("vehicle", vehicle)
    return {"id": _id}


@app.get("/api/vehicles")
def search_vehicles(q: Optional[str] = None):
    filt = {}
    if q:
        filt = {"$or": [
            {"vin": {"$regex": q, "$options": "i"}},
            {"make": {"$regex": q, "$options": "i"}},
            {"model": {"$regex": q, "$options": "i"}},
            {"color": {"$regex": q, "$options": "i"}},
        ]}
    docs = list(db.vehicle.find(filt).limit(100))
    return [with_id(d) for d in docs]


class VehicleStatusUpdate(BaseModel):
    status: Optional[str] = None
    location: Optional[str] = None


@app.patch("/api/vehicles/{vehicle_id}")
def update_vehicle_status(vehicle_id: str, body: VehicleStatusUpdate):
    update = {k: v for k, v in body.model_dump().items() if v is not None}
    res = db.vehicle.update_one({"_id": oid(vehicle_id)}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return {"success": True}


# --------------------------- Parts / Inventory ---------------------------
@app.post("/api/parts")
def create_part(p: Part):
    if db.part.find_one({"sku": p.sku}):
        raise HTTPException(status_code=409, detail="SKU already exists")
    _id = create_document("part", p)
    return {"id": _id}


@app.get("/api/parts")
def search_parts(q: Optional[str] = None, sku: Optional[str] = None):
    filt = {}
    if sku:
        filt = {"sku": sku}
    elif q:
        filt = {"$or": [
            {"sku": {"$regex": q, "$options": "i"}},
            {"name": {"$regex": q, "$options": "i"}},
        ]}
    docs = list(db.part.find(filt).limit(100))
    return [with_id(d) for d in docs]


class StockAdjust(BaseModel):
    quantity: int
    reason: Optional[str] = None


@app.post("/api/parts/{part_id}/adjust")
def adjust_stock(part_id: str, adj: StockAdjust):
    res = db.part.update_one({"_id": oid(part_id)}, {"$inc": {"stock": adj.quantity}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Part not found")
    move = InventoryMovement(part_id=part_id, movement_type="adjust", quantity=adj.quantity, note=adj.reason)
    create_document("inventorymovement", move)
    return {"success": True}


# --------------------------- Service: Job Cards & Parts Requests ---------------------------
@app.post("/api/jobcards")
def create_jobcard(j: JobCard):
    # Basic validation
    if not db.vehicle.find_one({"_id": oid(j.vehicle_id)}):
        raise HTTPException(status_code=404, detail="Vehicle not found")
    if not db.customer.find_one({"_id": oid(j.customer_id)}):
        raise HTTPException(status_code=404, detail="Customer not found")

    # Capacity checks for technicians (open/wip jobs)
    for tech_id in j.technician_ids:
        tech = db.technician.find_one({"_id": oid(tech_id)})
        if not tech:
            raise HTTPException(status_code=404, detail=f"Technician not found: {tech_id}")
        cap = int(tech.get("capacity", 3))
        open_jobs = db.jobcard.count_documents({
            "status": {"$in": ["open", "in_progress", "waiting_parts"]},
            "technician_ids": {"$in": [tech_id]}
        })
        if open_jobs >= cap:
            raise HTTPException(status_code=409, detail=f"Technician at capacity: {tech.get('name', tech_id)}")

    _id = create_document("jobcard", j)
    # Mark vehicle in_service
    db.vehicle.update_one({"_id": oid(j.vehicle_id)}, {"$set": {"status": "in_service"}})
    return {"id": _id}


@app.get("/api/jobcards")
def list_jobcards(status: Optional[str] = None):
    filt = {"status": status} if status else {}
    docs = list(db.jobcard.find(filt).sort("_id", -1).limit(100))
    return [with_id(d) for d in docs]


class JobStatus(BaseModel):
    status: str


class AssignTechnicians(BaseModel):
    technician_ids: List[str]
    primary_technician_id: Optional[str] = None


@app.post("/api/jobcards/{job_id}/status")
def set_jobcard_status(job_id: str, s: JobStatus):
    res = db.jobcard.update_one({"_id": oid(job_id)}, {"$set": {"status": s.status}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Job card not found")
    return {"success": True}


@app.post("/api/jobcards/{job_id}/assign")
def assign_technicians(job_id: str, body: AssignTechnicians):
    # Capacity checks
    for tech_id in body.technician_ids:
        tech = db.technician.find_one({"_id": oid(tech_id)})
        if not tech:
            raise HTTPException(status_code=404, detail=f"Technician not found: {tech_id}")
        cap = int(tech.get("capacity", 3))
        open_jobs = db.jobcard.count_documents({
            "_id": {"$ne": oid(job_id)},
            "status": {"$in": ["open", "in_progress", "waiting_parts"]},
            "technician_ids": {"$in": [tech_id]}
        })
        if open_jobs >= cap:
            raise HTTPException(status_code=409, detail=f"Technician at capacity: {tech.get('name', tech_id)}")

    update = {"technician_ids": body.technician_ids}
    if body.primary_technician_id:
        update["primary_technician_id"] = body.primary_technician_id
    res = db.jobcard.update_one({"_id": oid(job_id)}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Job card not found")
    return {"success": True}


@app.post("/api/parts-requests")
def create_parts_request(req: PartsRequest):
    if not db.jobcard.find_one({"_id": oid(req.job_card_id)}):
        raise HTTPException(status_code=404, detail="Job card not found")
    _id = create_document("partsrequest", req)
    db.jobcard.update_one({"_id": oid(req.job_card_id)}, {"$set": {"status": "waiting_parts"}})
    return {"id": _id}


class PartsRequestStatus(BaseModel):
    status: str  # approved, supplied, rejected


@app.post("/api/parts-requests/{req_id}/status")
def update_parts_request(req_id: str, body: PartsRequestStatus):
    pr = db.partsrequest.find_one({"_id": oid(req_id)})
    if not pr:
        raise HTTPException(status_code=404, detail="Parts request not found")
    db.partsrequest.update_one({"_id": pr["_id"]}, {"$set": {"status": body.status}})
    if body.status == "supplied":
        # deduct inventory
        for item in pr.get("items", []):
            db.part.update_one({"_id": oid(item["part_id"] )}, {"$inc": {"stock": -int(item.get("quantity", 1))}})
        db.jobcard.update_one({"_id": oid(pr["job_card_id"])}, {"$set": {"status": "in_progress"}})
    return {"success": True}


# --------------------------- Technicians ---------------------------
@app.post("/api/technicians")
def create_technician(t: Technician):
    _id = create_document("technician", t)
    return {"id": _id}


@app.get("/api/technicians")
def list_technicians(only_available: bool = Query(False)):
    filt = {"is_available": True} if only_available else {}
    docs = list(db.technician.find(filt))
    out = []
    for d in docs:
        tech_id_str = str(d.get("_id"))
        cap = int(d.get("capacity", 3))
        open_jobs = db.jobcard.count_documents({
            "status": {"$in": ["open", "in_progress", "waiting_parts"]},
            "technician_ids": {"$in": [tech_id_str]}
        })
        dd = with_id(d)
        dd["open_jobs"] = open_jobs
        dd["capacity"] = cap
        dd["remaining_capacity"] = max(cap - open_jobs, 0)
        out.append(dd)
    return out


# --------------------------- Sales: Quotations & Invoices ---------------------------
@app.post("/api/quotations")
def create_quotation(q: Quotation):
    _id = create_document("quotation", q)
    return {"id": _id}


@app.post("/api/quotations/{qid}/to-invoice")
def quotation_to_invoice(qid: str):
    q = db.quotation.find_one({"_id": oid(qid)})
    if not q:
        raise HTTPException(status_code=404, detail="Quotation not found")
    inv = Invoice(source="quotation", source_id=qid, customer_id=q["customer_id"], items=q["items"], vat_rate=q.get("vat_rate", 0.15))
    inv_id = create_document("invoice", inv)
    db.quotation.update_one({"_id": q["_id"]}, {"$set": {"status": "invoiced"}})
    return {"invoice_id": inv_id}


@app.post("/api/jobcards/{job_id}/prepare-invoice")
def jobcard_prepare_invoice(job_id: str):
    jc = db.jobcard.find_one({"_id": oid(job_id)})
    if not jc:
        raise HTTPException(status_code=404, detail="Job card not found")
    # build items from job card
    items: List[dict] = []
    for l in jc.get("labor", []):
        amount = float(l.get("flat_hours", 0)) * float(l.get("rate", 0)) - float(l.get("discount", 0))
        items.append({"item_type": "labor", "description": l.get("description"), "quantity": 1, "unit_price": amount, "discount": 0.0})
    for p in jc.get("parts", []):
        amount = float(p.get("price", 0))
        items.append({"item_type": "part", "ref_id": p.get("part_id"), "description": p.get("name"), "quantity": int(p.get("quantity", 1)), "unit_price": amount, "discount": float(p.get("discount", 0))})
    for m in jc.get("materials", []):
        items.append({"item_type": "material", "description": m.get("description"), "quantity": 1, "unit_price": float(m.get("cost", 0)), "discount": 0.0})
    for o in jc.get("outside", []):
        items.append({"item_type": "outside", "description": o.get("description"), "quantity": 1, "unit_price": float(o.get("cost", 0)), "discount": 0.0})
    inv = Invoice(source="job_card", source_id=job_id, customer_id=jc["customer_id"], items=items, vat_rate=jc.get("vat_rate", 0.15))
    inv_id = create_document("invoice", inv)
    db.jobcard.update_one({"_id": jc["_id"]}, {"$set": {"status": "ready"}})
    return {"invoice_id": inv_id}


# NEW: Create invoice (e.g., parts POS)
@app.post("/api/invoices")
def create_invoice(inv: Invoice):
    inv_id = create_document("invoice", inv)
    return {"id": inv_id}


@app.get("/api/invoices")
def list_invoices(status: Optional[str] = None):
    filt = {"status": status} if status else {}
    docs = list(db.invoice.find(filt).sort("_id", -1).limit(200))
    # compute totals with per-line rounding
    out = []
    for d in docs:
        subtotal = 0.0
        vat_total = 0.0
        for it in d.get("items", []):
            line_net = round(float(it.get("unit_price", 0)) * int(it.get("quantity", 1)) - float(it.get("discount", 0)), 2)
            subtotal += line_net
            vat_total += round(line_net * float(d.get("vat_rate", 0.15)), 2)
        subtotal = round(subtotal, 2)
        vat_total = round(vat_total, 2)
        total = round(subtotal + vat_total, 2)
        dd = with_id(d)
        dd["subtotal"] = subtotal
        dd["vat"] = vat_total
        dd["total"] = total
        out.append(dd)
    return out


class PayInvoice(BaseModel):
    cashier_id: Optional[str] = None
    method: Optional[str] = None  # legacy single method
    payments: Optional[List[Payment]] = None  # new split payments


def _validate_payments(payments: List[Payment], total_due: float):
    # Require references for certain methods
    for p in payments:
        if p.method in ("bank_transfer", "cheque", "account") and not p.reference:
            raise HTTPException(status_code=400, detail=f"Reference required for {p.method}")
        if p.amount <= 0:
            raise HTTPException(status_code=400, detail="Payment amount must be positive")
    paid_sum = round(sum(p.amount for p in payments), 2)
    total_due = round(total_due, 2)
    if paid_sum < total_due:
        raise HTTPException(status_code=400, detail="Insufficient payment amount")
    return paid_sum


@app.post("/api/invoices/{inv_id}/pay")
def pay_invoice(inv_id: str, body: PayInvoice):
    inv = db.invoice.find_one({"_id": oid(inv_id)})
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")

    # compute totals with per-line rounding
    subtotal = 0.0
    vat_total = 0.0
    for it in inv.get("items", []):
        line_net = round(float(it.get("unit_price", 0)) * int(it.get("quantity", 1)) - float(it.get("discount", 0)), 2)
        subtotal += line_net
        vat_total += round(line_net * float(inv.get("vat_rate", 0.15)), 2)
    subtotal = round(subtotal, 2)
    vat_total = round(vat_total, 2)
    total_due = round(subtotal + vat_total, 2)

    payments_payload: List[Payment] = []
    if body.payments and len(body.payments) > 0:
        payments_payload = body.payments
    else:
        # fallback to legacy single method
        payments_payload = [Payment(method=(body.method or "cash"), amount=total_due)]

    _validate_payments(payments_payload, total_due)

    # If parts sale, deduct inventory on payment
    if inv.get("source") == "parts":
        for it in inv.get("items", []):
            if it.get("item_type") == "part" and it.get("ref_id"):
                db.part.update_one({"_id": oid(it["ref_id"])}, {"$inc": {"stock": -int(it.get("quantity", 1))}})
                move = InventoryMovement(part_id=it["ref_id"], movement_type="out", quantity=int(it.get("quantity", 1)), reference=inv_id, note="parts sale")
                create_document("inventorymovement", move)

    res = db.invoice.update_one(
        {"_id": oid(inv_id)},
        {"$set": {
            "status": "paid",
            "cashier_id": body.cashier_id,
            "paid_at": datetime.utcnow(),
            "method": body.method,  # legacy
            "payments": [p.model_dump() for p in payments_payload],
        }}
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return {"success": True}


# --------------------------- Reports (basic) ---------------------------
@app.get("/api/reports/summary")
def summary_report():
    return {
        "vehicles": db.vehicle.count_documents({}),
        "parts": db.part.count_documents({}),
        "jobcards_open": db.jobcard.count_documents({"status": {"$in": ["open", "in_progress", "waiting_parts"]}}),
        "invoices_pending": db.invoice.count_documents({"status": "pending"}),
        "invoices_paid": db.invoice.count_documents({"status": "paid"}),
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
