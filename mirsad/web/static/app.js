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

  tabSummary(); tabHashes(); tabMeta(); tabRecovery(); tabImage(); tabSteg();
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
  $("#tab-meta").innerHTML =
    card("كل الحقول الوصفية المستخرجة", rows ? tbl(["الحقل", "القيمة", "المصدر"], rows)
      : "<p class='muted'>لا توجد بيانات وصفية قياسية — انتقل لتبويب «الاسترجاع».</p>") + extra;
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
