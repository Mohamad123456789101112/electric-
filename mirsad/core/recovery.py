"""
محرّك استرجاع البيانات الوصفية «الممسوحة».

الفكرة العلمية: أدوات المسح (مثل حفظ الصورة من واتساب/فيسبوك أو «إزالة الميتاداتا»)
تحذف المقاطع المعروفة فقط، لكن تبقى غالبًا آثار حقيقية داخل البايتات:
  1) شظايا EXIF/TIFF في أماكن غير متوقعة (داخل التيار، في مساحة free، في slack).
  2) حزم XMP كاملة أو جزئية (<?xpacket ... ) حتى بعد حذف APP1.
  3) صور مصغّرة JPEG مدمجة تحمل المشهد الأصلي قبل التعديل/القص.
  4) ملفات تعريف ICC وكتل Photoshop IRB تكشف الجهاز/البرنامج.
  5) بصمة جداول التكميم وسلاسل الترميز تكشف المصدر حتى بلا ميتاداتا إطلاقًا.
  6) بيانات ملحقة/مُدمجة بعد نهاية الملف المنطقية.

كل ما هنا مسحٌ فعلي للبايتات — لا استنتاج وهمي.
"""
from __future__ import annotations

import re
import struct
import zlib

from . import exif as exif_mod
from . import jpeg as jpeg_mod

XMP_RE = re.compile(rb"<\?xpacket begin.{0,80}?\?>.*?<\?xpacket end=.{0,20}?\?>", re.S)
XMP_META_RE = re.compile(rb"<x:xmpmeta.*?</x:xmpmeta>", re.S)
XMP_PARTIAL_RE = re.compile(rb"<rdf:RDF.*?</rdf:RDF>", re.S)
ICC_RE = re.compile(rb"(?=(.{36}acsp))", re.S)


def _safe_tiff(data: bytes, off: int) -> dict | None:
    t = exif_mod.parse_tiff(data[off:off + 262144], 0)
    if t.get("ok") and (t.get("IFD0") or t.get("ExifIFD") or t.get("GPSIFD")):
        t["_found_at_offset"] = off
        return t
    return None


def scan_exif_fragments(data: bytes, limit: int = 40) -> list[dict]:
    """بحث شامل عن كل ترويسات Exif/TIFF في الملف كاملًا — وليس المقطع الأول فقط."""
    found: list[dict] = []
    seen_off: set[int] = set()
    for m in re.finditer(rb"Exif\x00\x00(?=(II\*\x00|MM\x00\*))", data):
        off = m.end()
        if off in seen_off:
            continue
        seen_off.add(off)
        t = _safe_tiff(data, off)
        if t:
            t["_container"] = "ترويسة Exif\\0\\0 (APP1 أو شظية منه)"
            found.append(t)
        if len(found) >= limit:
            return found
    for m in re.finditer(rb"(II\*\x00[\x00-\xff]{4}|MM\x00\*[\x00-\xff]{4})", data):
        off = m.start()
        if off in seen_off or any(abs(off - o) < 16 for o in seen_off):
            continue
        # تجاهل بداية ملف TIFF الرئيسي إن كان الملف نفسه TIFF
        seen_off.add(off)
        t = _safe_tiff(data, off)
        if t:
            fields = len(t.get("IFD0", {})) + len(t.get("ExifIFD", {})) + len(t.get("GPSIFD", {}))
            if fields >= 2:
                t["_container"] = "بنية TIFF حرة داخل البيانات (شظية مستعادة)"
                found.append(t)
        if len(found) >= limit:
            break
    return found


def scan_xmp(data: bytes, limit: int = 20) -> list[dict]:
    out = []
    spans: list[tuple[int, int]] = []
    for rx, kind in ((XMP_RE, "حزمة XMP كاملة"), (XMP_META_RE, "كتلة x:xmpmeta"),
                     (XMP_PARTIAL_RE, "شظية rdf:RDF")):
        for m in rx.finditer(data):
            if any(m.start() >= s and m.end() <= e for s, e in spans):
                continue
            spans.append((m.start(), m.end()))
            txt = m.group().decode("utf-8", "replace")
            out.append({"offset": m.start(), "size": len(m.group()), "kind": kind,
                        "xmp": txt[:200000], "parsed": parse_xmp(txt)})
            if len(out) >= limit:
                return out
    return out


