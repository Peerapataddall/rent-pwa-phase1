// app/static/app.js
// =========================================================
// Global helpers
// =========================================================
async function fetchJSON(url, opts = {}) {
  const options = Object.assign(
    {
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
    },
    opts
  );
  const res = await fetch(url, options);
  const data = await res.json().catch(() => ({}));
  if (!res.ok || data.ok === false) {
    const msg = data.message || `Request failed: ${res.status}`;
    throw new Error(msg);
  }
  return data;
}

function qs(id) {
  return document.getElementById(id);
}

function setErr(id, msg) {
  const el = qs(id);
  if (el) el.textContent = msg || "";
}

function money(x) {
  const n = Number(x || 0);
  if (Number.isNaN(n)) return "0.00";
  return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function num(x) {
  const n = Number(x || 0);
  return Number.isNaN(n) ? 0 : n;
}

function showModal(id) {
  const el = qs(id);
  if (!el) return;
  const m = bootstrap.Modal.getOrCreateInstance(el);
  m.show();
}

function hideModal(id) {
  const el = qs(id);
  if (!el) return;
  const m = bootstrap.Modal.getOrCreateInstance(el);
  m.hide();
}

async function refreshMasters() {
  try {
    const data = await fetchJSON("/api/masters", { method: "GET", headers: {} });
    window._masters = data;
  } catch (e) {
    // silent
  }
}

// ✅ รองรับ Choices.js (searchable select) ถ้าเปิดใช้ใน base.html
function addOptionToSelect(selectId, id, label) {
  if (!selectId) return;
  const sel = qs(selectId);
  if (!sel) return;

  for (const opt of sel.options) {
    if (String(opt.value) === String(id)) {
      sel.value = String(id);
      if (typeof window.refreshSearchSelect === "function") window.refreshSearchSelect(sel);
      return;
    }
  }

  const opt = document.createElement("option");
  opt.value = String(id);
  opt.textContent = label;
  sel.appendChild(opt);
  sel.value = String(id);

  // ✅ refresh searchable dropdown instance
  if (typeof window.refreshSearchSelect === "function") window.refreshSearchSelect(sel);
}

// =========================================================
// ✅ Thai Status (DB-first)
// - เป้าหมาย: DB/API ใช้ "คำไทย" เป็นค่า status จริง
// - แต่เพื่อไม่ให้ข้อมูลเก่าพัง เรายังรองรับค่าอังกฤษเดิม (legacy) เวลาอ่าน
// =========================================================
const ASSET_STATUSES_TH = [
  "พร้อมใช้งาน",
  "จองแล้ว",
  "กำลังเช่า",
  "รอตรวจสภาพ",
  "ซ่อม",
  "สูญหาย",
  "จำหน่ายออก",
];

const ASSET_STATUS_LEGACY_TO_TH = {
  AVAILABLE: "พร้อมใช้งาน",
  RESERVED: "จองแล้ว",
  RENTED: "กำลังเช่า",
  INSPECT: "รอตรวจสภาพ",
  REPAIR: "ซ่อม",
  LOST: "สูญหาย",
  RETIRED: "จำหน่ายออก",
};

function normalizeAssetStatus(s) {
  const raw = String(s || "").trim();
  if (!raw) return "";
  const up = raw.toUpperCase();
  if (ASSET_STATUS_LEGACY_TO_TH[up]) return ASSET_STATUS_LEGACY_TO_TH[up];
  return raw; // already Thai
}

const PO_STATUS_LEGACY_TO_TH = {
  DRAFT: "ร่าง",
  APPROVED: "อนุมัติ",
  CANCELLED: "ยกเลิก",
  CANCELED: "ยกเลิก",
  PARTIAL: "รับบางส่วน",
  FULL: "รับครบ",
};

function normalizePoStatus(s) {
  const raw = String(s || "").trim();
  if (!raw) return "";
  const up = raw.toUpperCase();
  if (PO_STATUS_LEGACY_TO_TH[up]) return PO_STATUS_LEGACY_TO_TH[up];
  return raw;
}

function localizeSelectOptions(selectEl, mapLegacyToThai) {
  // ใช้แค่ "แสดงผล" ถ้า template ยังเผลอส่ง option value อังกฤษมา
  if (!selectEl) return;
  for (const opt of Array.from(selectEl.options || [])) {
    const v = String(opt.value || "").trim();
    const up = v.toUpperCase();
    if (mapLegacyToThai[up]) {
      opt.textContent = mapLegacyToThai[up];
    }
  }
}

function localizeStaticLabels() {
  // asset status dropdown (ถ้ายังเป็น legacy)
  localizeSelectOptions(qs("asset_status"), ASSET_STATUS_LEGACY_TO_TH);

  // adjust reason dropdown (ถ้ายังเป็น legacy)
  // (เหตุผลปรับสต็อก: value จะเป็นไทยใน template ใหม่ แต่ถ้าเก่า จะเป็น code อังกฤษ)
  localizeSelectOptions(qs("adj_reason"), ASSET_STATUS_LEGACY_TO_TH);

  // PO status badge (ถ้ายังเป็น legacy)
  const b = qs("po_status_badge");
  if (b) {
    const t = (b.textContent || "").trim();
    const up = t.toUpperCase();
    if (PO_STATUS_LEGACY_TO_TH[up]) b.textContent = PO_STATUS_LEGACY_TO_TH[up];
  }
}

// ✅ label helper สำหรับ PO (กัน ReferenceError ถ้าไฟล์อื่นเคยอ้าง)
function labelPoStatus(status) {
  return normalizePoStatus(status);
}

// =========================================================
// Customer (เดิม) - keep compatibility
// =========================================================
// ===== Customer =====
async function saveCustomer() {
  try {
    const payload = {
      code: document.getElementById("c_code")?.value || "",
      name: document.getElementById("c_name")?.value || "",
      tax_id: document.getElementById("c_tax")?.value || "",
      phone: document.getElementById("c_phone")?.value || "",
      email: document.getElementById("c_email")?.value || "",
      address: document.getElementById("c_addr")?.value || "",
      credit_days: document.getElementById("c_credit_days")?.value || 0,
      credit_limit: document.getElementById("c_credit_limit")?.value || 0,
      next: document.getElementById("c_next")?.value || "",
    };

    const data = await fetchJSON("/api/customers", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    // ✅ NEW: อัปเดต dropdown แบบใหม่ (ใน form.html)
    if (window.__addCustomerToDropdown) {
      window.__addCustomerToDropdown(data.id, data.name, true);
    } else {
      // fallback: ถ้ายังใช้ select แบบเดิมอยู่บางหน้า
      addOptionToSelect("customer_id", data.id, data.name);
    }

    hideModal("modalCustomer");
  } catch (e) {
    alert(e.message || String(e));
  }
}


// ===== Product =====
async function saveProduct() {
  try {
    const payload = {
      sku: document.getElementById("p_sku")?.value || "",
      name: document.getElementById("p_name")?.value || "",
      unit: document.getElementById("p_unit")?.value || "ชิ้น",
      rent_price_per_day: document.getElementById("p_rent")?.value || 0,
      spec: document.getElementById("p_spec")?.value || "",
    };

    const data = await fetchJSON("/api/products", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    // ✅ NEW: ใส่สินค้าใหม่เข้า "ทุก dropdown ของสินค้า" ทันที
    if (window.__addProductToAllDropdowns) {
      window.__addProductToAllDropdowns(data);
    }

    // ✅ NEW: ถ้าผู้ใช้กดปุ่ม + ข้างแถวไหน ให้เลือกสินค้านั้นใน "แถวนั้น" ทันที
    if (window.__selectProductInRow && window.__productModalTargetRow) {
      window.__selectProductInRow(window.__productModalTargetRow, data);
      window.__productModalTargetRow = null;
    }

    hideModal("modalProduct");
  } catch (e) {
    alert(e.message || String(e));
  }
}

// =========================================================
// Supplier
// =========================================================
async function openSupplierModal(id, targetSelectId) {
  setErr("sup_err", "");
  qs("sup_target").value = targetSelectId || "";
  qs("sup_id").value = id ? String(id) : "";
  qs("sup_title").textContent = id ? "แก้ไขเจ้าหนี้" : "เพิ่มเจ้าหนี้";

  if (!id) {
    qs("sup_name").value = "";
    qs("sup_phone").value = "";
    qs("sup_tax").value = "";
    qs("sup_email").value = "";
    qs("sup_address").value = "";
    qs("sup_credit_days").value = "0";
    qs("sup_credit_limit").value = "0";
    qs("sup_is_active").value = "1";
    showModal("modalSupplier");
    return;
  }

  try {
    const data = await fetchJSON(`/api/suppliers/${id}`, { method: "GET", headers: {} });
    const s = data.supplier;
    qs("sup_name").value = s.name || "";
    qs("sup_phone").value = s.phone || "";
    qs("sup_tax").value = s.tax_id || "";
    qs("sup_email").value = s.email || "";
    qs("sup_address").value = s.address || "";
    qs("sup_credit_days").value = String(s.credit_days || 0);
    qs("sup_credit_limit").value = String(s.credit_limit || 0);
    qs("sup_is_active").value = s.is_active ? "1" : "0";
    showModal("modalSupplier");
  } catch (e) {
    alert(e.message || String(e));
  }
}

async function saveSupplier() {
  setErr("sup_err", "");
  try {
    const payload = {
      id: qs("sup_id").value || null,
      name: qs("sup_name").value || "",
      phone: qs("sup_phone").value || "",
      tax_id: qs("sup_tax").value || "",
      email: qs("sup_email").value || "",
      address: qs("sup_address").value || "",
      credit_days: qs("sup_credit_days").value || 0,
      credit_limit: qs("sup_credit_limit").value || 0,
      is_active: qs("sup_is_active").value === "1",
    };
    const data = await fetchJSON("/api/suppliers", { method: "POST", body: JSON.stringify(payload) });
    await refreshMasters();

    addOptionToSelect(qs("sup_target").value, data.id, data.name);

    hideModal("modalSupplier");
    if (location.pathname === "/suppliers") location.reload();
  } catch (e) {
    setErr("sup_err", e.message || String(e));
  }
}

// =========================================================
// Category
// =========================================================
async function openCategoryModal(id, targetSelectId) {
  setErr("cat_err", "");
  qs("cat_target").value = targetSelectId || "";
  qs("cat_id").value = id ? String(id) : "";
  qs("cat_title").textContent = id ? "แก้ไขหมวดหมู่" : "เพิ่มหมวดหมู่";

  if (!id) {
    qs("cat_code").value = "";
    qs("cat_name").value = "";
    qs("cat_is_active").value = "1";
    showModal("modalCategory");
    return;
  }

  try {
    const data = await fetchJSON(`/api/categories/${id}`, { method: "GET", headers: {} });
    const c = data.category;
    qs("cat_code").value = c.code || "";
    qs("cat_name").value = c.name || "";
    qs("cat_is_active").value = c.is_active ? "1" : "0";
    showModal("modalCategory");
  } catch (e) {
    alert(e.message || String(e));
  }
}

async function saveCategory() {
  setErr("cat_err", "");
  try {
    const payload = {
      id: qs("cat_id").value || null,
      code: qs("cat_code").value || "",
      name: qs("cat_name").value || "",
      is_active: qs("cat_is_active").value === "1",
    };
    const data = await fetchJSON("/api/categories", { method: "POST", body: JSON.stringify(payload) });
    await refreshMasters();

    addOptionToSelect(qs("cat_target").value, data.id, `${data.code} · ${data.name}`);

    hideModal("modalCategory");
    if (location.pathname === "/stock/categories") location.reload();
  } catch (e) {
    setErr("cat_err", e.message || String(e));
  }
}

// =========================================================
// Brand
// =========================================================
async function openBrandModal(id, targetSelectId) {
  setErr("brand_err", "");
  qs("brand_target").value = targetSelectId || "";
  qs("brand_id").value = id ? String(id) : "";
  qs("brand_title").textContent = id ? "แก้ไขยี่ห้อ" : "เพิ่มยี่ห้อ";

  if (!id) {
    qs("brand_name").value = "";
    qs("brand_is_active").value = "1";
    showModal("modalBrand");
    return;
  }

  try {
    const data = await fetchJSON(`/api/brands/${id}`, { method: "GET", headers: {} });
    const b = data.brand;
    qs("brand_name").value = b.name || "";
    qs("brand_is_active").value = b.is_active ? "1" : "0";
    showModal("modalBrand");
  } catch (e) {
    alert(e.message || String(e));
  }
}

async function saveBrand() {
  setErr("brand_err", "");
  try {
    const payload = {
      id: qs("brand_id").value || null,
      name: qs("brand_name").value || "",
      is_active: qs("brand_is_active").value === "1",
    };
    const data = await fetchJSON("/api/brands", { method: "POST", body: JSON.stringify(payload) });
    await refreshMasters();

    addOptionToSelect(qs("brand_target").value, data.id, data.name);

    hideModal("modalBrand");
  } catch (e) {
    setErr("brand_err", e.message || String(e));
  }
}

// =========================================================
// Unit
// =========================================================
async function openUnitModal(id, targetSelectId) {
  setErr("unit_err", "");
  qs("unit_target").value = targetSelectId || "";
  qs("unit_id").value = id ? String(id) : "";
  qs("unit_title").textContent = id ? "แก้ไขหน่วย" : "เพิ่มหน่วย";

  if (!id) {
    qs("unit_name").value = "";
    qs("unit_is_active").value = "1";
    showModal("modalUnit");
    return;
  }

  try {
    const data = await fetchJSON(`/api/units/${id}`, { method: "GET", headers: {} });
    const u = data.unit;
    qs("unit_name").value = u.name || "";
    qs("unit_is_active").value = u.is_active ? "1" : "0";
    showModal("modalUnit");
  } catch (e) {
    alert(e.message || String(e));
  }
}

async function saveUnit() {
  setErr("unit_err", "");
  try {
    const payload = {
      id: qs("unit_id").value || null,
      name: qs("unit_name").value || "",
      is_active: qs("unit_is_active").value === "1",
    };
    const data = await fetchJSON("/api/units", { method: "POST", body: JSON.stringify(payload) });
    await refreshMasters();

    addOptionToSelect(qs("unit_target").value, data.id, data.name);

    hideModal("modalUnit");
  } catch (e) {
    setErr("unit_err", e.message || String(e));
  }
}

// =========================================================
// Asset
// =========================================================
function assetRecalcPreview() {
  const cost = num(qs("asset_cost")?.value);
  const pd = qs("asset_purchase_date")?.value;
  const lifeDays = num(qs("asset_life_days")?.value);
  const lifeMonths = num(qs("asset_life_months")?.value);

  if (!pd) {
    qs("asset_depr").textContent = "0.00";
    qs("asset_bv").textContent = money(cost);
    qs("asset_exp").textContent = "-";
    return;
  }

  const purchaseDate = new Date(pd + "T00:00:00");
  const now = new Date();
  const diffDays = Math.max(0, Math.floor((now - purchaseDate) / (1000 * 60 * 60 * 24)));

  let totalDays = 0;
  if (lifeDays > 0) totalDays = lifeDays;
  else if (lifeMonths > 0) totalDays = lifeMonths * 30;

  let depr = 0;
  if (cost > 0 && totalDays > 0) {
    depr = Math.min(cost, (cost / totalDays) * diffDays);
  }
  const bv = Math.max(0, cost - depr);

  qs("asset_depr").textContent = money(depr);
  qs("asset_bv").textContent = money(bv);

  let exp = null;
  if (lifeDays > 0) {
    exp = new Date(purchaseDate.getTime() + lifeDays * 86400000);
  } else if (lifeMonths > 0) {
    const y = purchaseDate.getFullYear();
    const m = purchaseDate.getMonth() + lifeMonths;
    const d = purchaseDate.getDate();
    const tmp = new Date(y, m, 1);
    const lastDay = new Date(tmp.getFullYear(), tmp.getMonth() + 1, 0).getDate();
    exp = new Date(tmp.getFullYear(), tmp.getMonth(), Math.min(d, lastDay));
  }
  qs("asset_exp").textContent = exp ? exp.toISOString().slice(0, 10) : "-";
}

async function openAssetModal(id) {
  setErr("asset_err", "");
  qs("asset_id").value = id ? String(id) : "";
  qs("asset_title").textContent = id ? "แก้ไขอุปกรณ์" : "เพิ่มอุปกรณ์";
  qs("asset_photo_list").innerHTML = "";
  if (qs("asset_photos")) qs("asset_photos").value = "";

  // ✅ ensure dropdown labels are Thai
  localizeStaticLabels();

  if (!id) {
    qs("asset_category_id").value = "";
    qs("asset_name").value = "";
    qs("asset_brand_id").value = "";
    qs("asset_unit_id").value = "";
    qs("asset_supplier_id").value = "";
    qs("asset_code").value = "";
    qs("asset_cost").value = "0";
    qs("asset_purchase_date").value = qs("asset_purchase_date").value || "";
    qs("asset_life_days").value = "";
    qs("asset_life_months").value = "";
    qs("asset_status").value = "พร้อมใช้งาน";
    qs("asset_rent_day").value = "0";
    qs("asset_rent_month").value = "0";
    qs("asset_rent_year").value = "0";
    assetRecalcPreview();

    // ✅ init searchable selects inside modal
    if (typeof window.initSearchableSelects === "function") window.initSearchableSelects(qs("modalAsset"));

    showModal("modalAsset");
    return;
  }

  try {
    const data = await fetchJSON(`/api/assets/${id}`, { method: "GET", headers: {} });
    const a = data.asset;
    qs("asset_category_id").value = a.category_id || "";
    qs("asset_name").value = a.name || "";
    qs("asset_brand_id").value = a.brand_id || "";
    qs("asset_unit_id").value = a.unit_id || "";
    qs("asset_supplier_id").value = a.supplier_id || "";
    qs("asset_code").value = a.asset_code || "";
    qs("asset_cost").value = String(a.cost || 0);
    qs("asset_purchase_date").value = a.purchase_date || "";
    qs("asset_life_days").value = a.useful_life_days || "";
    qs("asset_life_months").value = a.useful_life_months || "";
    qs("asset_status").value = normalizeAssetStatus(a.status || "พร้อมใช้งาน");
    qs("asset_rent_day").value = String(a.rent_day || 0);
    qs("asset_rent_month").value = String(a.rent_month || 0);
    qs("asset_rent_year").value = String(a.rent_year || 0);

    qs("asset_depr").textContent = money(a.depreciation_accum);
    qs("asset_bv").textContent = money(a.book_value);
    qs("asset_exp").textContent = a.expired_date || "-";

    renderAssetPhotoList(a);

    if (typeof window.initSearchableSelects === "function") window.initSearchableSelects(qs("modalAsset"));

    showModal("modalAsset");
  } catch (e) {
    alert(e.message || String(e));
  }
}

function renderAssetPhotoList(asset) {
  const wrap = qs("asset_photo_list");
  if (!wrap) return;

  const photos = asset.photos || [];
  if (photos.length === 0) {
    wrap.innerHTML = '<div class="text-secondary small">ยังไม่มีรูปภาพ</div>';
    return;
  }

  const mainId = asset.main_photo_id;

  const cards = photos
    .map((p) => {
      const isMain = mainId && String(mainId) === String(p.id) ? true : !!p.is_main;
      return `
        <div class="d-inline-block me-2 mb-2">
          <div class="border rounded p-2" style="width: 160px;">
            <img src="/static/${p.file_path}" class="rounded" style="width: 100%; height: 110px; object-fit: cover;">
            <div class="mt-2 d-flex justify-content-between align-items-center">
              <span class="badge ${isMain ? "text-bg-success" : "text-bg-light border"}">${isMain ? "รูปปก" : "รูป"}</span>
              <button class="btn btn-sm btn-outline-primary" type="button" onclick="setAssetMainPhoto(${asset.id}, ${p.id})">ตั้งเป็นปก</button>
            </div>
          </div>
        </div>
      `;
    })
    .join("");

  wrap.innerHTML = cards;
}

async function setAssetMainPhoto(assetId, photoId) {
  try {
    await fetchJSON(`/api/assets/${assetId}/set_main_photo`, {
      method: "POST",
      body: JSON.stringify({ photo_id: photoId }),
    });
    const data = await fetchJSON(`/api/assets/${assetId}`, { method: "GET", headers: {} });
    renderAssetPhotoList(data.asset);
  } catch (e) {
    alert(e.message || String(e));
  }
}

async function assetAutoCode() {
  setErr("asset_err", "");
  try {
    const categoryId = qs("asset_category_id").value;
    const d = qs("asset_purchase_date").value;
    if (!categoryId) {
      setErr("asset_err", "กรุณาเลือกหมวดก่อนกด Auto");
      return;
    }
    const data = await fetchJSON("/api/assets/auto_code", {
      method: "POST",
      body: JSON.stringify({ category_id: categoryId, date: d }),
    });
    qs("asset_code").value = data.asset_code || "";
  } catch (e) {
    setErr("asset_err", e.message || String(e));
  }
}

async function saveAsset() {
  setErr("asset_err", "");
  try {
    const id = qs("asset_id").value || null;

    const categoryId = qs("asset_category_id").value;
    const name = qs("asset_name").value.trim();

    const photosEl = qs("asset_photos");
    const selectedFiles = photosEl ? photosEl.files : null;

    if (!id && selectedFiles && selectedFiles.length > 0 && selectedFiles.length < 5) {
      setErr("asset_err", "อัปโหลดรูปขั้นต่ำ 5 รูป");
      return;
    }
    if (!id && (!selectedFiles || selectedFiles.length === 0)) {
      setErr("asset_err", "กรุณาอัปโหลดรูปขั้นต่ำ 5 รูป");
      return;
    }

    const payload = {
      id: id,
      category_id: categoryId,
      brand_id: qs("asset_brand_id").value || null,
      unit_id: qs("asset_unit_id").value || null,
      supplier_id: qs("asset_supplier_id").value || null,
      name: name,
      asset_code: qs("asset_code").value.trim(),
      auto_code: !qs("asset_code").value.trim(),
      cost: qs("asset_cost").value || 0,
      purchase_date: qs("asset_purchase_date").value || "",
      useful_life_days: qs("asset_life_days").value || null,
      useful_life_months: qs("asset_life_months").value || null,
      depreciation_method: "STRAIGHT_LINE",
      rent_day: qs("asset_rent_day").value || 0,
      rent_month: qs("asset_rent_month").value || 0,
      rent_year: qs("asset_rent_year").value || 0,
      status: (qs("asset_status").value || "พร้อมใช้งาน").toString(),
    };

    const data = await fetchJSON("/api/assets", { method: "POST", body: JSON.stringify(payload) });

    if (selectedFiles && selectedFiles.length > 0) {
      const fd = new FormData();
      for (const f of selectedFiles) fd.append("photos", f);
      const res = await fetch(`/api/assets/${data.id}/photos`, { method: "POST", body: fd, credentials: "same-origin" });
      const j = await res.json();
      if (!res.ok || j.ok === false) {
        throw new Error(j.message || "Upload failed");
      }
    }

    const re = await fetchJSON(`/api/assets/${data.id}`, { method: "GET", headers: {} });
    qs("asset_depr").textContent = money(re.asset.depreciation_accum);
    qs("asset_bv").textContent = money(re.asset.book_value);
    qs("asset_exp").textContent = re.asset.expired_date || "-";
    renderAssetPhotoList(re.asset);

    if (location.pathname === "/stock/assets") {
      hideModal("modalAsset");
      location.reload();
    }
  } catch (e) {
    setErr("asset_err", e.message || String(e));
  }
}

document.addEventListener("input", (ev) => {
  const ids = ["asset_cost", "asset_purchase_date", "asset_life_days", "asset_life_months"];
  if (ids.includes(ev.target?.id)) assetRecalcPreview();
});

// =========================================================
// PO
// =========================================================
function poLineRow(data = {}) {
  const cats = window._masters && window._masters.categories ? window._masters.categories : [];
  const units = window._masters && window._masters.units ? window._masters.units : [];

  // ✅ ให้แต่ละแถวมี id ของ select ของตัวเอง (เพื่อส่งเป็น target ตอนกด +)
  window.__poRowSeq = (window.__poRowSeq || 0) + 1;
  const rowKey = window.__poRowSeq;
  const catSelId = `po_cat_${rowKey}`;
  const unitSelId = `po_unit_${rowKey}`;

  const catOpts = ['<option value="">-</option>']
    .concat(cats.map((c) => `<option value="${c.id}">${c.code} · ${c.name}</option>`))
    .join("");

  const unitOpts = ['<option value="">-</option>']
    .concat(units.map((u) => `<option value="${u.id}">${u.name}</option>`))
    .join("");

  const item = (data.item_name || "").replaceAll('"', "&quot;");
  const qty = data.qty != null ? data.qty : "1";
  const cost = data.unit_cost != null ? data.unit_cost : "0";

  return `
    <tr>
      <td><input class="form-control form-control-sm po_item" value="${item}"></td>

      <td>
        <div class="input-group input-group-sm">
          <select class="form-select po_cat js-search" id="${catSelId}">${catOpts}</select>
          <button class="btn btn-outline-secondary" type="button" onclick="openCategoryModal(null, '${catSelId}')">+</button>
        </div>
      </td>

      <td>
        <div class="input-group input-group-sm">
          <select class="form-select po_unit js-search" id="${unitSelId}">${unitOpts}</select>
          <button class="btn btn-outline-secondary" type="button" onclick="openUnitModal(null, '${unitSelId}')">+</button>
        </div>
      </td>

      <td><input class="form-control form-control-sm text-end po_qty" value="${qty}"></td>
      <td><input class="form-control form-control-sm text-end po_cost" value="${cost}"></td>
      <td class="text-end po_total">0.00</td>

      <td class="text-end">
        <button class="btn btn-sm btn-outline-danger" type="button" onclick="this.closest('tr').remove(); poRecalc();">
          <i class="bi bi-trash"></i>
        </button>
      </td>
    </tr>
  `;
}

function poAddRow(data = {}) {
  const body = qs("po_lines_body");
  if (!body) return;
  body.insertAdjacentHTML("beforeend", poLineRow(data));

  const tr = body.lastElementChild;
  if (tr) {
    if (data.category_id) tr.querySelector(".po_cat").value = String(data.category_id);
    if (data.unit_id) tr.querySelector(".po_unit").value = String(data.unit_id);

    // ✅ init searchable selects for new row
    if (typeof window.initSearchableSelects === "function") window.initSearchableSelects(tr);
  }
  poRecalc();
}

function poRecalc() {
  const body = qs("po_lines_body");
  if (!body) return;
  let grand = 0;

  for (const tr of body.querySelectorAll("tr")) {
    const qty = num(tr.querySelector(".po_qty")?.value);
    const cost = num(tr.querySelector(".po_cost")?.value);
    const total = qty * cost;
    grand += total;
    const td = tr.querySelector(".po_total");
    if (td) td.textContent = money(total);
  }
  if (qs("po_grand_total")) qs("po_grand_total").textContent = money(grand);
}

document.addEventListener("input", (ev) => {
  if (ev.target?.classList?.contains("po_qty") || ev.target?.classList?.contains("po_cost")) {
    poRecalc();
  }
});

async function openPoModal(id) {
  setErr("po_err", "");
  await refreshMasters();

  qs("po_id").value = id ? String(id) : "";
  qs("po_title").textContent = id ? "แก้ไข PO" : "สร้าง PO";
  qs("po_status_badge").textContent = labelPoStatus("DRAFT");
  qs("po_no_hint").textContent = "";

  const body = qs("po_lines_body");
  if (body) body.innerHTML = "";

  if (!id) {
    qs("po_supplier_id").value = "";
    qs("po_date").value = qs("po_date").value || "";
    qs("po_remark").value = "";
    poAddRow({});
    if (typeof window.initSearchableSelects === "function") window.initSearchableSelects(qs("modalPO"));
    showModal("modalPO");
    return;
  }

  try {
    const data = await fetchJSON(`/api/purchase_orders/${id}`, { method: "GET", headers: {} });
    const po = data.po;
    qs("po_supplier_id").value = String(po.supplier_id || "");
    qs("po_date").value = po.po_date || "";
    qs("po_remark").value = po.remark || "";
    qs("po_status_badge").textContent = labelPoStatus(po.status || "DRAFT");
    qs("po_no_hint").textContent = `เลขที่: ${po.po_no}`;

    (po.lines || []).forEach((ln) => poAddRow(ln));
    if ((po.lines || []).length === 0) poAddRow({});
    poRecalc();

    if (typeof window.initSearchableSelects === "function") window.initSearchableSelects(qs("modalPO"));

    showModal("modalPO");
  } catch (e) {
    alert(e.message || String(e));
  }
}

async function savePO(status) {
  setErr("po_err", "");
  try {
    const id = qs("po_id").value || null;
    const supplierId = qs("po_supplier_id").value;
    if (!supplierId) {
      setErr("po_err", "กรุณาเลือกเจ้าหนี้");
      return;
    }

    const lines = [];
    for (const tr of qs("po_lines_body").querySelectorAll("tr")) {
      const item = tr.querySelector(".po_item")?.value?.trim() || "";
      if (!item) continue;
      lines.push({
        item_name: item,
        category_id: tr.querySelector(".po_cat")?.value || null,
        unit_id: tr.querySelector(".po_unit")?.value || null,
        qty: tr.querySelector(".po_qty")?.value || 0,
        unit_cost: tr.querySelector(".po_cost")?.value || 0,
      });
    }

    const payload = {
      id: id,
      supplier_id: supplierId,
      po_date: qs("po_date").value || "",
      remark: qs("po_remark").value || "",
      status: status || "ร่าง",
      lines: lines,
    };

    const data = await fetchJSON("/api/purchase_orders", { method: "POST", body: JSON.stringify(payload) });
    qs("po_id").value = String(data.id);
    qs("po_status_badge").textContent = labelPoStatus(data.status || "DRAFT");
    qs("po_no_hint").textContent = `เลขที่: ${data.po_no}`;
    if (location.pathname === "/purchase/po") location.reload();
  } catch (e) {
    setErr("po_err", e.message || String(e));
  }
}

async function approvePO() {
  setErr("po_err", "");
  const id = qs("po_id").value;
  if (!id) return setErr("po_err", "ต้องบันทึกร่างก่อน");
  try {
    await fetchJSON(`/api/purchase_orders/${id}/approve`, { method: "POST", body: JSON.stringify({}) });
    if (location.pathname === "/purchase/po") location.reload();
  } catch (e) {
    setErr("po_err", e.message || String(e));
  }
}

async function cancelPO() {
  setErr("po_err", "");
  const id = qs("po_id").value;
  if (!id) return setErr("po_err", "ต้องบันทึกก่อน");
  try {
    await fetchJSON(`/api/purchase_orders/${id}/cancel`, { method: "POST", body: JSON.stringify({}) });
    if (location.pathname === "/purchase/po") location.reload();
  } catch (e) {
    setErr("po_err", e.message || String(e));
  }
}

// =========================================================
// GRN
// =========================================================
function grnLineRow(data = {}) {
  const cats = window._masters && window._masters.categories ? window._masters.categories : [];
  const units = window._masters && window._masters.units ? window._masters.units : [];

  window.__grnRowSeq = (window.__grnRowSeq || 0) + 1;
  const rowKey = window.__grnRowSeq;
  const catSelId = `grn_cat_${rowKey}`;
  const unitSelId = `grn_unit_${rowKey}`;

  const catOpts = ['<option value="">-</option>']
    .concat(cats.map((c) => `<option value="${c.id}">${c.code} · ${c.name}</option>`))
    .join("");

  const unitOpts = ['<option value="">-</option>']
    .concat(units.map((u) => `<option value="${u.id}">${u.name}</option>`))
    .join("");

  return `
    <tr data-po-line-id="${data.po_line_id || ""}">
      <td>
        <input class="form-control form-control-sm grn_item"
               value="${(data.item_name || "").replaceAll('"', "&quot;")}">
      </td>

      <td>
        <div class="input-group input-group-sm">
          <select class="form-select grn_cat js-search" id="${catSelId}">
            ${catOpts}
          </select>
          <button class="btn btn-outline-secondary" type="button"
                  onclick="openCategoryModal(null, '${catSelId}')">+</button>
        </div>
      </td>

      <td>
        <div class="input-group input-group-sm">
          <select class="form-select grn_unit js-search" id="${unitSelId}">
            ${unitOpts}
          </select>
          <button class="btn btn-outline-secondary" type="button"
                  onclick="openUnitModal(null, '${unitSelId}')">+</button>
        </div>
      </td>

      <td>
        <input class="form-control form-control-sm text-end grn_qty"
               value="${data.qty_received != null ? data.qty_received : "1"}">
      </td>

      <td>
        <input class="form-control form-control-sm text-end grn_cost"
               value="${data.unit_cost != null ? data.unit_cost : "0"}">
      </td>

      <td class="text-end">
        <button class="btn btn-sm btn-outline-danger" type="button" onclick="this.closest('tr').remove();">
          <i class="bi bi-trash"></i>
        </button>
      </td>
    </tr>
  `;
}

function grnAddRow(data = {}) {
  const body = qs("grn_lines_body");
  if (!body) return;

  body.insertAdjacentHTML("beforeend", grnLineRow(data));
  const tr = body.lastElementChild;
  if (!tr) return;

  if (data.category_id) tr.querySelector(".grn_cat").value = String(data.category_id);
  if (data.unit_id) tr.querySelector(".grn_unit").value = String(data.unit_id);

  if (typeof window.initSearchSelects === "function") {
    window.initSearchSelects(tr);
  } else if (typeof window.initChoices === "function") {
    window.initChoices(tr);
  } else if (typeof window.initSearchableSelects === "function") {
    window.initSearchableSelects(tr);
  }
}

function fillGrnPoSelect() {
  const sel = qs("grn_po_id");
  if (!sel) return;

  const masters = window._masters || {};
  const pos = masters.pos || [];
  const supplierId = qs("grn_supplier_id")?.value || "";

  sel.innerHTML = `<option value="">-- เลือก PO (เฉพาะรับจาก PO) --</option>`;

  const rows = pos.filter((po) => {
    if (!supplierId) return true;
    return String(po.supplier_id) === String(supplierId);
  });

  for (const po of rows) {
    const opt = document.createElement("option");
    opt.value = String(po.id);
    opt.textContent = `${po.po_no} · ${po.supplier_name || ""}`;
    sel.appendChild(opt);
  }

  if (typeof window.refreshSearchSelect === "function") window.refreshSearchSelect(sel);
}

async function openGrnModal(id) {
  setErr("grn_err", "");
  await refreshMasters();

  qs("grn_id").value = id ? String(id) : "";
  qs("grn_title").textContent = id ? "แก้ไข GRN" : "สร้าง GRN";
  qs("grn_no_hint").textContent = "";
  qs("gen_assets_wrap").style.display = "none";
  qs("gen_assets_body").innerHTML = "";
  qs("grn_lines_body").innerHTML = "";

  if (!id) {
    const defMode = qs("grn_mode")?.value || "po";
    qs("grn_mode").value = defMode;

    qs("grn_supplier_id").value = "";
    qs("grn_date").value = qs("grn_date").value || "";
    qs("grn_remark").value = "";

    fillGrnPoSelect();
    qs("grn_po_id").value = "";

    grnModeChanged();

    // ✅ ถ้าเป็นโหมด cash ให้มีแถวว่าง 1 แถว
    // ✅ ถ้าเป็นโหมด po ยังไม่ต้องใส่แถว จนกว่าจะเลือก PO / prefill
    if (defMode === "cash") {
      grnAddRow({});
    }

    if (typeof window.initSearchSelects === "function") {
      window.initSearchSelects(qs("modalGRN"));
    } else if (typeof window.initChoices === "function") {
      window.initChoices(qs("modalGRN"));
    } else if (typeof window.initSearchableSelects === "function") {
      window.initSearchableSelects(qs("modalGRN"));
    }

    showModal("modalGRN");
    return;
  }

  try {
    const data = await fetchJSON(`/api/grns/${id}`, { method: "GET", headers: {} });
    const g = data.grn;

    qs("grn_supplier_id").value = String(g.supplier_id || "");
    qs("grn_date").value = g.grn_date || "";
    qs("grn_remark").value = g.remark || "";

    qs("grn_mode").value = g.po_id ? "po" : "cash";
    grnModeChanged();

    fillGrnPoSelect();
    qs("grn_po_id").value = g.po_id ? String(g.po_id) : "";

    qs("grn_no_hint").textContent = `เลขที่: ${g.grn_no}`;

    qs("grn_lines_body").innerHTML = "";
    (g.lines || []).forEach((ln) => grnAddRow(ln));

    if ((g.lines || []).length === 0) {
      grnAddRow({});
    }

    if (g.assets_generated_at) {
      setErr("grn_err", "GRN นี้ Generate Assets แล้ว (ระบบล็อกไม่ให้แก้ไขรายการ)");
    }

    if (typeof window.initSearchSelects === "function") {
      window.initSearchSelects(qs("modalGRN"));
    } else if (typeof window.initChoices === "function") {
      window.initChoices(qs("modalGRN"));
    } else if (typeof window.initSearchableSelects === "function") {
      window.initSearchableSelects(qs("modalGRN"));
    }

    showModal("modalGRN");
  } catch (e) {
    alert(e.message || String(e));
  }
}

function grnModeChanged() {
  const mode = qs("grn_mode").value;
  const poWrap = qs("grn_po_wrap");
  if (!poWrap) return;
  poWrap.style.display = mode === "po" ? "" : "none";
  if (mode !== "po") qs("grn_po_id").value = "";
}

async function prefillGrnFromPO(poIdArg = null) {
  setErr("grn_err", "");

  const poId = (poIdArg != null && String(poIdArg).trim() !== "")
    ? String(poIdArg).trim()
    : (qs("grn_po_id")?.value || "").trim();

  if (!poId) return;

  try {
    const data = await fetchJSON("/api/grns/prefill_from_po", {
      method: "POST",
      body: JSON.stringify({ po_id: poId }),
    });

    // 1) ตั้ง supplier ก่อน (สำคัญมาก)
    if (data.po && data.po.supplier_id) {
      qs("grn_supplier_id").value = String(data.po.supplier_id);
    }

    // 2) เติม PO dropdown หลังจากรู้ supplier แล้ว
    fillGrnPoSelect();

    // 3) ensure มี option ของ PO นี้อยู่ แม้ dropdown จะยังไม่เคยมี
    const poSel = qs("grn_po_id");
    if (poSel) {
      const exists = Array.from(poSel.options).some((o) => String(o.value) === String(poId));
      if (!exists && data.po) {
        const opt = document.createElement("option");
        opt.value = String(poId);
        opt.textContent = `${data.po.po_no || ("PO#" + poId)} · ${data.po.supplier_name || ""}`;
        poSel.appendChild(opt);
      }
      poSel.value = String(poId);

      if (typeof window.refreshSearchSelect === "function") {
        window.refreshSearchSelect(poSel);
      }
    }

    // 4) เติมรายการ lines
    const body = qs("grn_lines_body");
    body.innerHTML = "";

    (data.lines || []).forEach((ln) =>
      grnAddRow({
        po_line_id: ln.po_line_id || ln.id || "",
        item_name: ln.item_name || "",
        category_id: ln.category_id || "",
        unit_id: ln.unit_id || "",
        qty_received: ln.qty_received != null ? ln.qty_received : (ln.qty || 1),
        unit_cost: ln.unit_cost != null ? ln.unit_cost : 0,
      })
    );

    if ((data.lines || []).length === 0) {
      grnAddRow({});
    }

    // re-init searchable selects
    if (typeof window.initSearchSelects === "function") {
      window.initSearchSelects(qs("modalGRN"));
    } else if (typeof window.initChoices === "function") {
      window.initChoices(qs("modalGRN"));
    } else if (typeof window.initSearchableSelects === "function") {
      window.initSearchableSelects(qs("modalGRN"));
    }
  } catch (e) {
    setErr("grn_err", e.message || String(e));
  }
}

async function saveGRN() {
  setErr("grn_err", "");
  try {
    const id = qs("grn_id").value || null;
    const mode = qs("grn_mode").value;
    const supplierId = qs("grn_supplier_id").value;

    if (!supplierId) {
      setErr("grn_err", "กรุณาเลือกเจ้าหนี้");
      return;
    }

    const poId = mode === "po" ? (qs("grn_po_id").value || null) : null;
    if (mode === "po" && !poId) {
      setErr("grn_err", "โหมดรับจาก PO ต้องเลือก PO");
      return;
    }

    const lines = [];
    for (const tr of qs("grn_lines_body").querySelectorAll("tr")) {
      const item = tr.querySelector(".grn_item")?.value?.trim() || "";
      if (!item) continue;
      lines.push({
        po_line_id: tr.dataset.poLineId || null,
        item_name: item,
        category_id: tr.querySelector(".grn_cat")?.value || null,
        unit_id: tr.querySelector(".grn_unit")?.value || null,
        qty_received: tr.querySelector(".grn_qty")?.value || 0,
        unit_cost: tr.querySelector(".grn_cost")?.value || 0,
      });
    }

    const payload = {
      id: id,
      mode: mode,
      grn_date: qs("grn_date").value || "",
      supplier_id: supplierId,
      po_id: poId,
      remark: qs("grn_remark").value || "",
      lines: lines,
    };

    const data = await fetchJSON("/api/grns", { method: "POST", body: JSON.stringify(payload) });
    qs("grn_id").value = String(data.id);
    qs("grn_no_hint").textContent = `เลขที่: ${data.grn_no}`;
    if (location.pathname === "/purchase/grn") location.reload();
  } catch (e) {
    setErr("grn_err", e.message || String(e));
  }
}

function prepareGenerateAssets() {
  setErr("grn_err", "");
  const id = qs("grn_id").value;
  if (!id) {
    setErr("grn_err", "ต้องบันทึก GRN ก่อน");
    return;
  }

  const brands = window._masters && window._masters.brands ? window._masters.brands : [];
  const units = window._masters && window._masters.units ? window._masters.units : [];

  const brandOpts = ['<option value="">-</option>'].concat(brands.map((b) => `<option value="${b.id}">${b.name}</option>`)).join("");
  const unitOpts = ['<option value="">-</option>'].concat(units.map((u) => `<option value="${u.id}">${u.name}</option>`)).join("");

  const body = qs("gen_assets_body");
  body.innerHTML = "";

  for (const tr of qs("grn_lines_body").querySelectorAll("tr")) {
    const item = tr.querySelector(".grn_item")?.value?.trim() || "";
    const cat = tr.querySelector(".grn_cat")?.value || "";
    if (!item || !cat) continue;

    const qty = Math.max(0, Math.floor(num(tr.querySelector(".grn_qty")?.value)));
    const cost = tr.querySelector(".grn_cost")?.value || 0;

    for (let i = 0; i < qty; i++) {
      body.insertAdjacentHTML(
        "beforeend",
        `
          <tr data-cat-id="${cat}" data-default-name="${item.replaceAll('"', "&quot;")}" data-default-cost="${cost}">
            <td><input class="form-control form-control-sm gen_code text-uppercase" placeholder="ปล่อยว่างเพื่อ Auto"></td>
            <td><input class="form-control form-control-sm gen_name" value="${item.replaceAll('"', "&quot;")}"></td>
            <td><select class="form-select form-select-sm gen_brand js-search">${brandOpts}</select></td>
            <td><select class="form-select form-select-sm gen_unit js-search">${unitOpts}</select></td>
            <td><input class="form-control form-control-sm text-end gen_cost" value="${cost}"></td>
          </tr>
        `
      );
    }
  }

  qs("gen_assets_wrap").style.display = "";

  // ✅ init searchable selects for generated table
  if (typeof window.initSearchableSelects === "function") window.initSearchableSelects(qs("gen_assets_wrap"));
}

async function submitGenerateAssets() {
  setErr("grn_err", "");
  const id = qs("grn_id").value;
  if (!id) {
    setErr("grn_err", "ต้องบันทึก GRN ก่อน");
    return;
  }

  const items = [];
  for (const tr of qs("gen_assets_body").querySelectorAll("tr")) {
    items.push({
      asset_code: tr.querySelector(".gen_code")?.value || "",
      name: tr.querySelector(".gen_name")?.value || "",
      brand_id: tr.querySelector(".gen_brand")?.value || null,
      unit_id: tr.querySelector(".gen_unit")?.value || null,
      cost: tr.querySelector(".gen_cost")?.value || 0,
    });
  }

  try {
    const data = await fetchJSON(`/api/grns/${id}/generate_assets`, {
      method: "POST",
      body: JSON.stringify({ items }),
    });
    alert(`สร้างอุปกรณ์แล้ว ${data.created.length} รายการ`);
    hideModal("modalGRN");
    location.href = "/stock/assets";
  } catch (e) {
    setErr("grn_err", e.message || String(e));
  }
}

// Auto open from PO hash: #fromPO=123
// Auto open from PO hash: #fromPO=123
document.addEventListener("DOMContentLoaded", async () => {
  await refreshMasters();

  if (typeof localizeStaticLabels === "function") {
    localizeStaticLabels();
  }

  if (typeof window.initSearchSelects === "function") {
    window.initSearchSelects(document);
  } else if (typeof window.initChoices === "function") {
    window.initChoices(document);
  } else if (typeof window.initSearchableSelects === "function") {
    window.initSearchableSelects(document);
  }

  const supSel = qs("grn_supplier_id");
  if (supSel) {
    supSel.addEventListener("change", () => {
      fillGrnPoSelect();

      if (qs("grn_mode")?.value === "po") {
        qs("grn_po_id").value = "";
        qs("grn_lines_body").innerHTML = "";
      } else {
        qs("grn_lines_body").innerHTML = "";
        grnAddRow({});
      }
    });
  }

  // ✅ จุดสำคัญ: รองรับทั้ง /purchase/grn และ /purchase/grn?mode=po
  // ✅ Auto open from PO: รองรับทั้ง #fromPO=123 และ ?fromPO=123
const pathOk = window.location.pathname.includes("/purchase/grn");

function getFromPO() {
  const hash = window.location.hash || "";
  if (hash.startsWith("#fromPO=")) return hash.replace("#fromPO=", "").trim();

  const url = new URL(window.location.href);
  return (url.searchParams.get("fromPO") || "").trim();
}

const fromPO = pathOk ? getFromPO() : "";
if (fromPO) {
  const modalEl = qs("modalGRN");

  // ✅ เรียกตอน modal "แสดงจริง" เท่านั้น (แก้ปัญหา timing/choices รีเซ็ต)
  const onShown = async () => {
    try {
      const modeHidden = qs("grn_mode");
      const radioPo = qs("grnModePO");

      if (modeHidden) modeHidden.value = "po";
      if (radioPo) radioPo.checked = true;
      grnModeChanged();

      await prefillGrnFromPO(fromPO);
    } finally {
      modalEl?.removeEventListener("shown.bs.modal", onShown);
    }
  };

  if (modalEl) modalEl.addEventListener("shown.bs.modal", onShown, { once: true });

  // เปิด modal หลังจากผูก event แล้ว
  await openGrnModal(null);
}
});
// =========================================================
// Adjust
// =========================================================
function toggleAllAdjust(cb) {
  const checks = document.querySelectorAll(".adj-check");
  checks.forEach((c) => (c.checked = cb.checked));
}

function openAdjustModal() {
  const selected = Array.from(document.querySelectorAll(".adj-check")).filter((x) => x.checked);
  qs("adj_count").textContent = String(selected.length);
  setErr("adj_err", "");
  if (selected.length === 0) {
    setErr("adj_err", "กรุณาเลือกรายการก่อน");
    showModal("modalAdjust");
    return;
  }

  // ensure Thai option labels
  localizeStaticLabels();

  // init searchable selects inside modal
  if (typeof window.initSearchableSelects === "function") window.initSearchableSelects(qs("modalAdjust"));

  showModal("modalAdjust");
}

async function submitAdjust() {
  setErr("adj_err", "");
  const selected = Array.from(document.querySelectorAll(".adj-check"))
    .filter((x) => x.checked)
    .map((x) => x.value);
  if (selected.length === 0) {
    setErr("adj_err", "กรุณาเลือกรายการก่อน");
    return;
  }

  try {
    // ✅ backend ปัจจุบัน validate เป็น code อังกฤษ => ส่ง code เดิม
    const reasonCode = (qs("adj_reason").value || "").toString().toUpperCase();

    await fetchJSON("/api/adjust", {
      method: "POST",
      body: JSON.stringify({
        asset_ids: selected,
        reason: reasonCode,
        note: qs("adj_note").value || "",
      }),
    });
    hideModal("modalAdjust");
    location.reload();
  } catch (e) {
    setErr("adj_err", e.message || String(e));
  }
}