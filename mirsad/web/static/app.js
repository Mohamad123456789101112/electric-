/* مِرصاد — واجهة التحقيق الجنائي الرقمي */
let REPORT = null, EID = null, CASES = [];

const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, c =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const art = (f) => `/api/evidence/${EID}/artifact/${f}`;
const fmt = (v) => (v && typeof v === "object") ? JSON.stringify(v, null, 1) : String(v ?? "");

/* ---------------------------------------------------------------- القضايا */
async function loadCases() {
  CASES = await (await fetch("/api/cases")).json();
  const sel = $("#caseSelect");
  const cur = sel.value;
  sel.innerHTML = '<option value="">— بدون قضية —</option>' +
    CASES.map(c => `<option value="${c.id}">${esc(c.number)} — ${esc(c.title || "")} (${c.evidence_count} دليل)</option>`).join("");
  sel.value = cur;
}

$("#btnNewCase").onclick = () => {
  showModal("فتح قضية جديدة", `
    <input id="cNum" placeholder="رقم القضية *">
    <input id="cTitle" placeholder="عنوان القضية">
    <input id="cInv" placeholder="اسم المحقق">
    <input id="cAuth" placeholder="الجهة / النيابة">
    <input id="cNotes" placeholder="ملاحظات">
    <button class="btn primary" id="cSave">حفظ القضية</button>`);
  $("#cSave").onclick = async () => {
    const fd = new FormData();
    fd.append("number", $("#cNum").value || "بدون رقم");
    fd.append("title", $("#cTitle").value);
    fd.append("investigator", $("#cInv").value);
    fd.append("authority", $("#cAuth").value);
    fd.append("notes", $("#cNotes").value);
    const c = await (await fetch("/api/cases", { method: "POST", body: fd })).json();
    await loadCases();
    $("#caseSelect").value = c.id;
    closeModal();
  };
};

$("#btnChain").onclick = async () => {
  const cid = $("#caseSelect").value;
  if (!cid) return showModal("سلسلة الحيازة", "<p class='muted'>اختر قضية أولًا لعرض سجل الحيازة المُسلسل تشفيريًا.</p>");
  const c = await (await fetch(`/api/cases/${cid}`)).json();
  const ok = c.chain.intact;
  showModal(`سلسلة حيازة القضية ${esc(c.number)}`, `
    <p class="${ok ? "" : "badge crit"}">${esc(c.chain.statement)}</p>
    <p class="muted">عدد القيود: ${c.chain.entries} · بصمة الرأس: <code>${esc((c.chain.head_hash || "").slice(0, 24))}…</code></p>
    <div class="scroll"><table><thead><tr><th>#</th><th>الوقت</th><th>الفاعل</th><th>الإجراء</th><th>التفاصيل</th></tr></thead>
    <tbody>${c.custody.map(r => `<tr><td>${r.seq}</td><td class="mono">${esc(r.ts_utc)}</td>
      <td>${esc(r.actor)}</td><td>${esc(r.action)}</td><td>${esc(r.details)}</td></tr>`).join("")}</tbody></table></div>`);
};

$("#btnCameras").onclick = () => openCameras();
$("#btnSigs").onclick = () => openSigs();
$("#btnCaseMap").onclick = () => openCaseMap();

/* ----------------------------------------------------------------- الرفع */
const dz = $("#dropzone");
["dragenter", "dragover"].forEach(e => dz.addEventListener(e, ev => { ev.preventDefault(); dz.classList.add("drag"); }));
["dragleave", "drop"].forEach(e => dz.addEventListener(e, ev => { ev.preventDefault(); dz.classList.remove("drag"); }));
dz.addEventListener("drop", ev => { if (ev.dataTransfer.files[0]) upload(ev.dataTransfer.files[0]); });
$("#fileInput").onchange = e => { if (e.target.files[0]) upload(e.target.files[0]); };
$("#btnNew").onclick = () => { $("#results").classList.add("hidden"); dz.classList.remove("hidden"); $("#fileInput").value = ""; };

async function upload(file) {
  dz.classList.add("hidden");
  $("#results").classList.add("hidden");
  $("#progress").classList.remove("hidden");
  $("#progTitle").textContent = `جارٍ تحليل «${file.name}» …`;
  const steps = ["حساب البصمات التشفيرية…", "تعريف النوع من التوقيع الثنائي…",
    "تفكيك الحاوية واستخراج الميتاداتا…", "مسح البايتات لاسترجاع الآثار الممسوحة…",
    "تحليل ELA والضجيج والنسخ-اللصق…", "اختبارات الإخفاء الإحصائية…",
    "نحت الملفات المدمجة…", "بناء الخط الزمني والتقييم…"];
  let i = 0;
  const t = setInterval(() => { $("#progStep").textContent = steps[i % steps.length]; i++; }, 1400);
  $("#progStep").textContent = steps[0];

  const fd = new FormData();
  fd.append("file", file);
  fd.append("case_id", $("#caseSelect").value);
  fd.append("actor", $("#actorInput").value || "محقق");
  fd.append("source_note", $("#noteInput").value || "");
  fd.append("deep", $("#deepChk").checked ? "true" : "false");
  try {
    const r = await fetch("/api/analyze", { method: "POST", body: fd });
    if (!r.ok) throw new Error((await r.json()).detail || r.statusText);
    REPORT = await r.json();
    EID = REPORT.evidence.evidence_id;
    render();
    loadCases();
  } catch (e) {
    alert("فشل التحليل: " + e.message);
    dz.classList.remove("hidden");
  } finally {
    clearInterval(t);
    $("#progress").classList.add("hidden");
  }
}

