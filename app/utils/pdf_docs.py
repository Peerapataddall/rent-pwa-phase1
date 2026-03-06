# app/utils/pdf_docs.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
from pathlib import Path
from typing import Any, Iterable

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

PAGE_W, PAGE_H = A4


@dataclass
class PdfResult:
    filename: str
    content: bytes


# =========================================================
# Format helpers
# =========================================================
def _d(x: Any) -> Decimal:
    try:
        return Decimal(str(x or 0))
    except Exception:
        return Decimal("0")


def _fmt_money(x: Any) -> str:
    d = _d(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{d:,.2f}"


def _fmt_date(d: date | None) -> str:
    if not d:
        return "-"
    try:
        return d.strftime("%d/%m/%Y")
    except Exception:
        return str(d)


def _get_thai_font_name() -> str:
    """
    Try register Kanit Light from:
    app/static/fonts/Kanit-Light.ttf

    If not found, fallback to Helvetica.
    """
    try:
        app_dir = Path(__file__).resolve().parents[1]  # .../app
        font_path = app_dir / "static" / "fonts" / "Kanit-Light.ttf"
        if font_path.exists():
            font_name = "KanitLight"
            if font_name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(font_name, str(font_path)))
            return font_name
    except Exception:
        pass
    return "Helvetica"


# =========================================================
# Drawing primitives
# =========================================================
def _draw_hr(c: Canvas, y: float) -> float:
    c.setLineWidth(0.6)
    c.line(15 * mm, y, PAGE_W - 15 * mm, y)
    return y - 6 * mm


def _draw_kv(
    c: Canvas,
    x: float,
    y: float,
    label: str,
    value: str,
    font: str,
    *,
    size_label: int = 10,
    size_value: int = 12,
) -> float:
    c.setFont(font, size_label)
    c.drawString(x, y, label)

    c.setFont(font, size_value)
    c.drawString(x, y - 5 * mm, value)
    return y - 12 * mm


def _wrap_text(text: str, *, max_chars: int) -> list[str]:
    text = (text or "").strip()
    if not text:
        return ["-"]
    if max_chars <= 5:
        return [text[:max_chars]]

    out: list[str] = []
    for raw_line in text.splitlines():
        s = raw_line.strip()
        if not s:
            out.append("")
            continue
        while len(s) > max_chars:
            out.append(s[:max_chars])
            s = s[max_chars:]
        out.append(s)
    return out or ["-"]


def _render_common_header(
    c: Canvas,
    *,
    title: str,
    badge_text: str,
    doc_no: str,
    doc_date: date | None,
    installment_no: int | None,
    font: str,
) -> float:
    y = PAGE_H - 18 * mm

    c.setFont(font, 18)
    c.drawString(15 * mm, y, title)

    # badge (top-right)
    if badge_text:
        c.setFont(font, 11)
        w = c.stringWidth(badge_text, font, 11)
        pad_x = 4 * mm
        pad_y = 2.5 * mm

        bx2 = PAGE_W - 15 * mm
        bx1 = bx2 - (w + 2 * pad_x)
        by1 = y - 1 * mm
        by2 = by1 + (8 * mm)

        # black badge background (เหมือนภาพตัวอย่าง)
        c.setFillColorRGB(0, 0, 0)
        c.roundRect(bx1, by1, bx2 - bx1, by2 - by1, 3 * mm, stroke=0, fill=1)

        c.setFillColorRGB(1, 1, 1)
        c.drawString(bx1 + pad_x, by1 + pad_y, badge_text)

        c.setFillColorRGB(0, 0, 0)

    y -= 10 * mm
    c.setFont(font, 11)
    c.drawString(15 * mm, y, f"เลขที่เอกสาร: {doc_no}  ·  วันที่เอกสาร: {_fmt_date(doc_date)}")

    if installment_no is not None:
        c.drawRightString(PAGE_W - 15 * mm, y, f"งวดที่ {installment_no}")

    y -= 6 * mm
    y = _draw_hr(c, y)
    return y


def _render_total_box(c: Canvas, *, y: float, label: str, amount: Any, font: str) -> float:
    box_w = 70 * mm
    box_h = 22 * mm
    x2 = PAGE_W - 15 * mm
    x1 = x2 - box_w

    c.setLineWidth(0.8)
    c.roundRect(x1, y - box_h, box_w, box_h, 3 * mm, stroke=1, fill=0)

    c.setFont(font, 11)
    c.drawString(x1 + 4 * mm, y - 7 * mm, label)

    c.setFont(font, 18)
    c.drawString(x1 + 4 * mm, y - 16 * mm, _fmt_money(amount))

    c.setFont(font, 11)
    c.drawRightString(x2 - 4 * mm, y - 16 * mm, "บาท")
    return y - (box_h + 6 * mm)


