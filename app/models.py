# app/models.py
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy.sql import func

from app import db


# =========================================================
# CORE MASTER
# =========================================================
class Customer(db.Model):
    __tablename__ = "customers"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, index=True)
    name = db.Column(db.String(255), nullable=False, index=True)
    tax_id = db.Column(db.String(30))
    phone = db.Column(db.String(50))
    email = db.Column(db.String(255))

    address = db.Column(db.Text)
    ship_address = db.Column(db.Text)

    is_active = db.Column(db.Boolean, default=True)

    # optional credit terms
    credit_days = db.Column(db.Integer, default=0)
    credit_limit = db.Column(db.Numeric(12, 2), default=Decimal("0.00"))


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(80), unique=True, index=True)
    name = db.Column(db.String(255), nullable=False, index=True)
    unit = db.Column(db.String(50), default="ชิ้น")

    # rental pricing
    rent_price_per_day = db.Column(db.Numeric(12, 2), default=Decimal("0.00"))

    # future: spec/serial handled in Phase 2 (Asset table)
    spec = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)


# =========================================================
# QUOTATION (RENTAL)
# =========================================================
class Quote(db.Model):
    __tablename__ = "quotes"

    id = db.Column(db.Integer, primary_key=True)

    doc_no = db.Column(db.String(30), unique=True, index=True)
    doc_date = db.Column(db.Date, default=date.today)

    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    customer = db.relationship("Customer")

    # rental period (header)
    rent_start = db.Column(db.Date, nullable=True)
    rent_end = db.Column(db.Date, nullable=True)

    project_site = db.Column(db.String(255))  # พื้นที่โครงการ

    # status (ภาษาไทย)
    # "ร่าง" / "อนุมัติ" / "ยกเลิก"
    status = db.Column(db.String(20), default="ร่าง", index=True)

    # tax modes
    vat_mode = db.Column(db.String(20), default="EXCLUDED")  # INCLUDED/EXCLUDED/NONE
    vat_rate = db.Column(db.Numeric(5, 2), default=Decimal("7.00"))
    vat_amount = db.Column(db.Numeric(12, 2), default=Decimal("0.00"))

    # withholding (%): 0/1/3/5
    wht_percent = db.Column(db.Numeric(5, 2), default=Decimal("0.00"))
    wht_amount = db.Column(db.Numeric(12, 2), default=Decimal("0.00"))

    # totals
    subtotal = db.Column(db.Numeric(12, 2), default=Decimal("0.00"))
    total_incl_vat = db.Column(db.Numeric(12, 2), default=Decimal("0.00"))
    net_payable = db.Column(db.Numeric(12, 2), default=Decimal("0.00"))

    # deposit
    deposit_extra = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))

    remark = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    approved_at = db.Column(db.DateTime, nullable=True)
    canceled_at = db.Column(db.DateTime, nullable=True)

    @property
    def deposit_lines_total(self) -> Decimal:
        total = Decimal("0.00")
        for ln in getattr(self, "lines", []) or []:
            total += Decimal(str(ln.deposit or 0))
        return total.quantize(Decimal("0.01"))

    @property
    def deposit_total(self) -> Decimal:
        extra = Decimal(str(self.deposit_extra or 0))
        return (self.deposit_lines_total + extra).quantize(Decimal("0.01"))

    @property
    def is_approved(self) -> bool:
        return (self.status or "") in ("อนุมัติ", "อนุมัติแล้ว")


class QuoteLine(db.Model):
    __tablename__ = "quote_lines"

    id = db.Column(db.Integer, primary_key=True)

    quote_id = db.Column(db.Integer, db.ForeignKey("quotes.id"), nullable=False, index=True)
    quote = db.relationship(
        "Quote",
        backref=db.backref("lines", cascade="all, delete-orphan", lazy="joined"),
    )

    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    product = db.relationship("Product")

    qty = db.Column(db.Numeric(12, 2), default=Decimal("1.00"))
    days = db.Column(db.Integer, default=1)  # manual per-line
    price = db.Column(db.Numeric(12, 2), default=Decimal("0.00"))  # price/day
    deposit = db.Column(db.Numeric(12, 2), default=Decimal("0.00"))  # per-line deposit

    line_total = db.Column(db.Numeric(12, 2), default=Decimal("0.00"))


