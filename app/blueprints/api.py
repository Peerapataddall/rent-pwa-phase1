# app/blueprints/api.py
from __future__ import annotations

import os
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from flask import Blueprint, jsonify, request
from sqlalchemy import func

from app import db
from app.models import (
    Asset,
    AssetPhoto,
    Brand,
    Category,
    GRN,
    GRNLine,
    PurchaseOrder,
    PurchaseOrderLine,
    StockMove,
    Supplier,
    Unit,
    Customer,
    Product,
)

bp = Blueprint("api", __name__)


# =========================================================
# Helpers
# =========================================================
def _d(x) -> Decimal:
    try:
        return Decimal(str(x or 0))
    except Exception:
        return Decimal("0")


def _to_bool(v) -> bool:
    """
    Robust bool parsing:
    - True for: 1, "1", "true", "ทรู", "yes", True
    - False for: 0, "0", "false", "", None, False
    """
    if v is None:
        return False
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return int(v) != 0
    s = str(v).strip().lower()
    return s in ("1", "true", "yes", "y", "on")


def _ok(payload: dict, status_code: int = 200):
    return jsonify({"ok": True, **payload}), status_code


def _bad(message: str, status_code: int = 400):
    return jsonify({"ok": False, "message": message}), status_code


def _to_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except Exception:
        return None


def _uploads_root() -> Path:
    # app/static/uploads/assets
    here = Path(__file__).resolve()
    app_dir = here.parents[1]
    uploads = app_dir / "static" / "uploads" / "assets"
    uploads.mkdir(parents=True, exist_ok=True)
    return uploads


def _asset_auto_code(category_id: int, d: date) -> str:
    cat = Category.query.get(category_id)
    if not cat:
        raise ValueError("ไม่พบหมวดหมู่")
    code = (cat.code or "").strip().upper()
    if not code:
        raise ValueError("หมวดหมู่ยังไม่มี code")

    ddmmyy = d.strftime("%d%m%y")
    prefix = f"{code}{ddmmyy}"

    last = (
        Asset.query.filter(Asset.asset_code.like(prefix + "%"))
        .order_by(Asset.asset_code.desc())
        .first()
    )
    last_n = 0
    if last and last.asset_code and len(last.asset_code) >= len(prefix) + 2:
        try:
            last_n = int(str(last.asset_code)[-2:])
        except Exception:
            last_n = 0

    nxt = last_n + 1
    if nxt > 99:
        raise ValueError("เลขรันของวันนั้นเต็มแล้ว (01-99)")

    return prefix + f"{nxt:02d}"


def _po_no(d: date) -> str:
    yymm = f"{d.year % 100:02d}{d.month:02d}"
    prefix = f"PO{yymm}"
    last = (
        PurchaseOrder.query.filter(PurchaseOrder.po_no.like(prefix + "%"))
        .order_by(PurchaseOrder.id.desc())
        .first()
    )
    if not last:
        return prefix + f"{1:05d}"
    try:
        n = int(str(last.po_no)[-5:]) + 1
    except Exception:
        n = last.id + 1
    return prefix + f"{n:05d}"


def _grn_no(d: date) -> str:
    yymm = f"{d.year % 100:02d}{d.month:02d}"
    prefix = f"GR{yymm}"
    last = (
        GRN.query.filter(GRN.grn_no.like(prefix + "%"))
        .order_by(GRN.id.desc())
        .first()
    )
    if not last:
        return prefix + f"{1:05d}"
    try:
        n = int(str(last.grn_no)[-5:]) + 1
    except Exception:
        n = last.id + 1
    return prefix + f"{n:05d}"


def _recalc_po_received(po_id: int):
    """
    Recalculate PO line received totals from GRN lines.
    - Sum qty_received per po_line_id for GRNs that reference this PO
    - Then set PO.status (ไทย) = "รับครบ"/"รับบางส่วน"/"อนุมัติ" ตามยอดรับจริง
      (ถ้า PO ถูกยกเลิกแล้ว จะไม่เปลี่ยนสถานะ)
    """
    po = PurchaseOrder.query.get(po_id)
    if not po:
        return

    if (po.status or "") == "ยกเลิก":
        return

    sums = dict(
        db.session.query(
            GRNLine.po_line_id,
            func.coalesce(func.sum(GRNLine.qty_received), 0),
        )
        .join(GRN, GRN.id == GRNLine.grn_id)
        .filter(GRN.po_id == po_id)
        .filter(GRNLine.po_line_id.isnot(None))
        .group_by(GRNLine.po_line_id)
        .all()
    )

    any_received = False
    all_full = True

    for ln in po.lines:
        rcv = _d(sums.get(ln.id) or 0)
        ln.qty_received_total = rcv

        q = _d(ln.qty or 0)
        if q <= 0:
            ln.receive_status = "OPEN"
            all_full = False
            continue

        if rcv <= 0:
            ln.receive_status = "OPEN"
            all_full = False
        elif rcv < q:
            ln.receive_status = "PARTIAL"
            any_received = True
            all_full = False
        else:
            ln.receive_status = "FULL"
            any_received = True

    cur = (po.status or "").strip()
    if cur == "ร่าง":
        pass
    else:
        if any_received and all_full:
            po.status = "รับครบ"
        elif any_received and not all_full:
            po.status = "รับบางส่วน"
        else:
            if cur in ("รับบางส่วน", "รับครบ"):
                po.status = "อนุมัติ"

    db.session.flush()


