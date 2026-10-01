"""
توليد تقرير جنائي مستقل (HTML قابل للطباعة/التصدير كـ PDF من المتصفح) + ملخص نصي.
التقرير يحتوي الأدلة الخام (بصمات، إزاحات بايتية، قيم إحصائية) ليكون قابلًا للتدقيق.
"""
from __future__ import annotations

import html
import json
from datetime import datetime, timezone


def _esc(x) -> str:
    return html.escape(str(x)) if x is not None else ""


def _kv_table(d: dict, cols=("المفتاح", "القيمة")) -> str:
    if not d:
        return "<p class='muted'>لا توجد بيانات.</p>"
    rows = []
    for k, v in d.items():
        if isinstance(v, dict) and "value" in v and "source" in v:
            rows.append(f"<tr><td>{_esc(k)}</td><td>{_esc(_short(v['value']))}</td>"
                        f"<td class='src'>{_esc(v['source'])}</td></tr>")
        else:
            rows.append(f"<tr><td>{_esc(k)}</td><td colspan='2'>{_esc(_short(v))}</td></tr>")
    return (f"<table><thead><tr><th>{cols[0]}</th><th>{cols[1]}</th><th>المصدر</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>")


def _short(v, n: int = 400) -> str:
    if isinstance(v, (dict, list)):
        s = json.dumps(v, ensure_ascii=False)
    else:
        s = str(v)
    return s if len(s) <= n else s[:n] + " …"


SEV_CLASS = {"حرجة": "critical", "عالية": "high", "متوسطة": "medium",
             "منخفضة": "low", "معلوماتية": "info"}