def _render_signatures(c: Canvas, *, y: float, left_title: str, right_title: str, font: str) -> float:
    x0 = 15 * mm
    x1 = PAGE_W - 15 * mm
    mid = (x0 + x1) / 2

    c.setFont(font, 11)
    c.drawString(x0, y, left_title)
    c.drawRightString(x1, y, right_title)

    y -= 24 * mm
    c.setLineWidth(0.5)
    c.line(x0, y, mid - 10 * mm, y)
    c.line(mid + 10 * mm, y, x1, y)

    y -= 12 * mm
    c.setFont(font, 11)
    c.drawString(x0, y, "วันที่")
    c.drawRightString(mid - 10 * mm, y, "วันที่")

    c.drawString(mid + 10 * mm, y, "วันที่")
    c.drawRightString(x1, y, "วันที่")
    return y - 10 * mm


# =========================================================
# Quote-like items table (เหมือนหน้า print / ใบเสนอราคา)
# =========================================================
def _alloc_installment_amount(
    *,
    lines: Iterable[Any],
    doc_amount: Decimal,
) -> list[Decimal]:
    """
    Allocate doc_amount across quote lines by proportion of each line_total (or qty*days*price).
    Round to 2 decimals and fix the last line to ensure total == doc_amount.
    """
    base_totals: list[Decimal] = []
    for ln in lines:
        qty = _d(getattr(ln, "qty", 0))
        days = _d(getattr(ln, "days", 0))
        price = _d(getattr(ln, "price", 0))
        calc_total = qty * days * price
        line_total = _d(getattr(ln, "line_total", 0))
        base = line_total if line_total != 0 else calc_total
        base_totals.append(base)

    s = sum(base_totals) if base_totals else Decimal("0")
    if s == 0 or doc_amount == 0 or not base_totals:
        return [Decimal("0.00") for _ in base_totals]

    allocs: list[Decimal] = []
    running = Decimal("0.00")
    for i, base in enumerate(base_totals):
        if i == len(base_totals) - 1:
            a = (doc_amount - running).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            a = ((base / s) * doc_amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            running += a
        allocs.append(a)
    return allocs


def _render_items_table(
    c: Canvas,
    *,
    y: float,
    qt: Any,
    doc_amount: Any,
    font: str,
    empty_text: str = "ไม่พบรายการสินค้าในใบเสนอราคา (QT)",
) -> float:
    """
    Draw table:
    สินค้า | รายละเอียด | จำนวน | วัน | ราคา/วัน | รวม
    """
    x0 = 15 * mm
    x1 = PAGE_W - 15 * mm
    w = x1 - x0

    # column widths (approx align with HTML)
    col_product = 33 * mm
    col_detail = 65 * mm
    col_qty = 20 * mm
    col_days = 16 * mm
    col_price = 24 * mm
    col_total = w - (col_product + col_detail + col_qty + col_days + col_price)

    xs = [
        x0,
        x0 + col_product,
        x0 + col_product + col_detail,
        x0 + col_product + col_detail + col_qty,
        x0 + col_product + col_detail + col_qty + col_days,
        x0 + col_product + col_detail + col_qty + col_days + col_price,
        x1,
    ]

    header_h = 10 * mm
    row_pad_y = 2 * mm

    # header border
    c.setLineWidth(0.6)
    c.rect(x0, y - header_h, w, header_h, stroke=1, fill=0)

    c.setFont(font, 11)
    c.drawString(xs[0] + 2 * mm, y - 7 * mm, "สินค้า")
    c.drawString(xs[1] + 2 * mm, y - 7 * mm, "รายละเอียด")
    c.drawRightString(xs[3] - 2 * mm, y - 7 * mm, "จำนวน")
    c.drawRightString(xs[4] - 2 * mm, y - 7 * mm, "วัน")
    c.drawRightString(xs[5] - 2 * mm, y - 7 * mm, "ราคา/วัน")
    c.drawRightString(xs[6] - 2 * mm, y - 7 * mm, "รวม")

    y -= header_h

    lines = list(getattr(qt, "lines", []) or [])
    if not lines:
        # one empty row
        row_h = 14 * mm
        c.setLineWidth(0.3)
        c.rect(x0, y - row_h, w, row_h, stroke=1, fill=0)
        c.setFont(font, 11)
        c.drawCentredString((x0 + x1) / 2, y - 9 * mm, empty_text)
        return y - row_h - 6 * mm

    doc_amt = _d(doc_amount)
    allocs = _alloc_installment_amount(lines=lines, doc_amount=doc_amt)

    # grid verticals
    def _draw_row_grid(y_top: float, row_h: float) -> None:
        c.setLineWidth(0.3)
        c.rect(x0, y_top - row_h, w, row_h, stroke=1, fill=0)
        for x in xs[1:-1]:
            c.line(x, y_top, x, y_top - row_h)

    for ln, alloc in zip(lines, allocs):
        prod = getattr(ln, "product", None)
        prod_name = (getattr(prod, "name", None) or "-") if prod else "-"
        prod_spec = (getattr(prod, "spec", None) or "-") if prod else "-"

        qty = _d(getattr(ln, "qty", 0))
        days = getattr(ln, "days", 0) or 0
        price = _d(getattr(ln, "price", 0))

        # wrap spec into cell
        # estimate chars based on cell width; Kanit ~ 0.55em per char
        max_chars = max(12, int((col_detail / mm) * 1.7))  # rough
        spec_lines = _wrap_text(str(prod_spec), max_chars=max_chars)

        # row height depends on spec lines
        line_h = 5 * mm
        row_h = max(10 * mm, (len(spec_lines) * line_h) + 2 * row_pad_y)

        # page break if needed
        if y - row_h < 20 * mm:
            c.showPage()
            c.setFont(font, 11)
            y = PAGE_H - 20 * mm

        _draw_row_grid(y, row_h)

        # product
        c.setFont(font, 11)
        c.drawString(xs[0] + 2 * mm, y - 7 * mm, str(prod_name))

        # spec (multi-line)
        c.setFont(font, 10)
        ty = y - 6 * mm
        for s in spec_lines[:5]:  # cap lines to keep layout stable
            c.drawString(xs[1] + 2 * mm, ty, s)
            ty -= line_h

        # numbers
        c.setFont(font, 11)
        c.drawRightString(xs[3] - 2 * mm, y - 7 * mm, _fmt_money(qty))
        c.drawRightString(xs[4] - 2 * mm, y - 7 * mm, str(days))
        c.drawRightString(xs[5] - 2 * mm, y - 7 * mm, _fmt_money(price))
        c.drawRightString(xs[6] - 2 * mm, y - 7 * mm, _fmt_money(alloc))

        y -= row_h

    return y - 6 * mm


# =========================================================
# Unified builder
# =========================================================
def _doc_conf(kind: str, obj: Any) -> dict[str, Any]:
    kind = (kind or "").upper().strip()

    if kind == "BL":
        title = "ใบวางบิล / ใบแจ้งหนี้"
        status = (getattr(obj, "status", "") or "").strip()
        badge = "วางบิลแล้ว" if status == "วางบิลแล้ว" else "ยังไม่วางบิล"
        note = "หมายเหตุ: เอกสารนี้ออกตามยอดงวดในระบบ"
        sign_left = "ผู้จัดทำ"
        sign_right = "ผู้รับเอกสาร"
        left_fields = ("tax_id", "phone")
        # label in total box
        total_label = "รวมทั้งสิ้น"
    elif kind == "TX":
        title = "ใบกำกับภาษี"
        status = (getattr(obj, "status", "") or "").strip()
        badge = "อนุมัติแล้ว" if status == "อนุมัติแล้ว" else "ยังไม่อนุมัติ"
        note = "หมายเหตุ: ใบกำกับภาษีนี้ออกตามยอดงวดในระบบ"
        sign_left = "ผู้มีอำนาจลงนาม"
        sign_right = "ผู้รับสินค้า/บริการ"
        left_fields = ("tax_id", "address")
        total_label = "รวมทั้งสิ้น"
    elif kind == "RC":
        title = "ใบเสร็จรับเงิน"
        status = (getattr(obj, "status", "") or "").strip()
        badge = "รับเงินแล้ว" if status == "รับเงินแล้ว" else "ยังไม่รับเงิน"
        sign_left = "ผู้รับเงิน"
        sign_right = "ผู้ชำระเงิน"
        left_fields = ("phone", "address")
        total_label = "รวมทั้งสิ้น"

        # receipt note
        ins = getattr(obj, "installment", None)
        paid_note = ""
        try:
            paid_note = (getattr(ins, "paid_note", None) or "").strip() if ins else ""
        except Exception:
            paid_note = ""
        if not paid_note:
            paid_note = f"รับเงินผ่าน RC {getattr(obj, 'doc_no', '')}".strip()
        note = f"หมายเหตุการชำระ: {paid_note}"
    else:
        # safe fallback
        title = "เอกสาร"
        badge = ""
        note = ""
        sign_left = "ผู้จัดทำ"
        sign_right = "ผู้รับเอกสาร"
        left_fields = ("tax_id", "phone")
        total_label = "รวมทั้งสิ้น"

    return {
        "title": title,
        "badge": badge,
        "note": note,
        "sign_left": sign_left,
        "sign_right": sign_right,
        "left_fields": left_fields,
        "total_label": total_label,
    }


def build_installment_doc_pdf(kind: str, obj: Any) -> PdfResult:
    """
    Build BL/TX/RC PDF with a single unified layout that matches print templates:
    - header + badge + installment no
    - customer block + project/ref block
    - quote-like items table (สินค้า/รายละเอียด/จำนวน/วัน/ราคา/วัน/รวม)
    - note + total box + signatures
    """
    font = _get_thai_font_name()
    buf = BytesIO()
    c = Canvas(buf, pagesize=A4)
    c.setTitle(str(getattr(obj, "doc_no", kind)))

    conf = _doc_conf(kind, obj)

    ins = getattr(obj, "installment", None)
    ct = getattr(ins, "contract", None) if ins else None
    qt = getattr(ct, "quote", None) if ct else None
    cust = getattr(qt, "customer", None) if qt else None

    y = _render_common_header(
        c,
        title=conf["title"],
        badge_text=conf["badge"],
        doc_no=str(getattr(obj, "doc_no", "-")),
        doc_date=getattr(obj, "doc_date", None),
        installment_no=getattr(ins, "seq", None) if ins else None,
        font=font,
    )

    # left block (customer)
    y_left = y
    y_left = _draw_kv(c, 15 * mm, y_left, "ลูกค้า", (getattr(cust, "name", None) or "-") if cust else "-", font)

    lf = conf["left_fields"]
    if "tax_id" in lf:
        y_left = _draw_kv(
            c,
            15 * mm,
            y_left,
            "เลขผู้เสียภาษี",
            (getattr(cust, "tax_id", None) or "-") if (cust and getattr(cust, "tax_id", None)) else "-",
            font,
        )
    if "phone" in lf:
        y_left = _draw_kv(
            c,
            15 * mm,
            y_left,
            "โทร",
            (getattr(cust, "phone", None) or "-") if (cust and getattr(cust, "phone", None)) else "-",
            font,
        )
    if "address" in lf:
        y_left = _draw_kv(
            c,
            15 * mm,
            y_left,
            "ที่อยู่",
            (getattr(cust, "address", None) or "-") if (cust and getattr(cust, "address", None)) else "-",
            font,
        )

    # right block (project/ref)
    y_right = y
    project = "-"
    if ct and getattr(ct, "project_site", None):
        project = getattr(ct, "project_site", None) or "-"
    elif qt and getattr(qt, "project_site", None):
        project = getattr(qt, "project_site", None) or "-"

    y_right = _draw_kv(c, PAGE_W / 2 + 5 * mm, y_right, "โครงการ / หน้างาน", str(project), font)
    y_right = _draw_kv(c, PAGE_W / 2 + 5 * mm, y_right, "อ้างอิง QT", (getattr(qt, "doc_no", None) or "-") if qt else "-", font)
    y_right = _draw_kv(c, PAGE_W / 2 + 5 * mm, y_right, "อ้างอิงสัญญา (CT)", (getattr(ct, "doc_no", None) or "-") if ct else "-", font)

    y = min(y_left, y_right) - 2 * mm
    y = _draw_hr(c, y)

    # items table (quote-like)
    y = _render_items_table(c, y=y, qt=qt, doc_amount=getattr(obj, "amount", 0), font=font)

    # note
    if conf["note"]:
        c.setFont(font, 10)
        c.drawString(15 * mm, y, conf["note"])
        y -= 8 * mm

    # total
    y = _render_total_box(c, y=y, label=conf["total_label"], amount=getattr(obj, "amount", 0), font=font)

    y -= 10 * mm
    _render_signatures(c, y=y, left_title=conf["sign_left"], right_title=conf["sign_right"], font=font)

    c.showPage()
    c.save()

    return PdfResult(filename=f"{getattr(obj, 'doc_no', kind)}.pdf", content=buf.getvalue())


# =========================================================
# Backward-compatible wrappers (used by pages.py routes)
# =========================================================
def build_billing_pdf(b: Any) -> PdfResult:
    return build_installment_doc_pdf("BL", b)


def build_tax_pdf(t: Any) -> PdfResult:
    return build_installment_doc_pdf("TX", t)


def build_receipt_pdf(r: Any) -> PdfResult:
    return build_installment_doc_pdf("RC", r)