def _ensure_thai_po_status(po: PurchaseOrder):
    """Normalize PO.status ให้เป็นไทยล้วนเสมอ (กันของเก่าที่เป็นอังกฤษหลุดมา)."""
    s = (po.status or "").strip()
    if not s:
        po.status = "ร่าง"
        return
    m = {
        "DRAFT": "ร่าง",
        "APPROVED": "อนุมัติ",
        "CANCELLED": "ยกเลิก",
        "CANCELED": "ยกเลิก",
    }
    up = s.upper()
    if up in m:
        po.status = m[up]


def _ensure_thai_asset_status(a: Asset):
    """Normalize Asset.status ให้เป็นไทยล้วนเสมอ (กันของเก่าที่เป็นอังกฤษหลุดมา)."""
    s = (a.status or "").strip()
    if not s:
        a.status = "พร้อมใช้งาน"
        return
    m = {
        "AVAILABLE": "พร้อมใช้งาน",
        "RESERVED": "จองแล้ว",
        "RENTED": "กำลังเช่า",
        "INSPECT": "รอตรวจสภาพ",
        "REPAIR": "ซ่อม",
        "LOST": "สูญหาย",
        "RETIRED": "จำหน่ายออก",
    }
    up = s.upper()
    if up in m:
        a.status = m[up]


def _ensure_thai_grn_status(grn: GRN):
    """Normalize GRN.status ให้เป็นไทยล้วนเสมอ."""
    s = (getattr(grn, "status", "") or "").strip()
    if not s:
        grn.status = "ร่าง"
        return
    m = {
        "DRAFT": "ร่าง",
        "SAVED": "บันทึกแล้ว",
        "POSTED": "บันทึกแล้ว",
        "CANCELLED": "ยกเลิก",
        "CANCELED": "ยกเลิก",
        "ASSETED": "สร้างอุปกรณ์แล้ว",
    }
    up = s.upper()
    if up in m:
        grn.status = m[up]


def _assert_grn_editable(grn: GRN):
    """
    กติกา Step 1:
    - ถ้า GRN.status="สร้างอุปกรณ์แล้ว" หรือ assets_generated_at ไม่ว่าง
      => ห้ามแก้ lines/qty และห้าม generate ซ้ำ
    """
    if getattr(grn, "assets_generated_at", None):
        raise ValueError("GRN นี้ถูก Generate Assets แล้ว ไม่อนุญาตให้แก้ไข กรุณาสร้าง GRN ใหม่")
    if (getattr(grn, "status", "") or "").strip() == "สร้างอุปกรณ์แล้ว":
        raise ValueError("GRN นี้อยู่สถานะ 'สร้างอุปกรณ์แล้ว' ไม่อนุญาตให้แก้ไข กรุณาสร้าง GRN ใหม่")


# =========================================================
# Existing (Customer / Product)
# =========================================================
@bp.post("/customers")
def api_create_customer():
    data = request.get_json(force=True) or {}

    name = (data.get("name") or "").strip()
    if not name:
        return _bad("กรุณาใส่ชื่อลูกค้า")

    next_url = (data.get("next") or "").strip() or None

    c = Customer(
        code=(data.get("code") or "").strip() or None,
        name=name,
        tax_id=(data.get("tax_id") or "").strip() or None,
        phone=(data.get("phone") or "").strip() or None,
        email=(data.get("email") or "").strip() or None,
        address=(data.get("address") or "").strip() or None,
        credit_days=int(data.get("credit_days") or 0),
        credit_limit=_d(data.get("credit_limit")),
        is_active=True,
    )
    db.session.add(c)
    db.session.commit()

    return _ok({"id": c.id, "name": c.name, "email": c.email, "next": next_url})