def html_report(rep: dict, case: dict | None = None, evidence: dict | None = None,
                custody: list | None = None, artifacts_base: str = "") -> str:
    ev = rep.get("evidence", {})
    fp = rep.get("fingerprints", {})
    asmt = rep.get("assessment", {})
    t = rep.get("type", {})

    findings = "".join(
        f"<div class='finding {SEV_CLASS.get(f['severity'], 'info')}'>"
        f"<div class='fh'><span class='sev'>{_esc(f['severity'])}</span>"
        f"<strong>{_esc(f['title'])}</strong><span class='w'>وزن {f['weight']}</span></div>"
        f"<p>{_esc(f['detail'])}</p><code>{_esc(f['evidence'])}</code></div>"
        for f in asmt.get("findings", []))
    if not findings:
        findings = "<p class='muted'>لم تُرصد مؤشرات.</p>"

    tl = rep.get("timeline", {})
    tl_rows = "".join(
        f"<tr><td>{_esc(e.get('parsed'))}</td><td>{_esc(e.get('label'))}</td>"
        f"<td class='src'>{_esc(e.get('source'))}</td></tr>" for e in tl.get("events", []))
    conflicts = "".join(f"<li><b>{_esc(c['severity'])}:</b> {_esc(c['issue'])}</li>"
                        for c in tl.get("conflicts", []))

    rec = rep.get("recovery", {})
    rec_html = ""
    for frag in rec.get("exif_fragments", []):
        rec_html += (f"<h4>شظية EXIF عند الإزاحة {frag['offset']} "
                     f"({_esc(frag.get('container'))}) — {frag['fields_recovered']} حقلًا</h4>"
                     + _kv_table({k: v for k, v in list(frag["fields"].items())[:80]}))
        if frag.get("gps"):
            rec_html += _kv_table(frag["gps"])
    for pkt in rec.get("xmp_packets", [])[:5]:
        kf = pkt.get("parsed", {}).get("key_fields", {})
        rec_html += f"<h4>حزمة XMP عند {pkt['offset']} ({_esc(pkt['kind'])})</h4>" + _kv_table(kf)
    if rec.get("verdict"):
        rec_html = "<ul>" + "".join(f"<li>{_esc(v)}</li>" for v in rec["verdict"]) + "</ul>" + rec_html
    if not rec_html:
        rec_html = "<p class='muted'>لم يُعثر على آثار وصفية مستعادة.</p>"

    # ---- الموقع الجغرافي
    gl = rep.get("geolocation") or {}
    geo_html = f"<p><b>{_esc(gl.get('verdict') or 'لم يُفحص.')}</b></p>"
    gp = gl.get("primary")
    if gp:
        gf = gp.get("formats") or {}
        geo_html += _kv_table({
            "الإحداثيات (عشري)": gf.get("decimal"),
            "درجات/دقائق/ثوانٍ": gf.get("dms"),
            "ISO 6709": gf.get("iso_6709"),
            "Plus Code": gf.get("plus_code"),
            "Geohash": gf.get("geohash"),
            "منطقة UTM": (gf.get("utm") or {}).get("label"),
            "فرق التوقيت المحسوب من خط الطول":
                "UTC%+d" % ((gf.get("timezone") or {}).get("estimated_utc_offset") or 0),
            "الارتفاع (م)": gp.get("altitude_m"),
            "نوع التثبيت": gp.get("fix_type"),
            "حالة الإشارة": gp.get("status_meaning") or gp.get("status"),
            "عدد الأقمار": gp.get("satellites"),
            "DOP": gp.get("dop"),
            "الخطأ الأفقي (م)": gp.get("horizontal_error_m"),
            "السرعة (كم/س)": gp.get("speed_kmh"),
            "اتجاه الكاميرا": gp.get("camera_direction_text"),
            "تاريخ/وقت GPS (UTC)": " ".join(
                str(x) for x in (gp.get("gps_date_utc"), gp.get("gps_time_utc")) if x),
            "مرجع الإسناد": gp.get("map_datum"),
            "المصدر": gp.get("source"),
            "ثقة الموقع": f"{(gp.get('confidence') or {}).get('level')} "
                           f"({(gp.get('confidence') or {}).get('score')}/100) — "
                           + "، ".join((gp.get("confidence") or {}).get("reasons") or []),
        })
        links = gf.get("links") or {}
        geo_html += "<p>" + " · ".join(
            f"<a href=\"{_esc(v)}\">{_esc(k)}</a>" for k, v in links.items()
            if k != "خريطة مُضمَّنة") + "</p>"
    if gl.get("consistency_checks"):
        geo_html += "<h4>فحوص الاتساق</h4><ul>" + "".join(
            f"<li>[{_esc(x.get('severity'))}] {_esc(x.get('note'))}</li>"
            for x in gl["consistency_checks"]) + "</ul>"
    pts = gl.get("points") or []
    if len(pts) > 1:
        rows = "".join(
            f"<tr><td class='mono'>{_esc((q.get('formats') or {}).get('decimal'))}</td>"
            f"<td>{_esc(q.get('kind'))}</td><td>{_esc(q.get('source'))}</td>"
            f"<td class='mono'>{_esc((q.get('confidence') or {}).get('score'))}</td></tr>"
            for q in pts)
        geo_html += ("<h4>كل النقاط المرصودة</h4><table><thead><tr><th>الإحداثيات</th>"
                     "<th>النوع</th><th>المصدر</th><th>الثقة</th></tr></thead>"
                     f"<tbody>{rows}</tbody></table>")
    if gl.get("place_names"):
        geo_html += "<h4>أسماء أماكن مكتوبة</h4>" + _kv_table(
            {k: v.get("value") for k, v in gl["place_names"].items()})
    if gl.get("indirect_indicators"):
        geo_html += "<h4>مؤشرات ترجيحية</h4><ul>" + "".join(
            f"<li><b>{_esc(i.get('type'))}</b> {_esc(i.get('country') or '')}: "
            f"{_esc(i.get('value'))} — {_esc(i.get('note'))}</li>"
            for i in gl["indirect_indicators"]) + "</ul>"

    # ---- بصمة الضغط
    cs = rep.get("compression_signature") or {}
    if not cs.get("ok"):
        qt_html = f"<p class='muted'>{_esc(cs.get('reason') or 'لا ينطبق (ليس JPEG).')}</p>"
    else:
        sg = cs.get("signature") or {}
        qn = cs.get("quantization") or {}
        qt_html = f"<p><b>{_esc(cs.get('verdict'))}</b></p>"
        qt_html += _kv_table({
            "توقيع جداول التكميم": sg.get("qt_signature"),
            "توقيع جداول هوفمان": sg.get("huffman_signature"),
            "التوقيع البنيوي": sg.get("structure_signature"),
            "التوقيع الكامل": sg.get("full_signature"),
            "تخفيض اللون": sg.get("subsampling"),
            "نوع الإطار": "تقدمي" if sg.get("progressive") else "أساسي (Baseline)",
            "ترتيب مقاطع APP": " > ".join(sg.get("app_marker_order") or []) or "لا شيء",
            "جداول هوفمان": ("قياسية (Annex K)" if sg.get("huffman_standard")
                              else "مُحسَّنة (غير قياسية)" if sg.get("huffman_optimized") else "—"),
            "الجودة المقيسة": qn.get("quality_estimate"),
            "كل الجداول قياسية IJG": "نعم" if qn.get("all_tables_standard_ijg") else "لا",
        })
        for t in qn.get("tables", []):
            rows = "".join("<tr>" + "".join(f"<td class='mono'>{v}</td>" for v in row) + "</tr>"
                           for row in t.get("grid_8x8", []))
            qt_html += (f"<h4>جدول {_esc(t.get('table_id'))} — {_esc(t.get('role'))} · "
                        f"الجودة {_esc(t.get('quality'))}"
                        + (" (مطابقة تامة لمقياس IJG)" if t.get("exact_ijg_match")
                           else f" (غير قياسي، انحراف {_esc(t.get('max_deviation'))})") + "</h4>"
                        + f"<table>{rows}</table>"
                        + f"<p class='muted'>{_esc(t.get('note'))}</p>")
        inf = cs.get("structural_inference") or []
        if inf:
            qt_html += "<h4>استدلالات بنيوية مقيسة</h4><ul>" + "".join(
                f"<li><b>{_esc(f['fact'])}</b> — {_esc(f['detail'])} "
                f"<code>{_esc(f['evidence'])}</code></li>" for f in inf) + "</ul>"

    # ---- بصمة الجهاز من MakerNote
    mnr = rep.get("makernote") or {}
    mn_html = ""
    if mnr.get("verdict"):
        mn_html += f"<p><b>{_esc(mnr['verdict'])}</b></p>"
    if mnr.get("standard_exif_identity"):
        mn_html += ("<p><b>محدِّدات الجهاز من EXIF القياسي:</b></p>"
                    + _kv_table(mnr["standard_exif_identity"]))
    for m in mnr.get("makernotes", []):
        head = (f"<h4>{_esc(m.get('vendor_ar') or m.get('vendor') or 'مصنّع غير معروف')}"
                f" — {_esc(m.get('size'))} بايت · مرجع الإزاحات: {_esc(m.get('offset_base'))}"
                f" · {_esc(m.get('byte_order'))}</h4>")
        head += (f"<p class='muted mono' style='direction:ltr'>{_esc(m.get('header_ascii'))} | "
                 f"{_esc(m.get('header_hex'))}</p>")
        if not m.get("decoded"):
            mn_html += head + f"<p class='muted'>{_esc(m.get('reason'))}</p>"
            continue
        ident = {k: (v.get("value") if isinstance(v, dict) else v)
                 for k, v in (m.get("identity") or {}).items() if not k.startswith("_")}
        notes = [v for k, v in (m.get("identity") or {}).items() if k.startswith("_")]
        mn_html += head
        if ident:
            mn_html += "<p><b>محدِّدات هوية الجهاز:</b></p>" + _kv_table(
                {k: _short(v, 300) for k, v in ident.items()})
        for sec, vals in (m.get("interpreted") or {}).items():
            mn_html += f"<p><b>{_esc(sec)}:</b></p>" + _kv_table(
                {k: _short(v, 200) for k, v in vals.items()})
        mn_html += "<p><b>كل وسوم MakerNote المقروءة:</b></p>" + _kv_table(
            {f"{k} ({f.get('tag')})": _short(f.get("value"), 200)
             for k, f in (m.get("fields") or {}).items()})
        for n in notes:
            mn_html += f"<p class='muted'>ℹ️ {_esc(n)}</p>"
    if not mn_html:
        mn_html = "<p class='muted'>لا يحتوي هذا الملف على وسوم MakerNote.</p>"

    # ---- PRNU
    pr = (rep.get("image_forensics") or {}).get("prnu") or {}
    if not pr.get("ok"):
        prnu_html = (f"<p class='muted'>{_esc(pr.get('reason') or 'غير متاح لهذا الملف.')}</p>")
    else:
        prnu_html = _kv_table({
            "المقطع المستخدم": " × ".join(str(x) for x in pr.get("crop_used", [])),
            "أبعاد الصورة": " × ".join(str(x) for x in pr.get("image_dims", [])),
            "طاقة بقايا الضجيج": pr.get("residual_energy"),
            "الانحراف المعياري للبقايا": pr.get("residual_std"),
            "متوسط الشدة": pr.get("mean_intensity"),
            "نسبة البكسلات المشبعة": pr.get("saturated_ratio"),
            "صالحة كمرجع لبناء بصمة": "نعم" if pr.get("usable_as_reference") else "لا",
        })
        prnu_html += f"<p class='muted'>{_esc(pr.get('note'))}</p>"
        idf = pr.get("identification") or {}
        if idf:
            prnu_html += f"<p><b>{_esc(idf.get('verdict'))}</b></p>"
            rows = "".join(
                f"<tr><td>{_esc(r.get('camera_name') or r.get('camera_id'))}</td>"
                f"<td class='mono'>{_esc(round(r.get('pce', 0), 1))}</td>"
                f"<td class='mono'>{_esc(round(r.get('pce_best_shift', 0), 1))}</td>"
                f"<td class='mono'>{_esc(round(r.get('ncc_at_zero_shift', 0), 5))}</td>"
                f"<td>{_esc(r.get('verdict') or r.get('reason'))}</td></tr>"
                for r in idf.get("results", []))
            if rows:
                prnu_html += ("<table><thead><tr><th>الكاميرا</th><th>PCE(0,0)</th>"
                              "<th>PCE لأفضل إزاحة</th><th>NCC</th><th>الحكم</th></tr></thead>"
                              f"<tbody>{rows}</tbody></table>")
            prnu_html += ("<p class='muted'>العتبات المعتمدة: تطابق قوي ≥ 60 (FAR ≈ 10⁻⁵ وفق "
                          "Goljan 2009) · ترجيح ≥ 25 · مؤشر ضعيف ≥ 10 · مطابقة مع قصّ ≥ 150.</p>")

    imgf = rep.get("image_forensics", {})
    imgs = []
    for key, label in (("preview", "معاينة الدليل"),):
        if imgf.get(key):
            imgs.append((label, imgf[key]))
    for sec, key, label in (("ela", "image", "تحليل مستوى الخطأ ELA"),
                            ("noise", "noise_map", "خريطة الضجيج"),
                            ("noise", "residual_image", "بقايا الضجيج"),
                            ("thumbnail_check", "thumbnail_image", "المصغّرة المدمجة"),
                            ("thumbnail_check", "diff_image", "فرق المصغّرة عن الصورة")):
        v = (imgf.get(sec) or {}).get(key)
        if v:
            imgs.append((label, v))
    for c, f in ((imgf.get("steganalysis") or {}).get("bit_plane_images") or {}).items():
        imgs.append((f"مستوى البت الأدنى — القناة {c}", f))
    gallery = "".join(
        f"<figure><img src='{artifacts_base}{_esc(f)}' loading='lazy'><figcaption>{_esc(l)}</figcaption></figure>"
        for l, f in imgs)

    carved = rep.get("carving", [])
    carved_rows = "".join(
        f"<tr><td>{_esc(c['type'])}</td><td>{_esc(c.get('description'))}</td>"
        f"<td>{c['offset']}</td><td>{_esc(c.get('size'))}</td>"
        f"<td class='mono'>{_esc((c.get('sha256') or '')[:32])}</td></tr>" for c in carved)

    custody_rows = "".join(
        f"<tr><td>{r['seq']}</td><td>{_esc(r['ts_utc'])}</td><td>{_esc(r['actor'])}</td>"
        f"<td>{_esc(r['action'])}</td><td>{_esc(_short(r['details'], 160))}</td>"
        f"<td class='mono'>{_esc(r['entry_hash'][:16])}…</td></tr>"
        for r in (custody or []))

    iocs = (rep.get("strings") or {}).get("iocs", {})
    ioc_html = "".join(
        f"<h4>{_esc(k)} ({len(v)})</h4><div class='chips'>" +
        "".join(f"<span class='chip'>{_esc(x)}</span>" for x in v[:60]) + "</div>"
        for k, v in iocs.items()) or "<p class='muted'>لا توجد مؤشرات.</p>"

    gen = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>تقرير جنائي رقمي — {_esc(ev.get('filename'))}</title>