# =========================================================
# CONTRACT + INSTALLMENT + DOCS (Phase 2)
# =========================================================
class RentalContract(db.Model):
    __tablename__ = "rental_contracts"

    id = db.Column(db.Integer, primary_key=True)

    quote_id = db.Column(db.Integer, db.ForeignKey("quotes.id"), nullable=False, index=True)
    quote = db.relationship(
        "Quote",
        backref=db.backref("contract", uselist=False, cascade="all, delete-orphan"),
    )

    doc_no = db.Column(db.String(30), unique=True, index=True)
    doc_date = db.Column(db.Date, default=date.today)

    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    project_site = db.Column(db.String(255))

    # status (ไทย)
    # "สัญญากำลังดำเนินการ" / "มีผล" / "ปิดสัญญา" / "ยกเลิกสัญญา"
    status = db.Column(db.String(50), default="สัญญากำลังดำเนินการ", index=True)

    remark = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    canceled_at = db.Column(db.DateTime, nullable=True)


class Installment(db.Model):
    __tablename__ = "installments"

    id = db.Column(db.Integer, primary_key=True)

    contract_id = db.Column(db.Integer, db.ForeignKey("rental_contracts.id"), nullable=False, index=True)
    contract = db.relationship(
        "RentalContract",
        backref=db.backref("installments", cascade="all, delete-orphan", order_by="Installment.seq"),
    )

    seq = db.Column(db.Integer, nullable=False)  # งวดที่
    due_date = db.Column(db.Date, nullable=True)
    amount = db.Column(db.Numeric(12, 2), default=Decimal("0.00"))

    # status (ไทย)
    # "ยังไม่ชำระ" / "ชำระแล้ว"
    status = db.Column(db.String(20), default="ยังไม่ชำระ", index=True)
    paid_at = db.Column(db.DateTime, nullable=True)
    paid_note = db.Column(db.Text)
    evidence_path = db.Column(db.String(500))  # path/URL หลักฐาน

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Billing(db.Model):
    __tablename__ = "billings"

    id = db.Column(db.Integer, primary_key=True)

    installment_id = db.Column(
        db.Integer,
        db.ForeignKey("installments.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    installment = db.relationship(
        "Installment",
        backref=db.backref("billing", uselist=False, cascade="all, delete-orphan"),
    )

    doc_no = db.Column(db.String(30), unique=True, index=True)
    doc_date = db.Column(db.Date, default=date.today)
    amount = db.Column(db.Numeric(12, 2), default=Decimal("0.00"))

    # status: "ยังไม่วางบิล" / "วางบิลแล้ว"
    status = db.Column(db.String(20), default="ยังไม่วางบิล", index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class TaxInvoice(db.Model):
    __tablename__ = "tax_invoices"

    id = db.Column(db.Integer, primary_key=True)

    installment_id = db.Column(
        db.Integer,
        db.ForeignKey("installments.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    installment = db.relationship(
        "Installment",
        backref=db.backref("tax_invoice", uselist=False, cascade="all, delete-orphan"),
    )

    doc_no = db.Column(db.String(30), unique=True, index=True)
    doc_date = db.Column(db.Date, default=date.today)
    amount = db.Column(db.Numeric(12, 2), default=Decimal("0.00"))

    # status: "ยังไม่อนุมัติ" / "อนุมัติแล้ว"
    status = db.Column(db.String(20), default="ยังไม่อนุมัติ", index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Receipt(db.Model):
    __tablename__ = "receipts"

    id = db.Column(db.Integer, primary_key=True)

    installment_id = db.Column(
        db.Integer,
        db.ForeignKey("installments.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    installment = db.relationship(
        "Installment",
        backref=db.backref("receipt", uselist=False, cascade="all, delete-orphan"),
    )

    doc_no = db.Column(db.String(30), unique=True, index=True)
    doc_date = db.Column(db.Date, default=date.today)
    amount = db.Column(db.Numeric(12, 2), default=Decimal("0.00"))

    # status: "ยังไม่รับเงิน" / "รับเงินแล้ว"
    status = db.Column(db.String(20), default="ยังไม่รับเงิน", index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


# =========================================================
# PURCHASE / STOCK (Phase: Purchase+Inventory)
# =========================================================
class Supplier(db.Model):
    __tablename__ = "suppliers"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(255), nullable=False, index=True)
    phone = db.Column(db.String(50))
    tax_id = db.Column(db.String(30))
    email = db.Column(db.String(255))
    address = db.Column(db.Text)

    credit_days = db.Column(db.Integer, default=0)
    credit_limit = db.Column(db.Numeric(12, 2), default=Decimal("0.00"))

    is_active = db.Column(db.Boolean, default=True, index=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (db.UniqueConstraint("name", name="uq_suppliers_name"),)


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)

    code = db.Column(db.String(20), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True, index=True)

    __table_args__ = (
        db.UniqueConstraint("code", name="uq_categories_code"),
    )


class Brand(db.Model):
    __tablename__ = "brands"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(255), nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True, index=True)

    __table_args__ = (db.UniqueConstraint("name", name="uq_brands_name"),)


class Unit(db.Model):
    __tablename__ = "units"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True, index=True)

    __table_args__ = (db.UniqueConstraint("name", name="uq_units_name"),)


def _add_months(d: date, months: int) -> date:
    """Add months to date without external deps (clamps day to month end)."""
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    if m in (1, 3, 5, 7, 8, 10, 12):
        last_day = 31
    elif m in (4, 6, 9, 11):
        last_day = 30
    else:
        leap = (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0))
        last_day = 29 if leap else 28
    day = min(d.day, last_day)
    return date(y, m, day)


class Asset(db.Model):
    __tablename__ = "assets"

    id = db.Column(db.Integer, primary_key=True)

    asset_code = db.Column(db.String(30), unique=True, index=True, nullable=False)

    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False, index=True)
    category = db.relationship("Category")

    brand_id = db.Column(db.Integer, db.ForeignKey("brands.id"), nullable=True, index=True)
    brand = db.relationship("Brand")

    unit_id = db.Column(db.Integer, db.ForeignKey("units.id"), nullable=True, index=True)
    unit = db.relationship("Unit")

    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=True, index=True)
    supplier = db.relationship("Supplier")

    name = db.Column(db.String(255), nullable=False, index=True)

    cost = db.Column(db.Numeric(12, 2), default=Decimal("0.00"))
    purchase_date = db.Column(db.Date, default=date.today, index=True)

    useful_life_days = db.Column(db.Integer, nullable=True)
    useful_life_months = db.Column(db.Integer, nullable=True)

    depreciation_method = db.Column(db.String(30), default="STRAIGHT_LINE")  # future-proof

    rent_day = db.Column(db.Numeric(12, 2), default=Decimal("0.00"))
    rent_month = db.Column(db.Numeric(12, 2), default=Decimal("0.00"))
    rent_year = db.Column(db.Numeric(12, 2), default=Decimal("0.00"))

    # ✅ ไทยล้วน
    # "พร้อมใช้งาน","จองแล้ว","กำลังเช่า","รอตรวจสภาพ","ซ่อม","สูญหาย","จำหน่ายออก"
    status = db.Column(db.String(20), default="พร้อมใช้งาน", index=True)

    # NOTE: มี FK 2 ทางระหว่าง assets <-> asset_photos
    main_photo_id = db.Column(db.Integer, db.ForeignKey("asset_photos.id"), nullable=True)

    main_photo = db.relationship(
        "AssetPhoto",
        foreign_keys=[main_photo_id],
        post_update=True,
    )

    photos = db.relationship(
        "AssetPhoto",
        foreign_keys="AssetPhoto.asset_id",
        back_populates="asset",
        cascade="all, delete-orphan",
        lazy=True,
    )

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def useful_life_total_days(self) -> int:
        if self.useful_life_days and int(self.useful_life_days) > 0:
            return int(self.useful_life_days)
        if self.useful_life_months and int(self.useful_life_months) > 0:
            return int(self.useful_life_months) * 30
        return 0

    @property
    def expired_date(self) -> date | None:
        if not self.purchase_date:
            return None
        if self.useful_life_days and int(self.useful_life_days) > 0:
            return self.purchase_date + timedelta(days=int(self.useful_life_days))
        if self.useful_life_months and int(self.useful_life_months) > 0:
            return _add_months(self.purchase_date, int(self.useful_life_months))
        return None

    @property
    def depreciation_accum(self) -> Decimal:
        """Straight-line accumulated depreciation (as-of today)."""
        try:
            cost = Decimal(str(self.cost or 0))
        except Exception:
            cost = Decimal("0")
        total_days = self.useful_life_total_days()
        if cost <= 0 or total_days <= 0 or not self.purchase_date:
            return Decimal("0")
        days_used = (date.today() - self.purchase_date).days
        if days_used <= 0:
            return Decimal("0")
        if days_used >= total_days:
            return cost
        per_day = cost / Decimal(str(total_days))
        acc = per_day * Decimal(str(days_used))
        if acc < 0:
            return Decimal("0")
        if acc > cost:
            return cost
        return acc

    @property
    def book_value(self) -> Decimal:
        try:
            cost = Decimal(str(self.cost or 0))
        except Exception:
            cost = Decimal("0")
        bv = cost - self.depreciation_accum
        if bv < 0:
            return Decimal("0")
        return bv