@bp.post("/products")
def api_create_product():
    data = request.get_json(force=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return _bad("กรุณาใส่ชื่อสินค้า")

    sku = (data.get("sku") or "").strip() or None

    # 1) สร้าง Product (ของเดิม)
    p = Product(
        sku=sku,
        name=name,
        unit=(data.get("unit") or "ชิ้น").strip(),
        rent_price_per_day=data.get("rent_price_per_day") or 0,
        spec=(data.get("spec") or "").strip() or None,
        is_active=True,
    )
    db.session.add(p)
    db.session.flush()  # ได้ p.id ก่อน commit

    # 2) ✅ สร้าง/อัปเดต Category ให้ทันที (เพื่อให้ไปขึ้นเมนูหมวดหมู่)
    # - ใช้ sku เป็น code (ถ้าไม่กรอก sku จะสร้าง code อัตโนมัติ)
    cat_code = sku or f"PRD{p.id:05d}"  # เช่น PRD00001
    c = Category.query.filter_by(code=cat_code).first()
    if not c:
        c = Category(code=cat_code, name=name, is_active=True)
        db.session.add(c)
    else:
        # ถ้ามีอยู่แล้ว ให้ถือว่า “อัปเดตชื่อ/เปิดใช้งาน”
        c.name = name
        c.is_active = True

    db.session.commit()

    return _ok({
        "id": p.id,
        "name": p.name,
        "rent_price_per_day": str(p.rent_price_per_day),
        "category_code": c.code,
        "category_id": c.id,
    })

# =========================================================
# Master CRUD (Supplier / Category / Brand / Unit)
# =========================================================
@bp.get("/masters")
def api_get_masters():
    suppliers = Supplier.query.filter(Supplier.is_active.is_(True)).order_by(Supplier.name.asc()).all()
    categories = Category.query.filter(Category.is_active.is_(True)).order_by(Category.name.asc()).all()
    brands = Brand.query.filter(Brand.is_active.is_(True)).order_by(Brand.name.asc()).all()
    units = Unit.query.filter(Unit.is_active.is_(True)).order_by(Unit.name.asc()).all()

    # ✅ เพิ่ม PO (เฉพาะ "อนุมัติ" ที่ยังรับไม่ครบ/หรือรับได้)
    pos = (
        PurchaseOrder.query
        .filter(PurchaseOrder.status.in_(["อนุมัติ", "รับบางส่วน"]))
        .order_by(PurchaseOrder.id.desc())
        .limit(300)
        .all()
    )

    return _ok(
        {
            "suppliers": [{"id": x.id, "name": x.name} for x in suppliers],
            "categories": [{"id": x.id, "code": x.code, "name": x.name} for x in categories],
            "brands": [{"id": x.id, "name": x.name} for x in brands],
            "units": [{"id": x.id, "name": x.name} for x in units],
            "pos": [
                {
                    "id": po.id,
                    "po_no": po.po_no,
                    "supplier_id": po.supplier_id,
                    "supplier_name": (po.supplier.name if po.supplier else ""),
                    "po_date": (po.po_date.isoformat() if getattr(po, "po_date", None) else ""),
                    "status": (po.status or ""),
                }
                for po in pos
            ],
        }
    )


@bp.post("/suppliers")
def api_upsert_supplier():
    data = request.get_json(force=True) or {}
    sid = data.get("id")

    name = (data.get("name") or "").strip()
    if not name:
        return _bad("กรุณาใส่ชื่อเจ้าหนี้")

    if sid:
        s = Supplier.query.get(int(sid))
        if not s:
            return _bad("ไม่พบเจ้าหนี้")
    else:
        s = Supplier(is_active=True)

    s.name = name
    s.phone = (data.get("phone") or "").strip() or None
    s.tax_id = (data.get("tax_id") or "").strip() or None
    s.email = (data.get("email") or "").strip() or None
    s.address = (data.get("address") or "").strip() or None
    s.credit_days = int(data.get("credit_days") or 0)
    s.credit_limit = _d(data.get("credit_limit"))
    if "is_active" in data:
        s.is_active = _to_bool(data.get("is_active"))

    db.session.add(s)
    db.session.commit()

    return _ok({"id": s.id, "name": s.name})


@bp.get("/suppliers/<int:supplier_id>")
def api_get_supplier(supplier_id: int):
    s = Supplier.query.get_or_404(supplier_id)
    return _ok(
        {
            "supplier": {
                "id": s.id,
                "name": s.name,
                "phone": s.phone,
                "tax_id": s.tax_id,
                "email": s.email,
                "address": s.address,
                "credit_days": s.credit_days,
                "credit_limit": str(s.credit_limit or 0),
                "is_active": bool(s.is_active),
            }
        }
    )


@bp.post("/categories")
def api_upsert_category():
    data = request.get_json(force=True) or {}
    cid = data.get("id")

    code = (data.get("code") or "").strip().upper()
    name = (data.get("name") or "").strip()

    if not code:
        return _bad("กรุณาใส่รหัสหมวดหมู่ (เช่น SPT)")
    if not name:
        return _bad("กรุณาใส่ชื่อหมวดหมู่")

    q = Category.query.filter(func.lower(Category.code) == code.lower())
    if cid:
        q = q.filter(Category.id != int(cid))
    if q.first():
        return _bad("รหัสหมวดหมู่นี้ถูกใช้แล้ว")

    if cid:
        c = Category.query.get(int(cid))
        if not c:
            return _bad("ไม่พบหมวดหมู่")
    else:
        c = Category(is_active=True)

    c.code = code
    c.name = name
    if "is_active" in data:
        c.is_active = _to_bool(data.get("is_active"))

    db.session.add(c)
    db.session.commit()
    return _ok({"id": c.id, "code": c.code, "name": c.name})


@bp.get("/categories/<int:category_id>")
def api_get_category(category_id: int):
    c = Category.query.get_or_404(category_id)
    return _ok({"category": {"id": c.id, "code": c.code, "name": c.name, "is_active": bool(c.is_active)}})


@bp.post("/brands")
def api_upsert_brand():
    data = request.get_json(force=True) or {}
    bid = data.get("id")
    name = (data.get("name") or "").strip()
    if not name:
        return _bad("กรุณาใส่ชื่อยี่ห้อ")

    q = Brand.query.filter(func.lower(Brand.name) == name.lower())
    if bid:
        q = q.filter(Brand.id != int(bid))
    if q.first():
        return _bad("ยี่ห้อนี้ถูกใช้แล้ว")

    if bid:
        b = Brand.query.get(int(bid))
        if not b:
            return _bad("ไม่พบยี่ห้อ")
    else:
        b = Brand(is_active=True)

    b.name = name
    if "is_active" in data:
        b.is_active = _to_bool(data.get("is_active"))

    db.session.add(b)
    db.session.commit()
    return _ok({"id": b.id, "name": b.name})


@bp.get("/brands/<int:brand_id>")
def api_get_brand(brand_id: int):
    b = Brand.query.get_or_404(brand_id)
    return _ok({"brand": {"id": b.id, "name": b.name, "is_active": bool(b.is_active)}})


@bp.post("/units")
def api_upsert_unit():
    data = request.get_json(force=True) or {}
    uid = data.get("id")
    name = (data.get("name") or "").strip()
    if not name:
        return _bad("กรุณาใส่ชื่อหน่วย")

    q = Unit.query.filter(func.lower(Unit.name) == name.lower())
    if uid:
        q = q.filter(Unit.id != int(uid))
    if q.first():
        return _bad("หน่วยนี้ถูกใช้แล้ว")

    if uid:
        u = Unit.query.get(int(uid))
        if not u:
            return _bad("ไม่พบหน่วย")
    else:
        u = Unit(is_active=True)

    u.name = name
    if "is_active" in data:
        u.is_active = _to_bool(data.get("is_active"))

    db.session.add(u)
    db.session.commit()
    return _ok({"id": u.id, "name": u.name})


@bp.get("/units/<int:unit_id>")
def api_get_unit(unit_id: int):
    u = Unit.query.get_or_404(unit_id)
    return _ok({"unit": {"id": u.id, "name": u.name, "is_active": bool(u.is_active)}})


# =========================================================
# Asset
# =========================================================
@bp.post("/assets/auto_code")
def api_asset_auto_code():
    data = request.get_json(force=True) or {}
    category_id = int(data.get("category_id") or 0)
    d = _to_date((data.get("date") or "").strip()) or date.today()
    if not category_id:
        return _bad("กรุณาเลือกหมวดหมู่")
    try:
        code = _asset_auto_code(category_id, d)
    except Exception as e:
        return _bad(str(e))
    return _ok({"asset_code": code})


@bp.post("/assets")
def api_upsert_asset():
    data = request.get_json(force=True) or {}
    aid = data.get("id")

    category_id = int(data.get("category_id") or 0)
    if not category_id:
        return _bad("กรุณาเลือกหมวดหมู่")

    name = (data.get("name") or "").strip()
    if not name:
        return _bad("กรุณาใส่ชื่ออุปกรณ์")

    purchase_date = _to_date((data.get("purchase_date") or "").strip()) or date.today()

    asset_code = (data.get("asset_code") or "").strip().upper()
    auto = bool(data.get("auto_code"))

    if not asset_code and auto:
        try:
            asset_code = _asset_auto_code(category_id, purchase_date)
        except Exception as e:
            return _bad(str(e))

    if not asset_code:
        return _bad("กรุณาใส่รหัสอุปกรณ์ หรือกด Auto")

    q = Asset.query.filter(func.lower(Asset.asset_code) == asset_code.lower())
    if aid:
        q = q.filter(Asset.id != int(aid))
    if q.first():
        return _bad("รหัสอุปกรณ์นี้ถูกใช้แล้ว")

    if aid:
        a = Asset.query.get(int(aid))
        if not a:
            return _bad("ไม่พบอุปกรณ์")
    else:
        a = Asset(status="พร้อมใช้งาน")

    a.asset_code = asset_code
    a.category_id = category_id
    a.brand_id = int(data.get("brand_id") or 0) or None
    a.unit_id = int(data.get("unit_id") or 0) or None
    a.supplier_id = int(data.get("supplier_id") or 0) or None
    a.name = name
    a.cost = _d(data.get("cost"))
    a.purchase_date = purchase_date

    a.useful_life_days = int(data.get("useful_life_days") or 0) or None
    a.useful_life_months = int(data.get("useful_life_months") or 0) or None
    a.depreciation_method = (data.get("depreciation_method") or "STRAIGHT_LINE").strip().upper() or "STRAIGHT_LINE"

    a.rent_day = _d(data.get("rent_day"))
    a.rent_month = _d(data.get("rent_month"))
    a.rent_year = _d(data.get("rent_year"))

    if data.get("status"):
        a.status = (data.get("status") or "พร้อมใช้งาน").strip()

    _ensure_thai_asset_status(a)

    db.session.add(a)
    db.session.commit()

    return _ok(
        {
            "id": a.id,
            "asset_code": a.asset_code,
            "name": a.name,
            "status": a.status,
            "book_value": str(a.book_value),
            "depreciation_accum": str(a.depreciation_accum),
            "expired_date": a.expired_date.isoformat() if a.expired_date else None,
        }
    )


@bp.get("/assets/<int:asset_id>")
def api_get_asset(asset_id: int):
    a = Asset.query.get_or_404(asset_id)
    _ensure_thai_asset_status(a)
    return _ok(
        {
            "asset": {
                "id": a.id,
                "asset_code": a.asset_code,
                "category_id": a.category_id,
                "brand_id": a.brand_id,
                "unit_id": a.unit_id,
                "supplier_id": a.supplier_id,
                "name": a.name,
                "cost": str(a.cost or 0),
                "purchase_date": a.purchase_date.isoformat() if a.purchase_date else None,
                "useful_life_days": a.useful_life_days,
                "useful_life_months": a.useful_life_months,
                "depreciation_method": a.depreciation_method,
                "rent_day": str(a.rent_day or 0),
                "rent_month": str(a.rent_month or 0),
                "rent_year": str(a.rent_year or 0),
                "status": a.status,
                "main_photo_id": a.main_photo_id,
                "photos": [
                    {"id": p.id, "file_path": p.file_path, "is_main": bool(p.is_main), "sort_order": p.sort_order}
                    for p in sorted(a.photos, key=lambda x: (x.sort_order or 0, x.id))
                ],
                "depreciation_accum": str(a.depreciation_accum),
                "book_value": str(a.book_value),
                "expired_date": a.expired_date.isoformat() if a.expired_date else None,
            }
        }
    )


@bp.post("/assets/<int:asset_id>/photos")
def api_upload_asset_photos(asset_id: int):
    a = Asset.query.get_or_404(asset_id)

    files = request.files.getlist("photos")
    if not files:
        return _bad("ไม่พบไฟล์รูปภาพ")
    upload_root = _uploads_root() / a.asset_code
    upload_root.mkdir(parents=True, exist_ok=True)

    created = []
    for f in files:
        if not f or not getattr(f, "filename", ""):
            continue
        filename = os.path.basename(f.filename)
        ext = os.path.splitext(filename)[1].lower()
        if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
            continue
        safe = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}{ext}"
        abs_path = upload_root / safe
        f.save(abs_path)

        rel = f"uploads/assets/{a.asset_code}/{safe}"
        ph = AssetPhoto(asset_id=a.id, file_path=rel, is_main=False, sort_order=0)
        db.session.add(ph)
        db.session.flush()
        created.append({"id": ph.id, "file_path": ph.file_path})

    db.session.commit()

    return _ok({"photos": created})