/* ----------------------------------------------------------------- العرض */
function render() {
  $("#results").classList.remove("hidden");
  const a = REPORT.assessment || {}, ev = REPORT.evidence || {}, t = REPORT.type || {};
  const colors = { critical: "--crit", high: "--high", medium: "--med", low: "--low", clean: "--ok" };
  const col = `var(${colors[a.level_class] || "--ok"})`;
  const pct = Math.min(100, a.suspicion_score || 0);
  $("#verdict").innerHTML = `
    <div class="gauge" style="background:conic-gradient(${col} ${pct * 3.6}deg,#1b2635 0);color:${col}">
      <div style="width:82px;height:82px;border-radius:50%;background:var(--card);display:grid;place-items:center">${pct}</div>
    </div>
    <div class="vinfo">
      <h2 style="color:${col}">${esc(a.level || "")}</h2>
      <div class="vfile">${esc(ev.filename)} · ${esc(ev.size_human)} · ${esc(t.description || "")} · ${esc(t.mime || "")}</div>
      <div class="badges">
        <span class="badge">${a.findings_count || 0} مؤشر</span>
        ${t.extension_mismatch ? '<span class="badge crit">تمويه امتداد</span>' : ""}
        ${(REPORT.recovery?.exif_fragments || []).length ? `<span class="badge high">${REPORT.recovery.exif_fragments.length} شظية EXIF مستعادة</span>` : ""}
        ${REPORT.metadata && Object.keys(REPORT.metadata).length ? `<span class="badge ok">${Object.keys(REPORT.metadata).length} حقل وصفي</span>` : '<span class="badge med">لا ميتاداتا قياسية</span>'}
        ${gpsOf() ? '<span class="badge ok">📍 موقع جغرافي</span>' : ""}
        ${(REPORT.carving || []).filter(c => c.extracted).length ? `<span class="badge high">${REPORT.carving.filter(c => c.extracted).length} ملف منحوت</span>` : ""}
        <span class="badge">⏱ ${esc(ev.analysis_seconds)} ث</span>
      </div>
    </div>`;

  $("#btnHtml").href = `/api/evidence/${EID}/report.html`;
  $("#btnTxt").href = `/api/evidence/${EID}/report.txt`;
  $("#btnJson").href = `/api/evidence/${EID}`;
  $("#btnPkg").href = `/api/evidence/${EID}/package`;

  tabSummary(); tabHashes(); tabMeta(); tabGeo(); tabRecovery(); tabImage(); tabPrnu(); tabQt(); tabSteg(); tabDb();
  tabStruct(); tabCarve(); tabStrings(); tabTimeline(); tabEntropy(); tabHex(); tabRaw();
  $$("#tabs button")[0].click();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function gpsOf() {
  const m = REPORT.metadata || {};
  for (const k in m) if (k.includes("الموقع الجغرافي")) return m[k].value;
  for (const f of (REPORT.recovery?.exif_fragments || [])) if (f.gps) return f.gps;
  for (const e of (REPORT.recovery?.embedded_images || [])) if (e.info?.gps) return e.info.gps;
  return null;
}

$$("#tabs button").forEach(b => b.onclick = () => {
  $$("#tabs button").forEach(x => x.classList.remove("active"));
  $$(".panel").forEach(x => x.classList.remove("active"));
  b.classList.add("active");
  $("#tab-" + b.dataset.tab).classList.add("active");
});

const card = (title, body) => `<div class="card"><h3>${title}</h3>${body}</div>`;
const kvGrid = (obj) => `<div class="grid">` + Object.entries(obj || {}).map(([k, v]) =>
  `<div class="kv"><b>${esc(k)}</b><span class="${typeof v === "string" && /^[\x00-\x7F]+$/.test(v) ? "mono" : ""}">${esc(fmt(v)).slice(0, 400)}</span></div>`).join("") + `</div>`;
const tbl = (headers, rows) => `<div class="scroll"><table><thead><tr>${headers.map(h => `<th>${esc(h)}</th>`).join("")}</tr></thead><tbody>${rows}</tbody></table></div>`;

/* 1) الخلاصة */
function tabSummary() {
  const a = REPORT.assessment || {};
  const f = (a.findings || []).map(x => `
    <div class="finding ${esc(x.severity)}">
      <h4><span class="sev">${esc(x.severity)}</span>${esc(x.title)}<span class="pill">وزن ${x.weight}</span></h4>
      <div>${esc(x.detail)}</div><code>${esc(x.evidence)}</code>
    </div>`).join("") || "<p class='muted'>لم تُرصد أي مؤشرات تلاعب أو شذوذ.</p>";
  const g = gpsOf();
  let gps = "";
  if (g) gps = card("📍 الموقع الجغرافي المستخرج", kvGrid(g) +
    `<a class="map-link btn ghost" target="_blank" href="${esc(g.google_maps || "#")}">فتح في الخرائط</a>`);
  const rv = (REPORT.recovery?.verdict || []).map(v => `<li>${esc(v)}</li>`).join("");
  $("#tab-summary").innerHTML =
    card("المؤشرات المرصودة", f) +
    gps +
    (rv ? card("خلاصة الاسترجاع", `<ul>${rv}</ul>`) : "") +
    card("منهجية التقييم", `<p class="muted">${esc(a.disclaimer || "")}</p>`) +
    ((REPORT.errors || []).length ? card("أخطاء وحدات (شفافية كاملة)",
      tbl(["الوحدة", "الخطأ"], REPORT.errors.map(e => `<tr><td>${esc(e.module)}</td><td class="mono">${esc(e.error)}</td></tr>`).join(""))) : "");
}

/* 2) البصمات */
function tabHashes() {
  const fp = REPORT.fingerprints || {};
  const bh = REPORT.block_hashes || [];
  $("#tab-hashes").innerHTML =
    card("البصمات التشفيرية", kvGrid(fp)) +
    card("البصمة السياقية (CTPH)", `<p class="muted">تُستخدم لقياس التشابه بين الأدلة حتى لو اختلفت قليلًا — قارن دليلين عبر <code>POST /api/compare</code>.</p>
      <div class="kv"><b>ssdeep-style</b><span class="mono">${esc(fp.ctph_fuzzy)}</span></div>`) +
    card(`تجزئة القطاعات (${bh.length} قطعة × 4 ك.بايت)`,
      tbl(["الإزاحة", "الحجم", "SHA-256"], bh.slice(0, 400).map(b =>
        `<tr><td class="mono">${b.offset}</td><td>${b.size}</td><td class="mono">${esc(b.sha256)}</td></tr>`).join("")));
}

/* 3) الميتاداتا */
function tabMeta() {
  const m = REPORT.metadata || {};
  const rows = Object.entries(m).map(([k, v]) =>
    `<tr><td>${esc(k)}</td><td>${esc(fmt(v.value)).slice(0, 600)}</td><td class="muted">${esc(v.source)}</td></tr>`).join("");
  const c = REPORT.containers || {};
  let extra = "";
  const ex = c.jpeg?.app_payloads?.Exif || c.png?.exif || c.tiff || c.riff?.exif || c.iso_bmff?.exif;
  if (ex) {
    for (const sect of ["IFD0", "ExifIFD", "GPSIFD", "InteropIFD", "IFD1_thumbnail"]) {
      if (!ex[sect]) continue;
      extra += card(`EXIF · ${sect}`, tbl(["الوسم", "النوع", "القيمة", "الخام"],
        Object.entries(ex[sect]).map(([k, v]) => `<tr><td>${esc(k)} <span class="pill mono">${esc(v.tag || "")}</span></td>
          <td class="muted">${esc(v.type || "")}</td><td>${esc(fmt(v.value)).slice(0, 300)}</td>
          <td class="mono muted">${esc(fmt(v.raw)).slice(0, 120)}</td></tr>`).join("")));
    }
  }
  const icc = c.jpeg?.app_payloads?.ICC || c.png?.icc;
  if (icc) extra += card("ملف تعريف الألوان ICC", kvGrid(icc));
  const iptc = c.jpeg?.app_payloads?.Photoshop_IRB?.IPTC;
  if (iptc && Object.keys(iptc).length) extra += card("IPTC", kvGrid(iptc));
  const xmp = c.jpeg?.app_payloads?.XMP;
  if (xmp) extra += card("XMP الخام", `<pre class="json">${esc(xmp.slice(0, 20000))}</pre>`);
  $("#tab-meta").innerHTML = makerNoteCards() +
    card("كل الحقول الوصفية المستخرجة", rows ? tbl(["الحقل", "القيمة", "المصدر"], rows)
      : "<p class='muted'>لا توجد بيانات وصفية قياسية — انتقل لتبويب «الاسترجاع».</p>") + extra;
}

/* 3-أ) الموقع الجغرافي */
function tabGeo() {
  const el = $("#tab-geo");
  if (!el) return;
  const g = REPORT.geolocation || {};
  let h = "";
  const cls = g.located ? "ok" : "med";
  h += card("📍 خلاصة الموقع",
    `<p class="badge ${cls}" style="font-size:15px">${esc(g.verdict || "—")}</p>
     <p class="muted">إشارات مرصودة: ${g.points_count || 0} نقطة
      (${g.measured_points || 0} منها مُقاسة بجهاز) ·
      ${Object.keys(g.place_names || {}).length} اسم مكان ·
      ${(g.indirect_indicators || []).length} مؤشر غير مباشر.</p>`);

  const p = g.primary;
  if (p) {
    const f = p.formats || {};
    h += card("الموقع الأساسي", `
      <iframe class="geomap" src="${esc((f.links || {})["خريطة مُضمَّنة"])}"
        loading="lazy" referrerpolicy="no-referrer"></iframe>
      <p class="muted">إن لم تظهر الخريطة فالجهاز بلا إنترنت — الإحداثيات أدناه كاملة.</p>
      ` + kvGrid({
      "الإحداثيات (عشري)": f.decimal,
      "درجات/دقائق/ثوانٍ": f.dms,
      "ISO 6709": f.iso_6709,
      "Plus Code": f.plus_code,
      "Geohash": f.geohash,
      "منطقة UTM": (f.utm || {}).label + " — النصف " + (f.utm || {}).hemisphere,
      "فرق التوقيت المحسوب": "UTC" + (((f.timezone || {}).estimated_utc_offset >= 0 ? "+" : "") + (f.timezone || {}).estimated_utc_offset),
      "الارتفاع": p.altitude_m != null ? p.altitude_m + " م " + (p.altitude_note || "") : "—",
      "نوع التثبيت": p.fix_type || "—",
      "حالة الإشارة": p.status_meaning || p.status || "—",
      "عدد الأقمار": p.satellites || "—",
      "DOP": p.dop != null ? p.dop + " (" + (p.dop_quality || "") + ")" : "—",
      "الخطأ الأفقي المعلن": p.horizontal_error_m != null ? p.horizontal_error_m + " م" : "—",
      "السرعة لحظة الالتقاط": p.speed_kmh != null ? p.speed_kmh + " كم/س — " + (p.speed_note || "") : "—",
      "اتجاه عدسة الكاميرا": p.camera_direction_deg != null
        ? p.camera_direction_deg + "° (" + p.camera_direction_text + ") نسبةً إلى " + (p.camera_direction_ref || "") : "—",
      "اتجاه الحركة": p.movement_direction_deg != null
        ? p.movement_direction_deg + "° (" + p.movement_direction_text + ")" : "—",
      "تاريخ/وقت GPS (UTC)": [p.gps_date_utc, p.gps_time_utc].filter(Boolean).join(" ") || "—",
      "مرجع الإسناد (Datum)": p.map_datum || "—",
      "المصدر": p.source,
    }) + `<p><b>ثقة الموقع: ${esc((p.confidence || {}).level)} (${esc((p.confidence || {}).score)}/100)</b>
        — ${esc(((p.confidence || {}).reasons || []).join("، "))}</p>
      <div class="exportbar">` +
      Object.entries(f.links || {}).filter(([k]) => k !== "خريطة مُضمَّنة")
        .map(([k, v]) => `<a class="btn ghost" target="_blank" rel="noopener" href="${esc(v)}">${esc(k)}</a>`).join("") +
      `<button class="btn ghost" onclick="navigator.clipboard&&navigator.clipboard.writeText('${esc(f.decimal)}')">نسخ الإحداثيات</button></div>`);
  }

  const chk = g.consistency_checks || [];
  if (chk.length) h += card("⚠️ فحوص الاتساق",
    `<ul>${chk.map(c => `<li><b>[${esc(c.severity)}]</b> ${esc(c.note)}</li>`).join("")}</ul>`);

  if ((g.points || []).length > 1) {
    h += card(`كل النقاط المرصودة (${g.points.length})`,
      tbl(["الإحداثيات", "النوع", "المصدر", "الثقة", "خريطة"],
        g.points.map(q => `<tr>
          <td class="mono">${esc((q.formats || {}).decimal)}</td>
          <td>${esc(q.kind || "")}</td>
          <td>${esc(q.source || "")}${q.snippet ? `<div class="muted mono">${esc(q.snippet)}</div>` : ""}</td>
          <td class="mono">${esc((q.confidence || {}).score)}</td>
          <td><a class="btn ghost" target="_blank" rel="noopener"
             href="${esc(((q.formats || {}).links || {})["OpenStreetMap"])}">افتح</a></td></tr>`).join("")));
  }

  const places = g.place_names || {};
  if (Object.keys(places).length) h += card("أسماء أماكن مكتوبة في الملف",
    tbl(["الحقل", "القيمة", "المصدر"], Object.entries(places).map(([k, v]) =>
      `<tr><td>${esc(k)}</td><td><b>${esc(v.value)}</b></td><td class="muted">${esc(v.source)}</td></tr>`).join("")));

  const inds = g.indirect_indicators || [];
  if (inds.length) h += card("مؤشرات ترجيحية (تُضيّق النطاق ولا تحدّد نقطة)",
    tbl(["النوع", "الدولة", "القيم", "ملاحظة"], inds.map(i =>
      `<tr><td>${esc(i.type)}</td><td>${esc(i.country || "—")}</td>
       <td class="mono">${esc(Array.isArray(i.value) ? i.value.join("، ") : i.value)}</td>
       <td class="muted">${esc(i.note || "")}</td></tr>`).join("")));

  if (!g.located && !inds.length && !Object.keys(places).length)
    h += card("لا يوجد موقع", `<p class="muted">لم يُعثر على أي إشارة موقع. هذا لا يعني
      أن الملف بلا موقع أصلًا — قد تكون الميتاداتا أُزيلت تمامًا (راجع تبويب «الاسترجاع»).</p>`);

  el.innerHTML = h;
}

/* قواعد بيانات SQLite */
function tabDb() {
  const el = $("#tab-db");
  if (!el) return;
  const c = REPORT.containers || {};
  const s = c.sqlite;
  if (!s || !s.ok) {
    let h = card("قواعد البيانات", `<p class="muted">${esc((s && s.reason) ||
      "هذا الملف ليس قاعدة SQLite.")}</p>`);
    if (c.sqlite_wal) h += card("ملف WAL مستقل", kvGrid(c.sqlite_wal));
    if (c.sqlite_journal) h += card("ملف journal مستقل", kvGrid(c.sqlite_journal));
    el.innerHTML = h;
    return;
  }
  let h = card("♻️ خلاصة قاعدة البيانات",
    `<p class="badge ${s.deleted_count ? "high" : "ok"}" style="font-size:15px">${esc(s.verdict)}</p>
     <p class="muted">الحذف في SQLite لا يمحو البايتات: يضع السجل في «كتلة حرة» أو
      يُلحق الصفحة بقائمة الصفحات الحرة. هذه الوحدة تقرأ تلك المساحات وتُعيد بناء
      ترويسة السجل المطموسة.</p>`);
  h += card("ترويسة الملف", kvGrid(s.header));
  (s.tables || []).forEach(t => {
    const cols = t.columns || [];
    const rows = (t.rows || []).slice(0, 200).map(r => {
      const vals = r.values || [];
      return `<tr><td class="mono">${esc(r.rowid)}</td>` +
        vals.map(v => `<td>${esc(typeof v === "object" && v ? ("<ثنائي " + v._blob + " بايت>") : v)}</td>`).join("") +
        `</tr>`;
    }).join("");
    h += card(`جدول «${esc(t.name)}» — ${t.live_rows} سجل حيّ` +
      (t.forensic_hint ? ` <span class="pill">${esc(t.forensic_hint)}</span>` : ""),
      `<p class="mono muted" dir="ltr">${esc(t.sql || "")}</p>` +
      (rows ? tbl(["rowid", ...cols], rows) : "<p class='muted'>لا سجلات.</p>"));
  });
  if ((s.deleted_records || []).length) {
    h += card(`♻️ سجلات محذوفة مُستعادة (${s.deleted_count})`,
      tbl(["الموضع في الملف", "الصفحة", "المصدر", "القيم المستعادة"],
        s.deleted_records.map(d => `<tr>
          <td class="mono">${esc(d.offset_in_file)}</td>
          <td class="mono">${esc(d.page)}</td>
          <td>${esc(d.source)}${d.partial ? ' <span class="badge med">مبتور البداية</span>' : ""}</td>
          <td><b>${esc((d.values || []).map(v => typeof v === "object" && v ? ("<ثنائي " + v._blob + ">") : v).join(" | "))}</b></td>
        </tr>`).join("") ) +
      `<p class="muted">كل سجل مذكور بموضعه بالبايت داخل الملف ليتمكّن أي خبير مضاد
        من التحقق منه مباشرة.</p>`);
  }
  if ((s.text_fragments || []).length) {
    h += card(`🧩 شظايا نصية محذوفة (${s.text_fragment_count})`,
      tbl(["الموضع", "الصفحة", "المنطقة", "النص"], s.text_fragments.map(f =>
        `<tr><td class="mono">${esc(f.offset_in_file)}</td><td class="mono">${esc(f.page)}</td>
         <td>${esc(f.region)}</td><td><b>${esc(f.text)}</b></td></tr>`).join("")) +
      `<p class="muted">نصوص ناجية لم يُمكن نسبتها لصف بعينه بثقة — تُعرض كمحتوى
        محذوف مؤكد بلا ادعاء بمعرفة مصدره الدقيق.</p>`);
  }
  if (s.wal) {
    h += card("📄 ملف WAL", kvGrid({
      "عدد الإطارات": s.wal.frame_count, "صفحات متمايزة": s.wal.distinct_pages,
      "صفحات بعدة نسخ": s.wal.pages_with_multiple_versions,
      "معاملات مُثبَّتة": s.wal.committed_transactions,
      "إطارات من دورة سابقة": s.wal.stale_frames,
      "حجم الصفحة": s.wal.page_size,
    }) + `<p class="muted">${esc(s.wal.note || "")}</p>` +
      ((s.wal_records || []).length ? tbl(["المصدر", "القيم"], s.wal_records.map(r =>
        `<tr><td>${esc(r.source)}</td><td>${esc((r.values || []).map(v =>
          typeof v === "object" && v ? "<ثنائي>" : v).join(" | "))}</td></tr>`).join("")) : ""));
  }
  if (s.journal) h += card("📄 ملف journal", kvGrid(s.journal));
  if ((s.recovery_stats || null)) h += card("إحصاءات المسح", kvGrid(s.recovery_stats));
  el.innerHTML = h;
}

/* خريطة القضية */
async function openCaseMap() {
  const cid = $("#caseSelect").value;
  if (!cid) return showModal("🗺️ خريطة القضية", "<p class='muted'>اختر قضية أولًا.</p>");
  showModal("🗺️ خريطة القضية", "<p>جارٍ التجميع…</p>");
  const d = await (await fetch(`/api/cases/${cid}/map`)).json();
  const rows = (d.points || []).map(p => `<tr><td>${esc(p.label)}</td>
    <td class="mono">${esc((p.formats || {}).decimal)}</td>
    <td>${esc(p.source)}</td><td class="mono">${esc(p.confidence)}</td>
    <td><a class="btn ghost" target="_blank" rel="noopener"
      href="${esc(((p.formats || {}).links || {})["OpenStreetMap"])}">افتح</a></td></tr>`).join("");
  const cl = (d.clusters || []).map(c => `<li><b>${c.size} دليل</b> حول
     <span class="mono">${esc((c.formats || {}).decimal)}</span> — ${esc((c.members || []).join("، "))}</li>`).join("");
  $("#modalBody").innerHTML = `<p><b>${esc(d.verdict || "")}</b></p>
    ${cl ? `<h4>التجمّعات المكانية</h4><ul>${cl}</ul>` : ""}
    ${rows ? tbl(["الدليل", "الإحداثيات", "المصدر", "الثقة", ""], rows) : ""}`;
}

/* 3-ب) بصمة الجهاز من MakerNote */
function makerNoteCards() {
  const mn = REPORT.makernote || {};
  if (!mn.present && !(mn.standard_exif_identity && Object.keys(mn.standard_exif_identity).length))
    return mn.verdict ? card("🔧 بصمة الجهاز (MakerNote)", `<p class="muted">${esc(mn.verdict)}</p>`) : "";
  let h = "";
  if (mn.standard_exif_identity && Object.keys(mn.standard_exif_identity).length)
    h += card("🪪 محدِّدات الجهاز من EXIF القياسي", kvGrid(mn.standard_exif_identity));
  (mn.makernotes || []).forEach(m => {
    const title = `🔧 MakerNote · ${esc(m.vendor_ar || m.vendor || "غير معروف")}`;
    let b = `<p>${esc(mn.verdict)}</p>
      <div class="kv"><div><b>الحجم</b><span>${esc(m.size)} بايت</span></div>
      <div><b>مرجع الإزاحات</b><span>${esc(m.offset_base || "—")}</span></div>
      <div><b>ترتيب البايتات</b><span>${esc(m.byte_order || "—")}</span></div>
      <div><b>عدد الوسوم</b><span>${esc(m.tag_count || 0)}</span></div></div>
      <p class="mono muted" dir="ltr">${esc(m.header_ascii || "")} | ${esc(m.header_hex || "")}</p>`;
    if (!m.decoded) { h += card(title, b + `<p class="muted">${esc(m.reason || "")}</p>`); return; }
    const ident = Object.entries(m.identity || {}).filter(([k]) => !k.startsWith("_"));
    if (ident.length) b += tbl(["محدِّد الهوية", "القيمة", "الوسم"], ident.map(([k, v]) =>
      `<tr><td>${esc(k)}</td><td><b>${esc(fmt(v && v.value !== undefined ? v.value : v)).slice(0, 400)}</b></td>
       <td class="mono muted">${esc((v && v.tag) || "")}</td></tr>`).join(""));
    Object.entries(m.identity || {}).filter(([k]) => k.startsWith("_"))
      .forEach(([, v]) => { b += `<p class="muted">ℹ️ ${esc(fmt(v))}</p>`; });
    Object.entries(m.interpreted || {}).forEach(([sec, vals]) => {
      b += `<h4>${esc(sec)}</h4>` + kvGrid(vals);
    });
    b += `<h4>كل الوسوم المقروءة</h4>` + tbl(["الوسم", "النوع", "القيمة"],
      Object.entries(m.fields || {}).map(([k, f]) =>
        `<tr><td>${esc(k)} <span class="pill mono">${esc(f.tag)}</span></td>
         <td class="muted">${esc(f.type)}</td>
         <td>${esc(fmt(f.value)).slice(0, 300)}${f._rejected ? ` <span class="badge high">${esc(f._rejected)}</span>` : ""}</td></tr>`).join(""));
    h += card(title, b);
  });
  return h;
}

/* 4-ب) بصمة ضجيج المستشعر PRNU */
function tabPrnu() {
  const p = (REPORT.image_forensics || {}).prnu;
  const el = $("#tab-prnu");
  if (!el) return;
  if (!p || !p.ok) {
    el.innerHTML = card("بصمة ضجيج المستشعر (PRNU)",
      `<p class="muted">${esc((p && p.reason) || "غير متاح لهذا الملف (يلزم صورة نقطية ≥ 128×128).")}</p>`);
    return;
  }
  let h = card("🎯 ماذا تقيس هذه الصفحة؟",
    `<p>PRNU هو تفاوت مجهري في حساسية بكسلات المستشعر ناتج عن التصنيع. إنه
     <b>بصمة فيزيائية فريدة لكل كاميرا</b> مطبوعة في كل صورة تلتقطها، ولا تُزال
     بالضغط ولا بمسح الميتاداتا. هذه هي القدرة الوحيدة في المنظومة التي تربط صورة
     بـ<b>جهاز بعينه</b> لا بطراز فقط.</p>
     <p class="muted">المرجع: Lukáš–Fridrich–Goljan (IEEE TIFS 2006/2008) وإحصائية PCE (SPIE 2009).</p>`);

  h += card("خصائص بقايا الضجيج المستخرجة من هذه الصورة", kvGrid({
    "المقطع المستخدم": (p.crop_used || []).join(" × "),
    "أبعاد الصورة": (p.image_dims || []).join(" × "),
    "طاقة البقايا": p.residual_energy,
    "الانحراف المعياري للبقايا": p.residual_std,
    "الطاقة بعد إزالة متوسطات الصفوف/الأعمدة": p.residual_energy_after_zero_mean,
    "متوسط الشدة": p.mean_intensity,
    "نسبة البكسلات المشبعة": p.saturated_ratio,
    "نسبة البكسلات المظلمة": p.dark_ratio,
    "صالحة كصورة مرجعية لبناء بصمة": p.usable_as_reference ? "نعم ✅" : "لا (مشبعة/مظلمة/غير مناسبة)",
  }) + `<p class="muted">${esc(p.note)}</p>`);

  const idf = p.identification;
  if (idf) {
    const rows = (idf.results || []).map(r => `<tr>
      <td><b>${esc(r.camera_name || r.camera_id)}</b></td>
      <td class="mono">${r.ok ? (r.pce || 0).toFixed(1) : "—"}</td>
      <td class="mono">${r.ok ? (r.pce_best_shift || 0).toFixed(1) : "—"}</td>
      <td class="mono">${r.ok ? (r.ncc_at_zero_shift || 0).toFixed(4) : "—"}</td>
      <td>${esc(r.verdict || r.reason || "")}</td></tr>`).join("");
    h += card(`المطابقة مع الكاميرات المسجّلة (${idf.cameras_compared || 0})`,
      `<p><b>${esc(idf.verdict || "")}</b></p>` +
      (rows ? tbl(["الكاميرا", "PCE عند الإزاحة صفر", "PCE لأفضل إزاحة", "NCC", "الحكم"], rows) : "") +
      `<p class="muted">عتبات القرار: تطابق قوي ≥ 60 · ترجيح ≥ 25 · مؤشر ضعيف ≥ 10 ·
       مطابقة مع قصّ ≥ 150 (لأن البحث في كل الإزاحات يرفع الإحصائية).</p>`);
  }
  h += card("حدود معروفة (تُذكر صراحةً أمام الخبير المضاد)",
    `<ul>
      <li>تحديد الكاميرا يتطلب <b>بصمة مرجعية</b> مبنية من صور أخرى لنفس الجهاز — لا يمكن من صورة واحدة.</li>
      <li>تغيير الأبعاد (تصغير/تكبير) يُفقد المحاذاة؛ النسخة الحالية تقارن مقاطع بنفس الدقة فقط.</li>
      <li>الصور المشبعة أو المظلمة جدًا لا تحمل إشارة PRNU كافية (الإشارة ضربية في الشدة).</li>
      <li>الضغط الشديد جدًا والتصفية الرقمية يُضعفان الإشارة ويخفضان PCE.</li>
    </ul>`);
  el.innerHTML = h;
}

/* 4-ج) بصمة الضغط وجداول التكميم */
function tabQt() {
  const el = $("#tab-qt");
  if (!el) return;
  const c = REPORT.compression_signature;
  if (!c || !c.ok) {
    el.innerHTML = card("بصمة الضغط", `<p class="muted">${esc((c && c.reason) || "لا ينطبق (ليس ملف JPEG).")}</p>`);
    return;
  }
  const s = c.signature || {}, q = c.quantization || {};
  let h = card("🧬 ما هذه البصمة؟",
    `<p>جداول التكميم وهوفمان وترتيب المقاطع هي <b>توقيع المُرمِّز</b> الذي أنتج الملف.
     تبقى هذه البصمة سليمة <b>حتى لو مُسحت كل الميتاداتا</b>، لأنها جزء من بنية الضغط
     نفسها. هذا هو مبدأ عمل JPEGsnoop.</p>
     <p><b>${esc(c.verdict || "")}</b></p>`);

  h += card("التوقيع المقيس", kvGrid({
    "الجودة المقيسة": q.quality_estimate,
    "كل الجداول قياسية (IJG)": q.all_tables_standard_ijg ? "نعم" : "لا — جدول مخصّص",
    "تخفيض اللون": s.subsampling,
    "نوع الإطار": s.progressive ? "تقدمي (Progressive)" : "أساسي (Baseline)",
    "جداول هوفمان": s.huffman_standard ? "قياسية (Annex K)" : (s.huffman_optimized ? "مُحسَّنة" : "—"),
    "ترتيب مقاطع APP": (s.app_marker_order || []).join(" > ") || "لا شيء",
    "توقيع جداول التكميم": s.qt_signature,
    "توقيع هوفمان": s.huffman_signature,
    "التوقيع البنيوي": s.structure_signature,
    "التوقيع الكامل": s.full_signature,
  }));

  (q.tables || []).forEach(t => {
    const grid = `<table class="qt">${(t.grid_8x8 || []).map(r =>
      `<tr>${r.map(v => `<td class="mono">${v}</td>`).join("")}</tr>`).join("")}</table>`;
    h += card(`جدول ${t.table_id} — ${esc(t.role)} · الجودة ${esc(t.quality)}` +
      (t.exact_ijg_match ? " ✅ مطابق تمامًا لمقياس IJG" : ` ⚠️ غير قياسي (انحراف ${esc(t.max_deviation)})`),
      grid + `<p class="muted">${esc(t.note)}</p>` + kvGrid(t.stats || {}));
  });

  const inf = c.structural_inference || [];
  if (inf.length) h += card("استدلالات بنيوية مقيسة",
    `<ul>${inf.map(f => `<li><b>${esc(f.fact)}</b> — ${esc(f.detail)}
      <code class="mono">${esc(f.evidence)}</code></li>`).join("")}</ul>`);

  const m = c.database_match;
  if (m) {
    const mk = (arr, title) => arr && arr.length ? `<h4>${title}</h4>` + tbl(["المصدر", "التوثيق", "الجودة", "أُضيف"],
      arr.map(e => `<tr><td><b>${esc(e.source)}</b><div class="muted">${esc(e.notes || "")}</div></td>
        <td class="muted">${esc(e.provenance || "")}</td><td class="mono">${esc(e.quality)}</td>
        <td class="mono">${esc(e.added_utc || "")}</td></tr>`).join("")) : "";
    h += card(`المطابقة مع قاعدة البصمات (${m.database_size || 0} مُدخَلًا)`,
      `<p><b>${esc(m.verdict || "")}</b></p>` +
      mk(m.exact_matches, "تطابق تام للبصمة الكاملة") +
      mk(m.quant_table_matches, "تطابق جداول التكميم فقط") +
      (m.nearest && m.nearest.length ? `<h4>الأقرب (مسافة L1)</h4>` + tbl(["المصدر", "المسافة"],
        m.nearest.map(e => `<tr><td>${esc(e.source)}</td><td class="mono">${esc(e.distance)}</td></tr>`).join("")) : "") +
      `<p class="muted">لا تُنسب الصورة إلى جهة إلا بوجود عيّنة مرجعية موثّقة في القاعدة —
       أضف عيّنة من جهاز بحوزتك من زر «🧬 قاعدة بصمات الضغط».</p>`);
  }
  el.innerHTML = h;
}

/* قاعدة بصمات الضغط */
async function openSigs() {
  showModal("🧬 قاعدة بصمات الضغط (JPEG)", `<div id="sigBody">جارٍ التحميل…</div>`);
  await renderSigs();
}

async function renderSigs() {
  let d = { count: 0, signatures: [] };
  try { d = await (await fetch("/api/signatures")).json(); } catch (e) { }
  const user = d.signatures.filter(s => (s.origin || "").includes("المحقق"));
  const builtin = d.signatures.filter(s => !(s.origin || "").includes("المحقق"));
  const row = s => `<tr><td><b>${esc(s.source)}</b><div class="muted">${esc(s.provenance || "")}</div></td>
      <td class="mono">${esc(s.quality)}</td><td class="mono">${esc(s.subsampling || "")}</td>
      <td class="mono" style="font-size:11px">${esc((s.full_signature || "").slice(0, 12))}…</td>
      <td>${(s.origin || "").includes("المحقق") ? `<button class="btn ghost" data-sdel="${esc(s.full_signature)}">حذف</button>` : "—"}</td></tr>`;
  $("#sigBody").innerHTML = `
    <p class="muted">القاعدة تضم ${d.count} توقيعًا: ${builtin.length} مُولَّدة محليًا بمُرمِّز libjpeg
      (قابلة لإعادة التوليد بـ<code>tools/build_signature_db.py</code>) و${user.length} أضافها المحقق.
      <b>لا يُسجَّل هنا أي توقيع منسوب لجهة بلا عيّنة مرجعية موثّقة.</b></p>
    <h4>توقيعات المحقق</h4>
    ${user.length ? tbl(["المصدر / التوثيق", "الجودة", "تخفيض اللون", "التوقيع", ""], user.map(row).join(""))
      : "<p class='muted'>لا توجد بعد.</p>"}
    <hr><h4>تعلّم بصمة من عيّنة مرجعية</h4>
    <div class="dz-meta">
      <input id="sigName" placeholder="اسم المصدر (مثال: واتساب أندرويد 2.24 — صورة مُرسَلة)">
      <input id="sigProv" placeholder="توثيق العيّنة (إلزامي: الجهاز/الإصدار/كيف حصلت عليها)">
      <input id="sigNotes" placeholder="ملاحظات">
    </div>
    <p><input type="file" id="sigFile" accept="image/jpeg"></p>
    <button class="btn primary" id="sigAdd">استخراج البصمة وتسجيلها</button>
    <div id="sigMsg" class="muted"></div>
    <hr><details><summary>عرض التوقيعات المُرفقة (${builtin.length})</summary>
      ${tbl(["المصدر", "الجودة", "تخفيض اللون", "التوقيع", ""], builtin.map(row).join(""))}</details>`;
  $("#sigBody").querySelectorAll("[data-sdel]").forEach(b => b.onclick = async () => {
    await fetch("/api/signatures/" + b.dataset.sdel, { method: "DELETE" });
    renderSigs();
  });
  $("#sigAdd").onclick = async () => {
    const f = $("#sigFile").files[0], msg = $("#sigMsg");
    const name = $("#sigName").value.trim(), prov = $("#sigProv").value.trim();
    if (!name || !prov) { msg.textContent = "اسم المصدر وتوثيق العيّنة إلزاميان."; return; }
    if (!f) { msg.textContent = "اختر صورة JPEG مرجعية."; return; }
    const fd = new FormData();
    fd.append("source", name); fd.append("provenance", prov);
    fd.append("notes", $("#sigNotes").value); fd.append("file", f);
    msg.textContent = "جارٍ استخراج البصمة…";
    const r = await fetch("/api/signatures/learn", { method: "POST", body: fd });
    const j = await r.json();
    msg.textContent = r.ok ? `✅ سُجّلت بصمة «${j.source}» (جودة ${j.quality}).`
      : "خطأ: " + (j.detail || "تعذّر التسجيل");
    if (r.ok) renderSigs();
  };
}

/* سجل الكاميرات */
async function openCameras() {
  showModal("📷 سجل بصمات الكاميرات (PRNU)", `<div id="camBody">جارٍ التحميل…</div>`);
  await renderCameras();
}

async function renderCameras() {
  let list = [];
  try { list = await (await fetch("/api/prnu/cameras")).json(); } catch (e) { }
  const rows = list.map(c => `<tr>
      <td><b>${esc(c.name)}</b><div class="muted">${esc(c.notes || "")}</div></td>
      <td class="mono">${esc((c.dims || []).join("×"))}</td>
      <td class="mono">${esc(c.n_images)}</td>
      <td class="mono" style="font-size:11px">${esc((c.fingerprint_sha256 || "").slice(0, 16))}…</td>
      <td class="muted">${esc(c.created_utc || "")}</td>
      <td><button class="btn ghost" data-del="${esc(c.camera_id)}">حذف</button></td>
    </tr>`).join("");
  const body = $("#camBody");
  body.innerHTML = `
    <p class="muted">تُبنى بصمة الكاميرا من صور مرجعية مأخوذة بنفس الجهاز.
      الأفضل علميًا: 20–50 صورة <b>مسطّحة ساطعة</b> (سماء/حائط) بنفس الدقة وأقل ضغط.
      الصور لا تُحفَظ على الخادم — تُحفظ البصمة المستخرجة فقط.</p>
    ${list.length ? tbl(["الكاميرا", "أبعاد البصمة", "عدد الصور", "بصمة الملف", "تاريخ البناء", ""], rows)
      : "<p class='muted'>لا توجد كاميرات مسجّلة بعد.</p>"}
    <hr>
    <h4>تسجيل كاميرا جديدة</h4>
    <div class="dz-meta">
      <input id="camName" placeholder="اسم الكاميرا (مثال: آيفون المشتبه به — حرز 3)">
      <input id="camNotes" placeholder="ملاحظة / رقم الحرز">
      <input id="camCrop" type="number" value="1024" title="حجم المقطع المركزي بالبكسل">
    </div>
    <p><input type="file" id="camFiles" multiple accept="image/*"></p>
    <button class="btn primary" id="camAdd">بناء البصمة وتسجيل الكاميرا</button>
    <div id="camMsg" class="muted"></div>`;
  body.querySelectorAll("[data-del]").forEach(b => b.onclick = async () => {
    await fetch("/api/prnu/cameras/" + b.dataset.del, { method: "DELETE" });
    renderCameras();
  });
  $("#camAdd").onclick = async () => {
    const files = $("#camFiles").files;
    const name = $("#camName").value.trim();
    const msg = $("#camMsg");
    if (!name) { msg.textContent = "اكتب اسم الكاميرا أولًا."; return; }
    if (!files || files.length < 2) { msg.textContent = "اختر صورتين على الأقل من نفس الكاميرا."; return; }
    const fd = new FormData();
    fd.append("name", name);
    fd.append("notes", $("#camNotes").value);
    fd.append("crop", $("#camCrop").value || "1024");
    for (const f of files) fd.append("files", f);
    msg.textContent = `جارٍ استخراج بقايا الضجيج من ${files.length} صورة وبناء البصمة…`;
    try {
      const r = await fetch("/api/prnu/cameras", { method: "POST", body: fd });
      const j = await r.json();
      if (!r.ok) { msg.textContent = "خطأ: " + (j.detail || "تعذّر البناء"); return; }
      msg.textContent = `✅ سُجّلت «${j.name}» من ${j.n_images} صورة.`;
      renderCameras();
    } catch (e) { msg.textContent = "خطأ في الاتصال: " + e; }
  };
}

/* 4) الاسترجاع */
function tabRecovery() {
  const r = REPORT.recovery || {};
  let h = card("الحكم على حالة البيانات الوصفية",
    (r.verdict || []).length ? `<ul>${r.verdict.map(v => `<li>${esc(v)}</li>`).join("")}</ul>`
      : "<p class='muted'>لا ملاحظات.</p>");

  (r.exif_fragments || []).forEach((f, i) => {
    h += card(`شظية EXIF #${i + 1} — إزاحة ${f.offset} · ${f.fields_recovered} حقلًا مستعادًا`,
      `<p class="muted">${esc(f.container)} · ترتيب البايت: ${esc(f.byte_order)}${f.makernote_present ? " · يحتوي MakerNote" : ""}</p>`
      + tbl(["الحقل", "القيمة"], Object.entries(f.fields).map(([k, v]) =>
        `<tr><td>${esc(k)}</td><td>${esc(fmt(v)).slice(0, 300)}</td></tr>`).join(""))
      + (f.gps ? `<h4>📍 موقع مُستعاد</h4>${kvGrid(f.gps)}` : ""));
  });

  (r.xmp_packets || []).forEach((p, i) => {
    h += card(`حزمة XMP #${i + 1} — إزاحة ${p.offset} (${esc(p.kind)})`,
      kvGrid(p.parsed?.key_fields || {}) +
      `<details><summary class="muted">عرض XMP الخام</summary><pre class="json">${esc((p.xmp || "").slice(0, 30000))}</pre></details>`);
  });

  if ((r.embedded_images || []).length) {
    h += card(`صور مدمجة مستخرجة (${r.embedded_images.length})`,
      `<p class="muted">المصغّرات والمعاينات المدمجة قد تُظهر المشهد قبل القص أو التعديل، وقد تحمل EXIF خاصًا بها.</p>
      <div class="gallery">` + r.embedded_images.map(e => `
        <figure>${e.file ? `<img src="${art(e.file)}">` : ""}
        <figcaption>إزاحة ${e.offset} · ${e.size} بايت · ${e.width || "?"}×${e.height || "?"}
        ${e.info?.gps ? `<br>📍 <a target="_blank" href="${esc(e.info.gps.google_maps)}">موقع مستعاد</a>` : ""}
        ${e.info?.exif ? `<br><span class="pill">${Object.keys(e.info.exif).length} حقل EXIF</span>` : ""}</figcaption></figure>`).join("") + "</div>");
    r.embedded_images.forEach((e, i) => {
      if (e.info?.exif) h += card(`EXIF داخل الصورة المدمجة #${i + 1}`,
        tbl(["الحقل", "القيمة"], Object.entries(e.info.exif).map(([k, v]) =>
          `<tr><td>${esc(k)}</td><td>${esc(fmt(v)).slice(0, 300)}</td></tr>`).join("")));
    });
  }
  if ((r.icc_profiles || []).length)
    h += card("ملفات تعريف ICC مكتشفة داخل البايتات", r.icc_profiles.map(p => kvGrid(p)).join(""));
  if ((r.photoshop_irb || []).length)
    h += card("كتل Photoshop IRB", r.photoshop_irb.map(p =>
      tbl(["المعرّف", "الاسم", "الحجم"], p.blocks.map(b =>
        `<tr><td class="mono">${esc(b.id)}</td><td>${esc(b.name)}</td><td>${b.size}</td></tr>`).join("")) +
      (Object.keys(p.IPTC || {}).length ? kvGrid(p.IPTC) : "")).join(""));
  if ((r.source_fingerprint || []).length)
    h += card("🧬 بصمة المصدر (حتى بلا ميتاداتا)",
      `<ul>${r.source_fingerprint.map(s => `<li>${esc(s)}</li>`).join("")}</ul>`);
  $("#tab-recovery").innerHTML = h;
}

/* 5) تحليل الصورة */
function tabImage() {
  const f = REPORT.image_forensics;
  if (!f) { $("#tab-image").innerHTML = "<p class='muted'>الدليل ليس صورة — لا ينطبق هذا التحليل.</p>"; return; }
  let h = card("خصائص الصورة", kvGrid(f.basic));
  const imgs = [];
  if (f.preview) imgs.push(["الصورة الأصلية (معاينة)", f.preview]);
  if (f.ela?.image) imgs.push([`ELA (جودة ${f.ela.quality_used}) — ${f.ela.regions_found} منطقة شاذة`, f.ela.image]);
  if (f.noise?.noise_map) imgs.push(["خريطة الضجيج المناطقية", f.noise.noise_map]);
  if (f.noise?.residual_image) imgs.push(["بقايا الضجيج (High-pass)", f.noise.residual_image]);
  if (f.thumbnail_check?.thumbnail_image) imgs.push(["المصغّرة المدمجة الأصلية", f.thumbnail_check.thumbnail_image]);
  if (f.thumbnail_check?.diff_image) imgs.push(["فرق المصغّرة عن الصورة الحالية", f.thumbnail_check.diff_image]);
  (f.jpeg_ghosts?.images || []).forEach((im, i) =>
    imgs.push([`شبح JPEG عند جودة ${f.jpeg_ghosts.per_quality[i]?.quality}`, im]));
  h += card("المخرجات البصرية", `<div class="gallery">` + imgs.map(([l, im]) =>
    `<figure><img src="${art(im)}" onclick="lightbox(this.src)"><figcaption>${esc(l)}</figcaption></figure>`).join("") + `</div>`);

  if (f.thumbnail_check?.applicable) h += card("مطابقة المصغّرة المدمجة ↔ الصورة",
    `<ul>${f.thumbnail_check.verdict.map(v => `<li>${esc(v)}</li>`).join("")}</ul>` +
    kvGrid({ "الارتباط": f.thumbnail_check.correlation, "MSE": f.thumbnail_check.mse, "أبعاد المصغّرة": f.thumbnail_check.thumbnail_size }));
  if (f.ela) h += card("تحليل مستوى الخطأ (ELA)",
    kvGrid({ "متوسط الخطأ": f.ela.mean_error, "أقصى خطأ": f.ela.max_error, "مناطق مشبوهة": f.ela.regions_found }) +
    `<p class="muted">${esc(f.ela.interpretation)}</p>` +
    (f.ela.suspect_regions?.length ? tbl(["x", "y", "الحجم", "z-score"], f.ela.suspect_regions.map(r =>
      `<tr><td>${r.x}</td><td>${r.y}</td><td>${r.w}×${r.h}</td><td>${r.z_score}</td></tr>`).join("")) : ""));
  if (f.double_compression?.applicable) h += card("كشف الضغط المزدوج (DCT)",
    `<p><b>${esc(f.double_compression.verdict)}</b></p><p class="muted">${esc(f.double_compression.method)}</p>` +
    tbl(["المعامل", "عيّنات", "دور (خانات)", "درجة الدورية", "نسبة الفجوات", "دوري؟"], f.double_compression.coefficients.map(c =>
      `<tr><td class="mono">${esc(c.coefficient)}</td><td>${c.samples}</td><td>${c.period_bins}</td>
       <td>${c.periodicity_score}</td><td>${c.gap_ratio}</td>
       <td>${c.periodic ? "✅ نعم" : "—"}</td></tr>`).join("")) +
    (f.double_compression.limitation ? `<p class="muted">${esc(f.double_compression.limitation)}</p>` : "") +
    (f.coefficient_statistics?.applicable ? card("قانون بنفورد المعمّم على معاملات DCT",
      kvGrid({ "المسافة عن النموذج الملائم": f.coefficient_statistics.generalized_benford_fit?.total_variation,
        "q": f.coefficient_statistics.generalized_benford_fit?.q, "s": f.coefficient_statistics.generalized_benford_fit?.s,
        "معاملات AC غير صفرية": f.coefficient_statistics.nonzero_ac_coefficients,
        "التفسير": f.coefficient_statistics.interpretation }) ) : ""));
  if (f.jpeg_ghosts) h += card("أشباح JPEG",
    `<p class="muted">${esc(f.jpeg_ghosts.interpretation)}</p>` +
    kvGrid({ "جودة آخر حفظ المقدّرة": f.jpeg_ghosts.estimated_last_save_quality }) +
    tbl(["الجودة", "متوسط الخطأ", "التباين المكاني"], (f.jpeg_ghosts.per_quality || []).map(q =>
      `<tr><td>${q.quality}</td><td>${q.mean_sq_error}</td><td>${q.spatial_variation}</td></tr>`).join("")));
  if (f.copy_move?.applicable) h += card("كشف النسخ واللصق الداخلي",
    `<p><b class="${f.copy_move.detected ? "badge crit" : ""}">${esc(f.copy_move.interpretation)}</b></p>
     <p class="muted">${esc(f.copy_move.method)}</p>` +
    tbl(["متجه الإزاحة", "عدد الكتل المتطابقة"], (f.copy_move.top_shift_vectors || []).map(s =>
      `<tr><td class="mono">${esc(JSON.stringify(s.shift))}</td><td>${s.matching_blocks}</td></tr>`).join("")));
  if (f.noise) h += card("تحليل الضجيج",
    kvGrid({ "انحراف الضجيج العام": f.noise.global_noise_sigma, "مؤشر التجانس": f.noise.noise_uniformity_index, "مناطق شاذة": (f.noise.anomalous_regions || []).length }) +
    `<p class="muted">${esc(f.noise.interpretation)}</p>` +
    ((f.noise.anomalous_regions || []).length ? tbl(["x", "y", "z-score", "النوع"], f.noise.anomalous_regions.map(r =>
      `<tr><td>${r.x}</td><td>${r.y}</td><td>${r.z_score}</td><td>${esc(r.type)}</td></tr>`).join("")) : ""));
  if (f.histogram) {
    h += card("المدرج التكراري", kvGrid({
      "ملاحظة المشط": f.histogram.comb_artifact?.note,
      "حدّة (تباين التدرج)": f.histogram.sharpness_laplacian_var,
      "مستويات رمادية فريدة": f.histogram.unique_gray_levels
    }) + Object.entries(f.histogram.channels || {}).map(([c, v]) =>
      `<h4>القناة ${c}</h4>` + kvGrid({ "المتوسط": v.mean, "الانحراف": v.std, "قصّ أسود %": v.clipped_black_pct, "قصّ أبيض %": v.clipped_white_pct, "خانات فارغة": v.empty_bins }) +
      `<div class="bars">${histBars(v.histogram)}</div>`).join(""));
  }
  $("#tab-image").innerHTML = h;
}

function histBars(hist) {
  const mx = Math.max(...hist) || 1;
  return hist.map(v => `<i style="height:${(v / mx * 100).toFixed(1)}%"></i>`).join("");
}

/* 6) الإخفاء */
function tabSteg() {
  const s = REPORT.image_forensics?.steganalysis;
  if (!s) { $("#tab-steg").innerHTML = "<p class='muted'>تحليل الإخفاء ينطبق على الصور النقطية فقط.</p>"; return; }
  let h = card("الخلاصة", `<ul>${s.verdict.map(v => `<li>${esc(v)}</li>`).join("")}</ul><p class="muted">${esc(s.note)}</p>`);
  h += card("مستويات البت الأدنى (LSB)", `<div class="gallery">` +
    Object.entries(s.bit_plane_images).map(([c, f]) =>
      `<figure><img src="${art(f)}" onclick="lightbox(this.src)"><figcaption>القناة ${c}</figcaption></figure>`).join("") +
    `</div><p class="muted">ظهور نص أو أشكال هندسية واضحة في هذه الصور = دليل مباشر على بيانات مخفية.</p>`);
  h += card("اختبار كاي-تربيع (Westfeld & Pfitzmann)", kvGrid({
    "الكتل المفحوصة": s.chi_square.blocks_tested, "كتل مشبوهة": s.chi_square.suspicious_blocks,
    "النسبة المشبوهة": s.chi_square.suspicious_fraction, "المنهجية": s.chi_square.method
  }));
  h += card("تحليل RS (Fridrich)", kvGrid(s.rs_analysis));
  h += card("متوسط البت الأدنى لكل قناة", kvGrid(s.lsb_mean_per_channel) +
    `<p class="muted">القيمة الطبيعية للصور غير المعدّلة تقترب من 0.5 لكنها ليست دليلًا بمفردها.</p>`);
  const ent = REPORT.entropy || {};
  h += card("دلائل إحصائية مساندة", kvGrid({
    "إنتروبيا الملف": ent.shannon_bits_per_byte, "الحكم": ent.verdict,
    "كاي-تربيع العام": ent.chi_square?.chi2, "الارتباط التسلسلي": ent.serial_correlation
  }));
  $("#tab-steg").innerHTML = h;
}

/* 7) البنية */
function tabStruct() {
  const c = REPORT.containers || {};
  let h = card("تعريف النوع", kvGrid(REPORT.type || {}));
  if (c.jpeg) {
    h += card("مقاطع JPEG", tbl(["المقطع", "الإزاحة", "الحجم", "الوصف"],
      c.jpeg.segments.map(s => `<tr><td class="mono">${esc(s.marker)}</td><td class="mono">${s.offset}</td>
        <td>${s.size}</td><td>${esc(s.desc)}</td></tr>`).join("")) +
      kvGrid({ "الجودة المقدّرة": c.jpeg.estimated_jpeg_quality, "بصمة جداول التكميم": c.jpeg.quant_fingerprint, ...(c.jpeg.frame || {}) }));
    if (c.jpeg.trailing_data) h += card("⚠️ بيانات بعد نهاية الصورة", kvGrid(c.jpeg.trailing_data));
    (c.jpeg.quant_tables || []).forEach(t => {
      h += card(`جدول تكميم #${t.table_id} — جودة مقدّرة ${t.estimated_quality}`,
        `<div class="hexview">${qtGrid(t.values)}</div>`);
    });
  }
  if (c.png) h += card("كتل PNG", tbl(["النوع", "الإزاحة", "الطول", "CRC", "الوصف"],
    c.png.chunks.map(k => `<tr><td class="mono">${esc(k.type)}</td><td class="mono">${k.offset}</td><td>${k.length}</td>
      <td>${k.crc_ok ? "✅" : "❌ غير مطابق"}</td><td>${esc(k.desc)}</td></tr>`).join("")) +
    (Object.keys(c.png.text || {}).length ? kvGrid(c.png.text) : ""));
  if (c.gif) h += card("GIF", kvGrid({ ...c.gif.screen, "عدد الإطارات": c.gif.frames, "تعليقات": (c.gif.comments || []).join(" | ") }));
  if (c.riff) h += card("RIFF/WebP", kvGrid({ ...c.riff.metadata, "الصيغة": c.riff.form, "الحجم المعلن": c.riff.declared_size, "الحجم الفعلي": c.riff.actual_size }) +
    tbl(["الكتلة", "الإزاحة", "الحجم"], c.riff.chunks.map(k => `<tr><td class="mono">${esc(k.id)}</td><td>${k.offset}</td><td>${k.size}</td></tr>`).join("")));
  if (c.iso_bmff) h += card("صناديق ISO-BMFF (MP4/MOV/HEIC)",
    tbl(["المسار", "الإزاحة", "الحجم", "الوصف"], c.iso_bmff.boxes.slice(0, 400).map(b =>
      `<tr><td class="mono">${esc(b.path)}</td><td class="mono">${b.offset}</td><td>${b.size}</td><td>${esc(b.desc)}</td></tr>`).join("")) +
    kvGrid(flatten(c.iso_bmff.metadata)));
  if (c.pdf) h += card("بنية PDF", kvGrid({
    "الإصدار": c.pdf.version, "عدد الكائنات": c.pdf.objects_declared, "التيارات": c.pdf.streams,
    "علامات EOF": c.pdf.eof_markers, "تحديثات تزايدية": c.pdf.incremental_updates,
    "صفحات (تقدير)": c.pdf.page_count_estimate, "مشفّر": c.pdf.encrypted, "موقّع": c.pdf.signed
  }) + (c.pdf.incremental_note ? `<p class="badge high">${esc(c.pdf.incremental_note)}</p>` : "") +
    (c.pdf.risk_indicators?.length ? tbl(["العنصر", "التكرار", "الخطر"], c.pdf.risk_indicators.map(r =>
      `<tr><td class="mono">${esc(r.marker)}</td><td>${r.count}</td><td>${esc(r.risk)}</td></tr>`).join("")) : "") +
    (c.pdf.fonts?.length ? `<h4>الخطوط</h4><div class="chips">${c.pdf.fonts.map(f => `<span class="chip">${esc(f)}</span>`).join("")}</div>` : ""));
  if (c.ooxml_zip) h += card("مستند OOXML / أرشيف ZIP",
    kvGrid({ "النوع": c.ooxml_zip.kind, "عدد الإدخالات": c.ooxml_zip.entry_count, "ماكرو": c.ooxml_zip.has_macros, "تعديلات متتبّعة": c.ooxml_zip.tracked_changes }) +
    (c.ooxml_zip.metadata ? kvGrid(c.ooxml_zip.metadata) : "") +
    tbl(["الإدخال", "الحجم", "مضغوط", "التعديل", "CRC"], (c.ooxml_zip.entries || []).slice(0, 300).map(e =>
      `<tr><td class="mono">${esc(e.name)}</td><td>${e.size}</td><td>${e.compressed}</td>
       <td class="mono">${esc(e.modified)}</td><td class="mono">${esc(e.crc32)}</td></tr>`).join("")) +
    (c.ooxml_zip.text_preview ? card("معاينة النص", `<p>${esc(c.ooxml_zip.text_preview)}</p>`) : ""));
  if (c.audio_tags) h += card("وسوم الصوت", kvGrid({ ...(c.audio_tags.stream_info || {}), ...(c.audio_tags.tags || {}) }));
  $("#tab-struct").innerHTML = h;
}

function qtGrid(v) {
  let s = "";
  for (let i = 0; i < 64; i += 8) s += v.slice(i, i + 8).map(x => String(x).padStart(4)).join("") + "\n";
  return `<div class="hexrow">${esc(s)}</div>`;
}
function flatten(o, p = "") {
  const out = {};
  for (const k in (o || {})) {
    const v = o[k];
    if (v && typeof v === "object" && !Array.isArray(v)) Object.assign(out, flatten(v, p + k + "."));
    else out[p + k] = Array.isArray(v) ? v.join(", ") : v;
  }
  return out;
}

/* 8) النحت */
function tabCarve() {
  const c = REPORT.carving || [];
  $("#tab-carve").innerHTML = card(`الملفات المدمجة المكتشفة (${c.length})`,
    `<p class="muted">يُفحص الملف بايتًا بايتًا بحثًا عن توقيعات ملفات أخرى مدفونة بداخله، وتُستخرج فعليًا للتحميل.</p>` +
    (c.length ? tbl(["النوع", "الوصف", "الإزاحة", "الحجم", "SHA-256", "تحميل"], c.map(x =>
      `<tr><td>${esc(x.type)}</td><td>${esc(x.description)}</td><td class="mono">${x.offset}</td>
       <td>${x.size ?? "—"}</td><td class="mono">${esc((x.sha256 || "").slice(0, 24))}</td>
       <td>${x.file ? `<a href="${art(x.file)}" download>⬇ تنزيل</a>` : (x.note ? esc(x.note) : "—")}</td></tr>`).join(""))
      : "<p class='muted'>لا توجد ملفات مدمجة.</p>"));
}

/* 9) النصوص */
function tabStrings() {
  const s = REPORT.strings || {};
  let h = "";
  const iocs = s.iocs || {};
  h += card("مؤشرات مستخرجة (IOC)", Object.keys(iocs).length ? Object.entries(iocs).map(([k, v]) =>
    `<h4>${esc(k)} <span class="pill">${v.length}</span></h4><div class="chips">${v.slice(0, 120).map(x => `<span class="chip">${esc(x)}</span>`).join("")}</div>`).join("")
    : "<p class='muted'>لا توجد مؤشرات.</p>");
  const hints = s.hints || {};
  if ((hints["أجهزة محتملة"] || []).length || (hints["برمجيات محتملة"] || []).length)
    h += card("آثار أجهزة وبرمجيات داخل البايتات", Object.entries(hints).map(([k, v]) =>
      v.length ? `<h4>${esc(k)}</h4><div class="chips">${v.map(x => `<span class="chip">${esc(x)}</span>`).join("")}</div>` : "").join(""));
  if (s.arabic_text_blob) h += card("نص عربي مستخرج", `<pre class="json" style="direction:rtl;text-align:right">${esc(s.arabic_text_blob)}</pre>`);
  const a = s.strings?.ascii || [];
  h += card(`سلاسل ASCII (${s.strings?.counts?.ascii || 0})`,
    tbl(["الإزاحة", "النص"], a.slice(0, 600).map(x => `<tr><td class="mono">${x.offset}</td><td class="mono">${esc(x.text)}</td></tr>`).join("")));
  const u = s.strings?.utf16le || [];
  if (u.length) h += card(`سلاسل UTF-16LE (${u.length})`,
    tbl(["الإزاحة", "النص"], u.slice(0, 400).map(x => `<tr><td class="mono">${x.offset}</td><td>${esc(x.text)}</td></tr>`).join("")));
  $("#tab-strings").innerHTML = h;
}

/* 10) الخط الزمني */
function tabTimeline() {
  const t = REPORT.timeline || {};
  let h = "";
  if ((t.conflicts || []).length) h += card("⚠️ تضاربات زمنية",
    tbl(["الخطورة", "الحدث", "الوصف"], t.conflicts.map(c =>
      `<tr><td>${esc(c.severity)}</td><td>${esc(c.event)}</td><td>${esc(c.issue)}</td></tr>`).join("")));
  h += card(`الأحداث الزمنية (${(t.events || []).length})`, (t.events || []).length ?
    kvGrid({ "الأقدم": t.earliest?.parsed, "الأحدث": t.latest?.parsed, "المدى": t.span_human }) +
    tbl(["الوقت", "الحدث", "المصدر"], t.events.map(e =>
      `<tr><td class="mono">${esc(e.parsed)}</td><td>${esc(e.label)}</td><td class="muted">${esc(e.source)}</td></tr>`).join(""))
    : `<p class="muted">${esc(t.note || "لا توجد طوابع زمنية.")}</p>`);
  $("#tab-timeline").innerHTML = h;
}

/* 11) العشوائية */
function tabEntropy() {
  const e = REPORT.entropy || {};
  const map = e.map || [];
  const mx = 8;
  $("#tab-entropy").innerHTML =
    card("قياسات العشوائية", kvGrid({
      "إنتروبيا شانون (بت/بايت)": e.shannon_bits_per_byte, "المعياري": e.normalized, "الحكم": e.verdict,
      "كاي-تربيع": e.chi_square?.chi2, "تفسير كاي-تربيع": e.chi_square?.interpretation,
      "تقدير π (مونت كارلو)": e.monte_carlo?.pi_estimate, "خطأ π %": e.monte_carlo?.error_percent,
      "الارتباط التسلسلي": e.serial_correlation
    })) +
    card("خريطة الإنتروبيا على طول الملف",
      `<div class="bars" style="height:160px">${map.map(b =>
        `<i title="إزاحة ${b.offset} — ${b.entropy}" style="height:${(b.entropy / mx * 100).toFixed(1)}%;
         background:linear-gradient(180deg,${b.entropy > 7.5 ? "#ff6b6b" : b.entropy > 6 ? "#e3b341" : "#58a6ff"},#13243c)"></i>`).join("")}</div>
       <p class="muted">القمم الحمراء = مناطق شبه عشوائية (تشفير/ضغط/حمولة مخفية).</p>`) +
    ((e.anomalies || []).length ? card("مناطق شاذة",
      tbl(["الإزاحة", "الحجم", "الإنتروبيا", "الملاحظة"], e.anomalies.map(a =>
        `<tr><td class="mono">${a.offset}</td><td>${a.size}</td><td>${a.entropy}</td><td>${esc(a.note)}</td></tr>`).join(""))) : "");
}

/* 12) الهيكس */
let hexOffset = 0;
function tabHex() {
  $("#tab-hex").innerHTML = card("عارض الهيكس (قراءة مباشرة من النسخة المحفوظة للدليل)", `
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px">
      <input id="hexOff" type="number" value="0" style="width:160px" placeholder="الإزاحة">
      <input id="hexLen" type="number" value="1024" style="width:120px" placeholder="الطول">
      <button class="btn" id="hexGo">اذهب</button>
      <button class="btn ghost" id="hexPrev">◀ السابق</button>
      <button class="btn ghost" id="hexNext">التالي ▶</button>
      <span class="muted" id="hexInfo"></span>
    </div><div class="hexview" id="hexOut">…</div>`);
  $("#hexGo").onclick = () => loadHex(parseInt($("#hexOff").value) || 0, parseInt($("#hexLen").value) || 1024);
  $("#hexPrev").onclick = () => { const l = parseInt($("#hexLen").value) || 1024; loadHex(Math.max(0, hexOffset - l), l); };
  $("#hexNext").onclick = () => { const l = parseInt($("#hexLen").value) || 1024; loadHex(hexOffset + l, l); };
  loadHex(0, 1024);
}
async function loadHex(off, len) {
  const d = await (await fetch(`/api/evidence/${EID}/hex?offset=${off}&length=${len}`)).json();
  hexOffset = d.offset;
  $("#hexOff").value = d.offset;
  $("#hexInfo").textContent = `حجم الملف: ${d.file_size} بايت`;
  $("#hexOut").innerHTML = d.lines.map(l =>
    `<div class="hexrow"><span class="hexoff">${l.offset.toString(16).padStart(8, "0")}</span>  <span class="hexb">${esc(l.hex.padEnd(47))}</span>  <span class="hexa">${esc(l.ascii)}</span></div>`).join("");
}

/* 13) JSON */
function tabRaw() {
  $("#tab-raw").innerHTML = card("التقرير الكامل (JSON)",
    `<pre class="json">${esc(JSON.stringify(REPORT, null, 1).slice(0, 400000))}</pre>`);
}

/* أدوات */
window.lightbox = (src) => {
  const d = document.createElement("div");
  d.className = "lightbox";
  d.innerHTML = `<img src="${src}">`;
  d.onclick = () => d.remove();
  document.body.appendChild(d);
};
function showModal(title, body) {
  $("#modalTitle").innerHTML = title;
  $("#modalBody").innerHTML = body;
  $("#modal").classList.remove("hidden");
}
function closeModal() { $("#modal").classList.add("hidden"); }
$("#modalClose").onclick = closeModal;
$("#btnVerify").onclick = async () => {
  const v = await (await fetch(`/api/evidence/${EID}/verify`)).json();
  showModal("التحقق من سلامة الدليل", `<p class="${v.ok ? "badge ok" : "badge crit"}">
    ${v.ok ? "✅ الدليل سليم — البصمة المحسوبة تطابق المسجّلة وقت الاستلام" : "❌ تعارض في البصمة — تم تغيير النسخة المخزّنة!"}</p>
    ${kvGrid(v)}`);
};
loadCases();