class AssetPhoto(db.Model):
    __tablename__ = "asset_photos"

    id = db.Column(db.Integer, primary_key=True)

    asset_id = db.Column(db.Integer, db.ForeignKey("assets.id"), nullable=False, index=True)

    asset = db.relationship(
        "Asset",
        foreign_keys=[asset_id],
        back_populates="photos",
    )

    file_path = db.Column(db.String(500), nullable=False)
    is_main = db.Column(db.Boolean, default=False, index=True)
    sort_order = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class PurchaseOrder(db.Model):
    __tablename__ = "purchase_orders"

    id = db.Column(db.Integer, primary_key=True)

    po_no = db.Column(db.String(30), unique=True, index=True, nullable=False)
    po_date = db.Column(db.Date, default=date.today, index=True)

    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=False, index=True)
    supplier = db.relationship("Supplier")

    remark = db.Column(db.Text)

    # ✅ ไทยล้วน: "ร่าง","อนุมัติ","รับบางส่วน","รับครบ","ยกเลิก"
    status = db.Column(db.String(20), default="ร่าง", index=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class PurchaseOrderLine(db.Model):
    __tablename__ = "purchase_order_lines"

    id = db.Column(db.Integer, primary_key=True)

    po_id = db.Column(db.Integer, db.ForeignKey("purchase_orders.id"), nullable=False, index=True)
    po = db.relationship(
        "PurchaseOrder",
        backref=db.backref("lines", cascade="all, delete-orphan", lazy=True),
    )

    item_name = db.Column(db.String(255), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True, index=True)
    category = db.relationship("Category")

    unit_id = db.Column(db.Integer, db.ForeignKey("units.id"), nullable=True, index=True)
    unit = db.relationship("Unit")

    qty = db.Column(db.Numeric(12, 2), default=Decimal("0.00"))
    unit_cost = db.Column(db.Numeric(12, 2), default=Decimal("0.00"))
    line_total = db.Column(db.Numeric(12, 2), default=Decimal("0.00"))

    # ✅ Phase GRN: เก็บยอดรับสะสม
    qty_received_total = db.Column(db.Numeric(12, 2), default=Decimal("0.00"), server_default="0.00")
    # OPEN/PARTIAL/FULL
    receive_status = db.Column(db.String(20), default="OPEN", server_default="OPEN", index=True)


class GRN(db.Model):
    __tablename__ = "grns"

    id = db.Column(db.Integer, primary_key=True)

    grn_no = db.Column(db.String(30), unique=True, index=True, nullable=False)
    grn_date = db.Column(db.Date, default=date.today, index=True)

    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=False, index=True)
    supplier = db.relationship("Supplier")

    po_id = db.Column(db.Integer, db.ForeignKey("purchase_orders.id"), nullable=True, index=True)
    po = db.relationship("PurchaseOrder")

    remark = db.Column(db.Text)

    # ✅ ไทยล้วน: "ร่าง","บันทึกแล้ว","สร้างอุปกรณ์แล้ว","ยกเลิก"
    status = db.Column(db.String(20), default="ร่าง", index=True)

    assets_generated_at = db.Column(db.DateTime, nullable=True, index=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class GRNLine(db.Model):
    __tablename__ = "grn_lines"

    id = db.Column(db.Integer, primary_key=True)

    grn_id = db.Column(db.Integer, db.ForeignKey("grns.id"), nullable=False, index=True)
    grn = db.relationship(
        "GRN",
        backref=db.backref("lines", cascade="all, delete-orphan", lazy=True),
    )

    po_line_id = db.Column(db.Integer, db.ForeignKey("purchase_order_lines.id"), nullable=True, index=True)
    po_line = db.relationship("PurchaseOrderLine")

    item_name = db.Column(db.String(255), nullable=False)

    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True, index=True)
    category = db.relationship("Category")

    unit_id = db.Column(db.Integer, db.ForeignKey("units.id"), nullable=True, index=True)
    unit = db.relationship("Unit")

    qty_received = db.Column(db.Numeric(12, 2), default=Decimal("0.00"))
    unit_cost = db.Column(db.Numeric(12, 2), default=Decimal("0.00"))