@bp.post("/assets/<int:asset_id>/set_main_photo")
def api_asset_set_main_photo(asset_id: int):
    data = request.get_json(force=True) or {}
    photo_id = int(data.get("photo_id") or 0)
    a = Asset.query.get_or_404(asset_id)
    p = AssetPhoto.query.get(photo_id)
    if not p or p.asset_id != a.id:
        return _bad("ไม่พบรูปภาพ")

    AssetPhoto.query.filter(AssetPhoto.asset_id == a.id).update({"is_main": False})
    p.is_main = True
    a.main_photo_id = p.id
    db.session.commit()

    return _ok({"asset_id": a.id, "main_photo_id": a.main_photo_id})


# =========================================================
# Purchase Order (PO)
# =========================================================
@bp.post("/purchase_orders")
def api_upsert_po():
    data = request.get_json(force=True) or {}
    po_id = data.get("id")

    supplier_id = int(data.get("supplier_id") or 0)
    if not supplier_id:
        return _bad("กรุณาเลือกเจ้าหนี้")

    po_date = _to_date((data.get("po_date") or "").strip()) or date.today()
    remark = (data.get("remark") or "").strip() or None

    if po_id:
        po = PurchaseOrder.query.get(int(po_id))
        if not po:
            return _bad("ไม่พบ PO")
        _ensure_thai_po_status(po)
        if (po.status or "") == "ยกเลิก":
            return _bad("PO ถูกยกเลิกแล้ว ไม่อนุญาตให้แก้ไข")
    else:
        po = PurchaseOrder(po_no=_po_no(po_date), status="ร่าง")

    po.po_date = po_date
    po.supplier_id = supplier_id
    po.remark = remark

    if data.get("status"):
        po.status = (data.get("status") or "ร่าง").strip()
        _ensure_thai_po_status(po)

    lines = data.get("lines") or []
    po.lines = []
    for ln in lines:
        item_name = (ln.get("item_name") or "").strip()
        if not item_name:
            continue
        qty = _d(ln.get("qty"))
        unit_cost = _d(ln.get("unit_cost"))
        line_total = qty * unit_cost

        pol = PurchaseOrderLine(
            item_name=item_name,
            category_id=int(ln.get("category_id") or 0) or None,
            unit_id=int(ln.get("unit_id") or 0) or None,
            qty=qty,
            unit_cost=unit_cost,
            line_total=line_total,
        )
        po.lines.append(pol)

    db.session.add(po)
    db.session.commit()

    return _ok({"id": po.id, "po_no": po.po_no, "status": po.status})