XMP_FIELDS = {
    "xmp:CreateDate": "تاريخ الإنشاء", "xmp:ModifyDate": "تاريخ التعديل",
    "xmp:MetadataDate": "تاريخ تعديل البيانات الوصفية",
    "xmp:CreatorTool": "الأداة المُنشئة", "tiff:Make": "صانع الجهاز",
    "tiff:Model": "طراز الجهاز", "tiff:Software": "البرنامج",
    "exif:DateTimeOriginal": "تاريخ الالتقاط", "exif:GPSLatitude": "خط العرض",
    "exif:GPSLongitude": "خط الطول", "exif:LensModel": "العدسة",
    "dc:creator": "المُنشئ", "dc:title": "العنوان", "dc:description": "الوصف",
    "dc:rights": "الحقوق", "dc:subject": "الموضوع",
    "photoshop:DateCreated": "تاريخ فوتوشوب", "photoshop:History": "سجل فوتوشوب",
    "xmpMM:DocumentID": "معرّف المستند", "xmpMM:InstanceID": "معرّف النسخة",
    "xmpMM:OriginalDocumentID": "معرّف المستند الأصلي",
    "xmpMM:DerivedFrom": "مشتق من", "xmpMM:History": "سجل التعديلات",
    "crs:Version": "إصدار Camera Raw", "GCamera:": "بيانات Google Camera",
    "Container:Directory": "حاوية صور متعددة (Google/Samsung)",
    "pdf:Producer": "منتج PDF", "xmpDM:": "بيانات وسائط ديناميكية",
    "Iptc4xmpExt:": "امتداد IPTC", "plus:": "ترخيص PLUS",
    "digiKam:": "digiKam", "lr:hierarchicalSubject": "وسوم Lightroom",
}


def parse_xmp(xmp: str) -> dict:
    out: dict = {}
    for m in re.finditer(r"<([A-Za-z0-9_]+:[A-Za-z0-9_\-]+)(?:\s[^>]*)?>([^<]{1,2000})</\1>", xmp):
        key, val = m.group(1), m.group(2).strip()
        if val:
            out[key] = val[:1000]
    for m in re.finditer(r'([A-Za-z0-9_]+:[A-Za-z0-9_\-]+)\s*=\s*"([^"]{1,2000})"', xmp):
        key, val = m.group(1), m.group(2).strip()
        if key.split(":")[0] not in ("xmlns", "x", "rdf") and val:
            out.setdefault(key, val[:1000])
    # ترجمة الحقول المهمة
    named = {}
    for k, v in out.items():
        label = XMP_FIELDS.get(k)
        if label:
            named[f"{label} ({k})"] = v
    hist = re.findall(r'stEvt:action="([^"]+)"[^>]*?(?:stEvt:softwareAgent="([^"]*)")?[^>]*?(?:stEvt:when="([^"]*)")?',
                      xmp)
    if hist:
        named["سجل التعديلات (XMP History)"] = [
            {"action": a, "software": s, "when": w} for a, s, w in hist][:50]
    return {"all_fields": out, "key_fields": named}


def scan_embedded_jpegs(data: bytes, min_size: int = 1024, limit: int = 30) -> list[dict]:
    """استخراج كل صور JPEG الكاملة داخل البايتات (مصغّرات/معاينات/صور مخفية)."""
    out = []
    pos = 0
    while True:
        s = data.find(b"\xFF\xD8\xFF", pos)
        if s < 0:
            break
        e = data.find(b"\xFF\xD9", s + 3)
        if e < 0:
            break
        blob = data[s:e + 2]
        pos = s + 2
        if len(blob) < min_size:
            continue
        w = h = None
        info = {}
        j = 2
        while j < len(blob) - 9:
            if blob[j] != 0xFF:
                j += 1
                continue
            mk = blob[j + 1]
            if mk in (0xC0, 0xC1, 0xC2):
                h, w = struct.unpack_from(">HH", blob, j + 5)
                break
            if mk in (0xD8, 0x01) or 0xD0 <= mk <= 0xD7:
                j += 2
                continue
            try:
                ln = struct.unpack_from(">H", blob, j + 2)[0]
            except struct.error:
                break
            j += 2 + ln
        idx = blob.find(b"Exif\x00\x00")
        if idx >= 0:
            t = _safe_tiff(blob, idx + 6)
            if t:
                info["exif"] = exif_mod.flatten(t)
                if t.get("GPS_decoded"):
                    info["gps"] = t["GPS_decoded"]
        out.append({"offset": s, "size": len(blob), "width": w, "height": h,
                    "info": info, "_bytes": blob})
        if len(out) >= limit:
            break
    return out


