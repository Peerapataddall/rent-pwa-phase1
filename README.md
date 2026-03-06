# RENT_PWA · Phase 1 (One-page QT)

✅ Rental quotation only  
✅ Doc No: QT + YYMM + running (QT690200001)  
✅ Pricing: price/day × days × qty  
✅ VAT modes: EXCLUDED (default), INCLUDED, NONE  
✅ WHT: subtotal(before VAT) × %  
✅ Net: total incl VAT - WHT  
✅ Deposit: per-line + total (NOT included in net)

---

## Run (Windows)

```bash
cd RENT_PWA_PHASE1
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt

copy .env.example .env
flask db init
flask db migrate -m "init phase1"
flask db upgrade
flask run
```

Open:
- http://127.0.0.1:5000/
- http://127.0.0.1:5000/quotes

> Note: This zip does not include `migrations/`. Create them locally with the commands above.