@bp.get("/purchase_orders/<int:po_id>")
def api_get_po(po_id: int):
    po = PurchaseOrder.query.get_or_404(po_id)
    _ensure_thai_po_status(po)
    return _ok(
        {
            "po": {
                "id": po.id,
                "po_no": po.po_no,
                "po_date": po.po_date.isoformat() if po.po_date else None,
                "supplier_id": po.supplier_id,
                "remark": po.remark,
                "status": po.status,
                "lines": [
                    {
                        "id": ln.id,
                        "item_name": ln.item_name,
                        "category_id": ln.category_id,
                        "unit_id": ln.unit_id,
                        "qty": str(ln.qty or 0),
                        "qty_received_total": str(getattr(ln, "qty_received_total", 0) or 0),
                        "receive_status": (getattr(ln, "receive_status", "") or "OPEN"),
                        "unit_cost": str(ln.unit_cost or 0),
                        "line_total": str(ln.line_total or 0),
                    }
                    for ln in po.lines
                ],
            }
        }
    )


@bp.post("/purchase_orders/<int:po_id>/approve")
def api_po_approve(po_id: int):
    po = PurchaseOrder.query.get_or_404(po_id)
    _ensure_thai_po_status(po)

    if po.status == "ยกเลิก":
        return _bad("PO ถูกยกเลิกแล้ว")
    if po.status in ("รับครบ",):
        return _bad("PO รับครบแล้ว ไม่ต้องอนุมัติซ้ำ")

    po.status = "อนุมัติ"
    db.session.commit()
    return _ok({"id": po.id, "status": po.status})