class StockMove(db.Model):
    __tablename__ = "stock_moves"

    id = db.Column(db.Integer, primary_key=True)

    move_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    ref_type = db.Column(
        db.String(20),
        nullable=False,
        index=True,
    )  # PO/GRN/ADJ/RESERVE/UNRESERVE/RENT_OUT/RENT_IN/REPAIR_DONE/ASSET_GEN
    ref_no = db.Column(db.String(50), nullable=True, index=True)

    asset_id = db.Column(db.Integer, db.ForeignKey("assets.id"), nullable=True, index=True)
    asset = db.relationship("Asset")

    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True, index=True)
    category = db.relationship("Category")

    qty_in = db.Column(db.Numeric(12, 2), default=Decimal("0.00"), server_default="0.00")
    qty_out = db.Column(db.Numeric(12, 2), default=Decimal("0.00"), server_default="0.00")

    note = db.Column(db.Text)

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=func.now(),
    )

    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        server_default=func.now(),
    )


# =========================================================
# STEP 3-5 (Reservation / Rental / Repair)
# =========================================================
class Reservation(db.Model):
    __tablename__ = "reservations"

    id = db.Column(db.Integer, primary_key=True)

    quote_id = db.Column(db.Integer, db.ForeignKey("quotes.id"), nullable=False, index=True)
    quote = db.relationship(
        "Quote",
        backref=db.backref("reservations", cascade="all, delete-orphan", lazy=True),
    )

    doc_no = db.Column(db.String(30), unique=True, index=True, nullable=False)
    doc_date = db.Column(db.Date, default=date.today, index=True)

    # ไทยล้วน: "ร่าง","ยืนยันแล้ว","ยกเลิก","หมดอายุ"
    status = db.Column(db.String(20), default="ร่าง", index=True)

    expires_at = db.Column(db.DateTime, nullable=True, index=True)
    remark = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    confirmed_at = db.Column(db.DateTime, nullable=True)
    canceled_at = db.Column(db.DateTime, nullable=True)