def scan_png_blobs(data: bytes, limit: int = 10) -> list[dict]:
    out = []
    for m in re.finditer(rb"\x89PNG\r\n\x1a\n", data):
        s = m.start()
        e = data.find(b"IEND\xaeB`\x82", s)
        if e < 0:
            continue
        out.append({"offset": s, "size": e + 8 - s, "_bytes": data[s:e + 8]})
        if len(out) >= limit:
            break
    return out


def scan_icc(data: bytes, limit: int = 6) -> list[dict]:
    out = []
    for m in re.finditer(rb"acsp", data):
        start = m.start() - 36
        if start < 0:
            continue
        try:
            size = struct.unpack_from(">I", data, start)[0]
        except struct.error:
            continue
        if not (128 <= size <= 10_000_000) or start + size > len(data) + 4096:
            continue
        prof = jpeg_mod.parse_icc(data[start:start + min(size, 200000)])
        if prof.get("color_space"):
            prof["_offset"] = start
            out.append(prof)
        if len(out) >= limit:
            break
    return out


def scan_photoshop_irb(data: bytes) -> list[dict]:
    out = []
    for m in re.finditer(rb"8BIM", data):
        if len(out) >= 3:
            break
        res = jpeg_mod.parse_irb(data[m.start():m.start() + 200000])
        if res.get("blocks"):
            res["_offset"] = m.start()
            res.pop("_photoshop_thumbnail", None)
            out.append(res)
            break
    return out


# بصمات جداول تكميم شائعة (مصدر الملف حتى بدون أي ميتاداتا)
QUALITY_SIGNATURES = [
    (lambda q, s: s == "4:2:0" and 70 <= q <= 76, "ضغط يطابق نمط واتساب/تطبيقات المراسلة (جودة ~75، 4:2:0)"),
    (lambda q, s: s == "4:2:0" and 84 <= q <= 86, "ضغط يطابق نمط فيسبوك/إنستغرام (جودة ~85)"),
    (lambda q, s: q >= 95, "جودة عالية جدًا — ملف قريب من الأصل أو مُصدَّر بإعداد أقصى"),
    (lambda q, s: s.startswith("4:4:4"), "بدون تقليل لوني — نمط برامج التحرير الاحترافية (فوتوشوب/لايت روم)"),
]