@bp.post("/purchase_orders/<int:po_id>/cancel")
def api_po_cancel(po_id: int):
    po = PurchaseOrder.query.get_or_404(po_id)
    po.status = "ยกเลิก"
    db.session.commit()
    return _ok({"id": po.id, "status": po.status})


# =========================================================
# GRN
# =========================================================
@bp.post("/grns/prefill_from_po")
def api_prefill_grn_from_po():
    data = request.get_json(force=True) or {}
    po_id = int(data.get("po_id") or 0)
    if not po_id:
        return _bad("กรุณาเลือก PO")

    po = PurchaseOrder.query.get_or_404(po_id)
    _ensure_thai_po_status(po)

    if po.status not in ("อนุมัติ", "รับบางส่วน"):
        return _bad("ต้องเป็น PO สถานะอนุมัติ/รับบางส่วน เท่านั้น")

    return _ok(
        {
            "po": {"id": po.id, "po_no": po.po_no, "supplier_id": po.supplier_id},
            "lines": [
                {
                    "po_line_id": ln.id,
                    "item_name": ln.item_name,
                    "category_id": ln.category_id,
                    "unit_id": ln.unit_id,
                    "qty_received": str(max(Decimal("0.00"), _d(ln.qty) - _d(getattr(ln, "qty_received_total", 0)))),
                    "unit_cost": str(ln.unit_cost or 0),
                }
                for ln in po.lines
            ],
        }
    )