class ReservationLine(db.Model):
    __tablename__ = "reservation_lines"

    id = db.Column(db.Integer, primary_key=True)

    reservation_id = db.Column(db.Integer, db.ForeignKey("reservations.id"), nullable=False, index=True)
    reservation = db.relationship(
        "Reservation",
        backref=db.backref("lines", cascade="all, delete-orphan", lazy=True),
    )

    quote_line_id = db.Column(db.Integer, db.ForeignKey("quote_lines.id"), nullable=True, index=True)
    quote_line = db.relationship("QuoteLine")

    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True, index=True)
    category = db.relationship("Category")

    qty_requested = db.Column(db.Numeric(12, 2), default=Decimal("0.00"), server_default="0.00")

    note = db.Column(db.Text)


class ReservationAsset(db.Model):
    __tablename__ = "reservation_assets"

    id = db.Column(db.Integer, primary_key=True)

    reservation_line_id = db.Column(db.Integer, db.ForeignKey("reservation_lines.id"), nullable=False, index=True)
    reservation_line = db.relationship(
        "ReservationLine",
        backref=db.backref("locked_assets", cascade="all, delete-orphan", lazy=True),
    )

    asset_id = db.Column(db.Integer, db.ForeignKey("assets.id"), nullable=False, index=True)
    asset = db.relationship("Asset")

    locked_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    released_at = db.Column(db.DateTime, nullable=True, index=True)


