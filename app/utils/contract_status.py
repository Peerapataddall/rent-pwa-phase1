from __future__ import annotations

from flask import flash, redirect, url_for

from app import db
from app.models import RentalContract


LOCKED_STATUSES = ("ยกเลิกสัญญา", "ปิดสัญญา")


def guard_contract_not_locked(c: RentalContract):
    """
    ถ้าสัญญาอยู่ในสถานะที่ล็อกแล้ว (ยกเลิก/ปิด) จะไม่อนุญาตให้ทำรายการต่อ
    คืนค่า redirect response ถ้าถูกล็อก, ไม่งั้นคืน None
    """
    if not c:
        return None

    st = (c.status or "").strip()
    if st in LOCKED_STATUSES:
        flash("สัญญาถูกล็อกแล้ว (ยกเลิก/ปิดสัญญา) ไม่สามารถทำรายการต่อได้", "warning")
        return redirect(url_for("pages.contract_view", contract_id=c.id))

    return None


def ensure_contract_running_status(c: RentalContract) -> None:
    """
    นโยบาย: "สัญญาไม่มีสถานะร่าง"
    - ถ้าเจอค่าสถานะเดิมเป็น 'ร่าง' ให้ normalize เป็น 'สัญญากำลังดำเนินการ'
    """
    if not c:
        return
    st = (c.status or "").strip()
    if st == "ร่าง" or st == "":
        c.status = "สัญญากำลังดำเนินการ"
        db.session.commit()


def auto_update_contract_status(c: RentalContract) -> None:
    """
    สถานะสัญญา:
    - ถ้าค้างชำระ = 0 (ทุกงวด 'ชำระแล้ว') => ปิดสัญญา
    - ไม่งั้น => สัญญากำลังดำเนินการ
    - ถ้า 'ยกเลิกสัญญา' ให้คงไว้ ไม่เปลี่ยน
    """
    if not c:
        return

    st = (c.status or "").strip()
    if st == "ยกเลิกสัญญา":
        return

    # normalize draft just in case
    if st == "ร่าง" or st == "":
        c.status = "สัญญากำลังดำเนินการ"
        db.session.commit()
        st = c.status

    ins = list(c.installments or [])
    if not ins:
        # ไม่มีงวดก็ถือว่ายังดำเนินการ
        if st != "สัญญากำลังดำเนินการ":
            c.status = "สัญญากำลังดำเนินการ"
            db.session.commit()
        return

    all_paid = all((i.status or "") == "ชำระแล้ว" for i in ins)

    new_status = "ปิดสัญญา" if all_paid else "สัญญากำลังดำเนินการ"
    if st != new_status:
        c.status = new_status
        db.session.commit()