@bp.post("/grns")
def api_create_grn():
    data = request.get_json(force=True) or {}
    grn_id = data.get("id")

    mode = (data.get("mode") or "").strip().lower() or None  # "po" / "cash"
    grn_date = _to_date((data.get("grn_date") or "").strip()) or date.today()
    supplier_id = int(data.get("supplier_id") or 0)
    if not supplier_id:
        return _bad("กรุณาเลือกเจ้าหนี้")

    po_id = int(data.get("po_id") or 0) or None
    remark = (data.get("remark") or "").strip() or None

    if grn_id:
        grn = GRN.query.get(int(grn_id))
        if not grn:
            return _bad("ไม่พบ GRN")

        _ensure_thai_grn_status(grn)

        try:
            _assert_grn_editable(grn)
        except Exception as e:
            return _bad(str(e))

        StockMove.query.filter(StockMove.ref_type == "GRN", StockMove.ref_no == grn.grn_no).delete(
            synchronize_session=False
        )

        grn.lines = []
    else:
        grn = GRN(grn_no=_grn_no(grn_date), status="ร่าง")

    grn.grn_date = grn_date
    grn.supplier_id = supplier_id
    grn.remark = remark

    if data.get("status"):
        grn.status = (data.get("status") or "ร่าง").strip()
    _ensure_thai_grn_status(grn)

    lines = data.get("lines") or []
    built_lines: list[GRNLine] = []

    for ln in lines:
        item_name = (ln.get("item_name") or "").strip()
        if not item_name:
            continue

        qty = _d(ln.get("qty_received"))
        unit_cost = _d(ln.get("unit_cost"))
        po_line_id = int(ln.get("po_line_id") or 0) or None

        gl = GRNLine(
            po_line_id=po_line_id,
            item_name=item_name,
            category_id=int(ln.get("category_id") or 0) or None,
            unit_id=int(ln.get("unit_id") or 0) or None,
            qty_received=qty,
            unit_cost=unit_cost,
        )
        built_lines.append(gl)

    if len(built_lines) == 0:
        return _bad("กรุณาเพิ่มรายการรับเข้าอย่างน้อย 1 รายการ")

    if not mode:
        mode = "po" if po_id else "cash"

    if mode == "po":
        if not po_id:
            return _bad("โหมดรับจาก PO ต้องระบุ PO (po_id ห้ามว่าง)")

        po = PurchaseOrder.query.get(po_id)
        if not po:
            return _bad("ไม่พบ PO")
        _ensure_thai_po_status(po)

        if po.status not in ("อนุมัติ", "รับบางส่วน", "รับครบ"):
            return _bad("ต้องเป็น PO สถานะอนุมัติ/รับบางส่วน เท่านั้น")
        if po.status == "ยกเลิก":
            return _bad("PO ถูกยกเลิกแล้ว")
        if int(po.supplier_id) != int(supplier_id):
            return _bad("เจ้าหนี้ใน GRN ต้องตรงกับเจ้าหนี้ของ PO")

        for gl in built_lines:
            if not gl.po_line_id:
                return _bad("โหมดรับจาก PO ต้องอ้างอิงรายการจาก PO (po_line_id ห้ามว่าง)")
            pol = PurchaseOrderLine.query.get(gl.po_line_id)
            if not pol:
                return _bad(f"ไม่พบรายการ PO line id={gl.po_line_id}")
            if int(pol.po_id) != int(po_id):
                return _bad("พบรายการรับเข้าที่ไม่ใช่ของ PO ที่เลือก")

            q = _d(pol.qty or 0)
            received = _d(getattr(pol, "qty_received_total", 0) or 0)
            remain = q - received
            if remain < 0:
                remain = Decimal("0")
            if _d(gl.qty_received) > remain:
                return _bad(f"รับเกินยอดคงเหลือ: {pol.item_name} (คงเหลือ {remain})")
    else:
        po_id = None
        for gl in built_lines:
            gl.po_line_id = None

    grn.po_id = po_id

    for gl in built_lines:
        grn.lines.append(gl)

    if not data.get("status"):
        grn.status = "บันทึกแล้ว"
    _ensure_thai_grn_status(grn)

    db.session.add(grn)
    db.session.flush()

    now = datetime.utcnow()
    for ln in grn.lines:
        if not ln.qty_received or _d(ln.qty_received) <= 0:
            continue

        sm = StockMove(
            move_date=now,
            ref_type="GRN",
            ref_no=grn.grn_no,
            asset_id=None,
            category_id=ln.category_id,
            qty_in=_d(ln.qty_received),
            qty_out=_d(0),
            note=f"รับสินค้า: {ln.item_name}",
            created_at=now,
        )
        db.session.add(sm)

    if grn.po_id:
        _recalc_po_received(grn.po_id)

    db.session.commit()

    return _ok({"id": grn.id, "grn_no": grn.grn_no, "po_id": grn.po_id, "status": grn.status})


@bp.get("/grns/<int:grn_id>")
def api_get_grn(grn_id: int):
    grn = GRN.query.get_or_404(grn_id)
    _ensure_thai_grn_status(grn)
    return _ok(
        {
            "grn": {
                "id": grn.id,
                "grn_no": grn.grn_no,
                "grn_date": grn.grn_date.isoformat() if grn.grn_date else None,
                "supplier_id": grn.supplier_id,
                "po_id": grn.po_id,
                "remark": grn.remark,
                "status": (grn.status or ""),
                "assets_generated_at": (grn.assets_generated_at.isoformat() if grn.assets_generated_at else None),
                "lines": [
                    {
                        "id": ln.id,
                        "po_line_id": ln.po_line_id,
                        "item_name": ln.item_name,
                        "category_id": ln.category_id,
                        "unit_id": ln.unit_id,
                        "qty_received": str(ln.qty_received or 0),
                        "unit_cost": str(ln.unit_cost or 0),
                    }
                    for ln in grn.lines
                ],
            }
        }
    )