<style>
*{{box-sizing:border-box}}
body{{font-family:"Segoe UI","Noto Naskh Arabic",Tahoma,sans-serif;background:#0d1117;color:#e6edf3;margin:0;padding:24px;line-height:1.7}}
.wrap{{max-width:1100px;margin:auto}}
h1{{font-size:26px;border-bottom:2px solid #2f81f7;padding-bottom:10px}}
h2{{font-size:20px;margin-top:34px;color:#58a6ff;border-right:4px solid #2f81f7;padding-right:10px}}
h4{{color:#8b949e;margin:16px 0 6px}}
table{{width:100%;border-collapse:collapse;margin:10px 0;font-size:13px;background:#0f1620}}
th,td{{border:1px solid #21262d;padding:6px 9px;text-align:right;vertical-align:top;word-break:break-word}}
th{{background:#161b22;color:#8b949e}}
.mono,code{{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12px;color:#7ee787;direction:ltr;display:inline-block}}
.src{{color:#6e7681;font-size:11px}}
.muted{{color:#6e7681}}
.score{{display:flex;gap:18px;align-items:center;background:#161b22;border:1px solid #21262d;border-radius:12px;padding:18px;margin:16px 0}}
.score .num{{font-size:48px;font-weight:bold}}
.critical{{color:#ff7b72}} .high{{color:#ffa657}} .medium{{color:#e3b341}} .low{{color:#79c0ff}} .clean,.info{{color:#56d364}}
.finding{{border-right:4px solid;padding:10px 14px;margin:10px 0;background:#11161d;border-radius:6px}}
.finding.critical{{border-color:#ff7b72}} .finding.high{{border-color:#ffa657}}
.finding.medium{{border-color:#e3b341}} .finding.low{{border-color:#79c0ff}} .finding.info{{border-color:#56d364}}
.fh{{display:flex;gap:10px;align-items:center;flex-wrap:wrap}}
.sev{{font-size:11px;padding:2px 8px;border-radius:20px;background:#21262d}}
.w{{margin-right:auto;font-size:11px;color:#6e7681}}
figure{{margin:0;background:#0f1620;border:1px solid #21262d;border-radius:8px;padding:8px}}
figure img{{width:100%;border-radius:4px}}
figcaption{{font-size:12px;color:#8b949e;text-align:center;padding-top:6px}}
.gallery{{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px}}
.chips{{display:flex;flex-wrap:wrap;gap:6px}}
.chip{{background:#161b22;border:1px solid #21262d;border-radius:20px;padding:2px 10px;font-size:12px;direction:ltr}}
.hdr{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px}}
.card{{background:#161b22;border:1px solid #21262d;border-radius:10px;padding:12px}}
.card b{{display:block;color:#8b949e;font-size:12px;font-weight:normal}}
footer{{margin-top:40px;border-top:1px solid #21262d;padding-top:14px;font-size:12px;color:#6e7681}}
@media print{{body{{background:#fff;color:#000}} .card,table,figure{{background:#fff}} h2{{color:#000}}}}
</style></head><body><div class="wrap">
<h1>⚖️ تقرير فحص جنائي رقمي — منظومة مِرصاد</h1>
<div class="hdr">
  <div class="card"><b>اسم الملف</b>{_esc(ev.get('filename'))}</div>
  <div class="card"><b>الحجم</b>{_esc(ev.get('size_human'))} ({_esc(ev.get('size_bytes'))} بايت)</div>
  <div class="card"><b>النوع الحقيقي</b>{_esc(t.get('description'))} — {_esc(t.get('mime'))}</div>
  <div class="card"><b>وقت التحليل (UTC)</b>{_esc(ev.get('analyzed_at_utc'))}</div>
  {"<div class='card'><b>رقم القضية</b>" + _esc(case.get('number')) + "</div>" if case else ""}
  {"<div class='card'><b>المحقق</b>" + _esc(case.get('investigator')) + "</div>" if case else ""}
  {"<div class='card'><b>معرّف الدليل</b><span class='mono'>" + _esc(evidence.get('id')) + "</span></div>" if evidence else ""}
</div>

<h2>1. الخلاصة التنفيذية</h2>
<div class="score"><div class="num {_esc(asmt.get('level_class'))}">{_esc(asmt.get('suspicion_score'))}</div>
<div><b>مؤشر الشبهة من 100:</b> <span class="{_esc(asmt.get('level_class'))}">{_esc(asmt.get('level'))}</span><br>
<span class="muted">عدد المؤشرات المرصودة: {_esc(asmt.get('findings_count'))}</span></div></div>
<p class="muted">{_esc(asmt.get('disclaimer'))}</p>

<h2>2. المؤشرات المرصودة والأدلة المساندة</h2>
{findings}

<h2>3. البصمات الرقمية (سلامة الدليل)</h2>
{_kv_table({k: v for k, v in fp.items()})}

<h2>4. تعريف نوع الملف</h2>
{_kv_table({k: v for k, v in t.items() if k != 'pe'})}

<h2>5. البيانات الوصفية المستخرجة</h2>
{_kv_table(rep.get('metadata', {}))}

<h2>6. الموقع الجغرافي</h2>
{geo_html}

<h2>7. بصمة الضغط وجداول التكميم (تحديد المُرمِّز بلا ميتاداتا)</h2>
{qt_html}

<h2>8. بصمة الجهاز من MakerNote (الوسوم الخاصة بالمصنّع)</h2>
{mn_html}

<h2>9. استرجاع البيانات الوصفية الممسوحة</h2>
{rec_html}

<h2>10. الخط الزمني</h2>
{"<ul>" + conflicts + "</ul>" if conflicts else ""}
<table><thead><tr><th>التاريخ/الوقت</th><th>الحدث</th><th>المصدر</th></tr></thead><tbody>{tl_rows}</tbody></table>

<h2>11. التحليل الإحصائي والعشوائية</h2>
{_kv_table({k: v for k, v in (rep.get('entropy') or {}).items() if k not in ('map', 'anomalies')})}

<h2>12. تحليل الصورة الجنائي</h2>
<div class="gallery">{gallery or "<p class='muted'>لا توجد مخرجات بصرية.</p>"}</div>
{_kv_table({k: _short(v, 300) for k, v in (imgf.get('basic') or {}).items()})}

<h2>13. بصمة ضجيج المستشعر PRNU (ربط الصورة بكاميرا فيزيائية)</h2>
{prnu_html}

<h2>14. الملفات المنحوتة والمدمجة</h2>
<table><thead><tr><th>النوع</th><th>الوصف</th><th>الإزاحة</th><th>الحجم</th><th>SHA-256</th></tr></thead>
<tbody>{carved_rows or "<tr><td colspan='5' class='muted'>لا شيء</td></tr>"}</tbody></table>

<h2>15. المؤشرات النصية المستخرجة (IOC)</h2>
{ioc_html}

<h2>16. سلسلة الحيازة</h2>
<table><thead><tr><th>#</th><th>الوقت (UTC)</th><th>الفاعل</th><th>الإجراء</th><th>التفاصيل</th><th>بصمة القيد</th></tr></thead>
<tbody>{custody_rows or "<tr><td colspan='6' class='muted'>لا توجد قيود</td></tr>"}</tbody></table>

<footer>
تقرير مُولَّد آليًا بواسطة <b>مِرصاد</b> — منظومة التحقيق الجنائي الرقمي · وقت التوليد: {gen} ·
جميع القيم الواردة مقيسة مباشرة من بايتات الدليل ويمكن إعادة التحقق منها باستخدام نفس الأدوات المفتوحة.
</footer>
</div></body></html>"""


def text_summary(rep: dict) -> str:
    a = rep.get("assessment", {})
    ev = rep.get("evidence", {})
    lines = [
        "=" * 64,
        f"مِرصاد — ملخص الفحص الجنائي: {ev.get('filename')}",
        "=" * 64,
        f"الحجم: {ev.get('size_human')} | النوع: {(rep.get('type') or {}).get('description')}",
        f"SHA-256: {(rep.get('fingerprints') or {}).get('sha256')}",
        f"مؤشر الشبهة: {a.get('suspicion_score')}/100 — {a.get('level')}",
        "-" * 64,
    ]
    for f in a.get("findings", []):
        lines.append(f"[{f['severity']}] {f['title']}: {f['detail']}")
        lines.append(f"    الدليل: {f['evidence']}")
    md = rep.get("metadata") or {}
    if md:
        lines.append("-" * 64)
        lines.append("أبرز البيانات الوصفية:")
        for k, v in list(md.items())[:40]:
            lines.append(f"  {k} = {_short(v.get('value') if isinstance(v, dict) else v, 120)}")
    return "\n".join(lines)