class RentalOrder(db.Model):
    __tablename__ = "rental_orders"

    id = db.Column(db.Integer, primary_key=True)

    reservation_id = db.Column(db.Integer, db.ForeignKey("reservations.id"), nullable=True, index=True)
    reservation = db.relationship(
        "Reservation",
        backref=db.backref("rental_orders", cascade="all, delete-orphan", lazy=True),
    )

    doc_no = db.Column(db.String(30), unique=True, index=True, nullable=False)
    doc_date = db.Column(db.Date, default=date.today, index=True)

    # ไทยล้วน: "ร่าง","ส่งมอบแล้ว","ปิดงาน","ยกเลิก"
    status = db.Column(db.String(20), default="ร่าง", index=True)

    rent_start = db.Column(db.Date, nullable=True)
    rent_end = db.Column(db.Date, nullable=True)

    remark = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    delivered_at = db.Column(db.DateTime, nullable=True)
    closed_at = db.Column(db.DateTime, nullable=True)
    canceled_at = db.Column(db.DateTime, nullable=True)


class RentalLine(db.Model):
    __tablename__ = "rental_lines"

    id = db.Column(db.Integer, primary_key=True)

    rental_order_id = db.Column(db.Integer, db.ForeignKey("rental_orders.id"), nullable=False, index=True)
    rental_order = db.relationship(
        "RentalOrder",
        backref=db.backref("lines", cascade="all, delete-orphan", lazy=True),
    )

    reservation_line_id = db.Column(db.Integer, db.ForeignKey("reservation_lines.id"), nullable=True, index=True)
    reservation_line = db.relationship("ReservationLine")

    asset_id = db.Column(db.Integer, db.ForeignKey("assets.id"), nullable=False, index=True)
    asset = db.relationship("Asset")

    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True, index=True)
    category = db.relationship("Category")

    qty = db.Column(db.Numeric(12, 2), default=Decimal("1.00"), server_default="1.00")

    note = db.Column(db.Text)


class RepairOrder(db.Model):
    __tablename__ = "repair_orders"

    id = db.Column(db.Integer, primary_key=True)

    rental_order_id = db.Column(db.Integer, db.ForeignKey("rental_orders.id"), nullable=True, index=True)
    rental_order = db.relationship(
        "RentalOrder",
        backref=db.backref("repair_orders", cascade="all, delete-orphan", lazy=True),
    )

    doc_no = db.Column(db.String(30), unique=True, index=True, nullable=False)
    doc_date = db.Column(db.Date, default=date.today, index=True)

    # ไทยล้วน: "เปิดงาน","กำลังซ่อม","รออะไหล่","ซ่อมเสร็จ","ส่งคืนคลัง","ยกเลิก"
    status = db.Column(db.String(20), default="เปิดงาน", index=True)

    remark = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    finished_at = db.Column(db.DateTime, nullable=True)
    canceled_at = db.Column(db.DateTime, nullable=True)


class RepairLine(db.Model):
    __tablename__ = "repair_lines"

    id = db.Column(db.Integer, primary_key=True)

    repair_order_id = db.Column(db.Integer, db.ForeignKey("repair_orders.id"), nullable=False, index=True)
    repair_order = db.relationship(
        "RepairOrder",
        backref=db.backref("lines", cascade="all, delete-orphan", lazy=True),
    )

    asset_id = db.Column(db.Integer, db.ForeignKey("assets.id"), nullable=False, index=True)
    asset = db.relationship("Asset")

    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True, index=True)
    category = db.relationship("Category")

    note = db.Column(db.Text)