def source_fingerprint(jp: dict, strings_blob: str) -> list[str]:
    """استنتاج مصدر الصورة من البصمات التقنية وحدها (عندما تُمسح الميتاداتا)."""
    notes: list[str] = []
    q = jp.get("estimated_jpeg_quality")
    sub = (jp.get("frame") or {}).get("subsampling", "")
    if q:
        for cond, note in QUALITY_SIGNATURES:
            try:
                if cond(q, sub):
                    notes.append(f"{note} — الجودة المقدّرة {q}.")
            except Exception:
                pass
    segs = [s["marker"] for s in jp.get("segments", [])]
    order = "-".join(segs[:6])
    if order.startswith("SOI-APP0"):
        notes.append("ترتيب المقاطع يبدأ بـ APP0/JFIF: نمط مكتبات libjpeg (معالجة/إعادة حفظ برمجية).")
    if order.startswith("SOI-APP1"):
        notes.append("ترتيب المقاطع يبدأ بـ APP1/Exif: نمط إخراج مباشر من كاميرا/هاتف.")
    if "APP14" in segs:
        notes.append("وجود APP14 (Adobe) — الملف مرّ ببرنامج من أدوبي.")
    if "APP12" in segs:
        notes.append("وجود APP12 (Ducky) — أُنتج عبر «Save for Web» في فوتوشوب.")
    if (jp.get("frame") or {}).get("progressive"):
        notes.append("JPEG تقدمي (Progressive) — نمط تحسين الويب، نادر في الإخراج المباشر من الكاميرا.")
    if jp.get("app_payloads", {}).get("MPF"):
        notes.append("وجود MPF — صورة من هاتف يدعم الصور المتعددة (سامسونج/أبل).")
    low = strings_blob.lower()
    for marker, note in (("whatsapp", "سلسلة نصية تشير إلى WhatsApp"),
                         ("telegram", "سلسلة نصية تشير إلى Telegram"),
                         ("instagram", "سلسلة نصية تشير إلى Instagram"),
                         ("facebook", "سلسلة نصية تشير إلى Facebook"),
                         ("picsart", "سلسلة نصية تشير إلى PicsArt"),
                         ("snapseed", "سلسلة نصية تشير إلى Snapseed")):
        if marker in low:
            notes.append(note + " داخل بايتات الملف.")
    return notes


def analyze(data: bytes, strings_blob: str = "", jpeg_info: dict | None = None,
            known_sections: list[tuple[int, int]] | None = None) -> dict:
    """المسح الشامل لاسترجاع كل أثر وصفي داخل البايتات."""
    res: dict = {}
    res["exif_fragments"] = []
    for frag in scan_exif_fragments(data):
        flat = exif_mod.flatten(frag)
        res["exif_fragments"].append({
            "offset": frag.get("_found_at_offset"),
            "container": frag.get("_container"),
            "byte_order": frag.get("byte_order"),
            "fields_recovered": len(flat),
            "fields": flat,
            "gps": frag.get("GPS_decoded"),
            "datetimes": exif_mod.exif_datetimes(frag),
            "makernote_present": frag.get("MakerNote_present", False),
        })
    res["xmp_packets"] = scan_xmp(data)
    jpgs = scan_embedded_jpegs(data)
    res["embedded_images"] = [{k: v for k, v in j.items() if k != "_bytes"} for j in jpgs]
    res["_embedded_image_bytes"] = [j["_bytes"] for j in jpgs]
    res["embedded_pngs"] = [{"offset": p["offset"], "size": p["size"]} for p in scan_png_blobs(data)]
    res["icc_profiles"] = scan_icc(data)
    res["photoshop_irb"] = scan_photoshop_irb(data)
    if jpeg_info:
        res["source_fingerprint"] = source_fingerprint(jpeg_info, strings_blob)

    # تقييم: هل مُسحت الميتاداتا؟
    verdict = []
    has_main_exif = bool(jpeg_info and jpeg_info.get("app_payloads", {}).get("Exif"))
    if not has_main_exif and res["exif_fragments"]:
        verdict.append("🔴 لا يوجد EXIF في موضعه الطبيعي، لكن استُرجعت شظايا EXIF من داخل البايتات — "
                       "دليل قوي على محاولة مسح البيانات الوصفية مع بقاء آثار قابلة للاسترجاع.")
    if not has_main_exif and not res["exif_fragments"] and jpeg_info and jpeg_info.get("is_jpeg"):
        verdict.append("🟠 لا توجد أي بيانات EXIF إطلاقًا — الصورة إمّا مُعاد ترميزها بالكامل "
                       "(تطبيق مراسلة/شبكة اجتماعية) أو مُسحت بأداة شاملة. "
                       "الاعتماد ينتقل إلى البصمات التقنية (جداول التكميم/الترتيب/الإحصاء).")
    if res["xmp_packets"] and not has_main_exif:
        verdict.append("🟡 عُثر على حزم XMP رغم غياب EXIF — المسح كان جزئيًا.")
    if res["embedded_images"]:
        verdict.append(f"🟢 استُخرجت {len(res['embedded_images'])} صورة مدمجة (مصغّرات/معاينات) — "
                       "قد تُظهر المشهد قبل القص أو التعديل.")
    res["verdict"] = verdict
    return res