@bp.post("/grns/<int:grn_id>/generate_assets")
def api_generate_assets_from_grn(grn_id: int):
    """
    Generate Asset records from GRN lines (qty_received).
    - validate required_count vs items
    - prevent double-generate
    - create StockMove ref_type=ASSET_GEN (trace only, qty=0) to avoid double-counting inventory
    - update GRN.status -> "สร้างอุปกรณ์แล้ว" and lock further edits
    """
    data = request.get_json(force=True) or {}
    items = data.get("items") or []

    grn = GRN.query.get_or_404(grn_id)
    _ensure_thai_grn_status(grn)

    if grn.assets_generated_at or (grn.status == "สร้างอุปกรณ์แล้ว"):
        return _bad("GRN นี้ถูก Generate Assets แล้ว (ห้ามทำซ้ำ)")

    required = 0
    for ln in grn.lines:
        if not ln.category_id:
            continue
        q = int(float(ln.qty_received or 0))
        if q > 0:
            required += q

    if required <= 0:
        return _bad("ไม่พบจำนวนรับที่สามารถ Generate Assets ได้ (ต้องมี qty_received > 0 และเลือกหมวดหมู่)")

    if items and len(items) != required:
        return _bad(f"จำนวนรายการที่ส่งมา ({len(items)}) ไม่ตรงกับจำนวนที่ต้องสร้าง ({required})")

    created = []
    idx = 0
    now = datetime.utcnow()

    for ln in grn.lines:
        qty = int(float(ln.qty_received or 0))
        if qty <= 0:
            continue
        if not ln.category_id:
            continue

        for _i in range(qty):
            override = items[idx] if items else {}
            idx += 1

            purchase_date = grn.grn_date or date.today()

            raw_code = (override.get("asset_code") or "").strip().upper()
            if raw_code:
                asset_code = raw_code
            else:
                try:
                    asset_code = _asset_auto_code(int(ln.category_id), purchase_date)
                except Exception as e:
                    return _bad(str(e))

            if Asset.query.filter(func.lower(Asset.asset_code) == asset_code.lower()).first():
                return _bad(f"รหัสอุปกรณ์ซ้ำ: {asset_code}")

            name = (override.get("name") or ln.item_name or "").strip() or ln.item_name

            if "cost" in override and override.get("cost") not in (None, ""):
                cost = _d(override.get("cost"))
            else:
                cost = _d(ln.unit_cost)

            a = Asset(
                asset_code=asset_code,
                category_id=int(ln.category_id),
                brand_id=int(override.get("brand_id") or 0) or None,
                unit_id=int(override.get("unit_id") or 0) or ln.unit_id,
                supplier_id=grn.supplier_id,
                name=name,
                cost=cost,
                purchase_date=purchase_date,
                useful_life_days=int(override.get("useful_life_days") or 0) or None,
                useful_life_months=int(override.get("useful_life_months") or 0) or None,
                depreciation_method="STRAIGHT_LINE",
                rent_day=_d(override.get("rent_day")),
                rent_month=_d(override.get("rent_month")),
                rent_year=_d(override.get("rent_year")),
                status="พร้อมใช้งาน",
            )
            _ensure_thai_asset_status(a)

            db.session.add(a)
            db.session.flush()

            sm = StockMove(
                move_date=now,
                ref_type="ASSET_GEN",
                ref_no=grn.grn_no,
                asset_id=a.id,
                category_id=a.category_id,
                qty_in=_d(0),
                qty_out=_d(0),
                note="Generate Asset from GRN",
                created_at=now,
            )
            db.session.add(sm)

            created.append({"id": a.id, "asset_code": a.asset_code, "name": a.name})

    grn.assets_generated_at = now
    grn.status = "สร้างอุปกรณ์แล้ว"

    db.session.commit()
    return _ok({"created": created})


# =========================================================
# Adjust Stock (asset-level)
# =========================================================
@bp.post("/adjust")
def api_adjust_assets():
    data = request.get_json(force=True) or {}
    asset_ids = data.get("asset_ids") or []
    reason = (data.get("reason") or "").strip()
    note = (data.get("note") or "").strip() or None

    if not asset_ids:
        return _bad("กรุณาเลือกอุปกรณ์อย่างน้อย 1 รายการ")

    allowed = {"พร้อมใช้งาน", "ซ่อม", "สูญหาย", "จำหน่ายออก"}
    if reason not in allowed:
        return _bad("เหตุผลไม่ถูกต้อง")

    now = datetime.utcnow()
    for aid in asset_ids:
        a = Asset.query.get(int(aid))
        if not a:
            continue

        _ensure_thai_asset_status(a)
        old = a.status

        a.status = reason
        _ensure_thai_asset_status(a)

        sm = StockMove(
            move_date=now,
            ref_type="ADJ",
            ref_no=None,
            asset_id=a.id,
            category_id=a.category_id,
            qty_in=_d(1) if (old in ["สูญหาย", "จำหน่ายออก"] and reason == "พร้อมใช้งาน") else _d(0),
            qty_out=_d(1) if (reason in ["สูญหาย", "จำหน่ายออก"]) else _d(0),
            note=(note or f"ปรับสถานะ: {old} -> {reason}"),
            created_at=now,
        )
        db.session.add(sm)

    db.session.commit()
    return _ok({"updated": len(asset_ids)})