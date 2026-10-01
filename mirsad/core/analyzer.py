"""
المنسّق الرئيسي: يشغّل كل وحدات التحليل على الدليل وينتج تقريرًا موحّدًا
مع «مؤشر الشبهة» (Tamper Indicator Score) المبني على أدلة قابلة للتحقق فقط.
"""
from __future__ import annotations

import hashlib
import io
import os
import time
import traceback
from datetime import datetime, timezone

from . import (carver, containers, documents, entropy, exif as exif_mod, hashing,
               imaging, jpeg as jpeg_mod, jpegdct, makernote as makernote_mod,
               prnu as prnu_mod, recovery, signatures, strings_, timeline)


def _try(name: str, fn, errors: list):
    try:
        return fn()
    except Exception as e:  # pragma: no cover
        errors.append({"module": name, "error": f"{type(e).__name__}: {e}",
                       "trace": traceback.format_exc()[-800:]})
        return None


def analyze(data: bytes, filename: str, artifacts_dir: str,
            deep: bool = True, prnu_registry=None) -> dict:
    t0 = time.time()
    errors: list = []
    rep: dict = {
        "evidence": {
            "filename": filename,
            "size_bytes": len(data),
            "size_human": _hsize(len(data)),
            "analyzed_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
        "errors": errors,
    }

    # 1) البصمات
    rep["fingerprints"] = _try("hashing", lambda: hashing.full_fingerprint(data), errors) or {}
    if deep and len(data) <= 64 * 1024 * 1024:
        rep["block_hashes"] = _try("block_hashes", lambda: hashing.block_hashes(data), errors) or []

    # 2) التعريف
    tid = _try("signatures", lambda: signatures.identify(data, filename), errors)
    if tid:
        rep["type"] = {
            "mime": tid.mime, "extension_real": tid.ext, "description": tid.description,
            "confidence": tid.confidence, "signature_hex": tid.matched_signature,
            "signature_offset": tid.offset, "extension_mismatch": tid.extension_mismatch,
            "notes": tid.notes,
        }
        if tid.ext in ("exe", "macho"):
            rep["type"]["pe"] = signatures.pe_info(data)
    kind = tid.ext if tid else "bin"

    # 3) الإنتروبيا والإحصاء
    rep["entropy"] = _try("entropy", lambda: entropy.analyze(data), errors) or {}

    # 4) السلاسل والمؤشرات
    st = _try("strings", lambda: strings_.analyze(data), errors) or {}
    rep["strings"] = st
    blob = "\n".join(x["text"] for x in st.get("strings", {}).get("ascii", [])[:4000])

    # 5) الحاويات حسب النوع
    containers_out: dict = {}
    jp = None
    if data[:2] == b"\xFF\xD8":
        jp = _try("jpeg", lambda: jpeg_mod.parse(data), errors)
        containers_out["jpeg"] = _strip_bytes(jp) if jp else None
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        containers_out["png"] = _try("png", lambda: containers.parse_png(data), errors)
    if data[:6] in (b"GIF87a", b"GIF89a"):
        containers_out["gif"] = _try("gif", lambda: containers.parse_gif(data), errors)
    if data[:4] == b"RIFF":
        containers_out["riff"] = _try("riff", lambda: containers.parse_riff(data), errors)
    if len(data) > 12 and data[4:8] in (b"ftyp", b"moov", b"mdat", b"styp", b"free"):
        containers_out["iso_bmff"] = _try("bmff", lambda: containers.parse_bmff(data), errors)
    if data[:4] == b"\x1aE\xdf\xa3":
        containers_out["matroska"] = _try("mkv", lambda: containers.parse_matroska(data), errors)
    if data[:4] in (b"II*\x00", b"MM\x00*"):
        containers_out["tiff"] = _try("tiff", lambda: exif_mod.parse_tiff(data, 0), errors)
    if data.lstrip()[:5] == b"%PDF-":
        containers_out["pdf"] = _try("pdf", lambda: documents.parse_pdf(data), errors)
    if data[:4] in (b"PK\x03\x04", b"PK\x05\x06"):
        containers_out["ooxml_zip"] = _try("ooxml", lambda: documents.parse_ooxml(data), errors)
        containers_out["zip_structure"] = _try("zipstruct", lambda: documents.zip_structure(data), errors)
    if data[:3] == b"ID3" or kind in ("mp3", "flac", "ogg", "m4a", "wav"):
        containers_out["audio_tags"] = _try("audio", lambda: _audio_tags(data), errors)
    rep["containers"] = containers_out

    # 6) الميتاداتا الموحّدة
    rep["metadata"] = _try("metadata", lambda: _unified_metadata(containers_out), errors) or {}

    # 6-ب) فكّ MakerNote الخاص بالمصنّع (بصمة الجهاز داخل الميتاداتا)
    mn = _try("makernote", lambda: makernote_mod.analyze(data), errors) or {}
    rep["makernote"] = mn
    # محدِّدات الجهاز الموجودة في EXIF القياسي نفسه (تبقى أحيانًا بعد إزالة MakerNote)
    _std_src = ((containers_out.get("jpeg") or {}).get("app_payloads") or {}).get("Exif") \
        or (containers_out.get("png") or {}).get("exif") or containers_out.get("tiff") \
        or ((containers_out.get("iso_bmff") or {}).get("exif")) or {}
    _std: dict = {}
    if isinstance(_std_src, dict):
        for sect in ("IFD0", "ExifIFD"):
            for tag, label in (("BodySerialNumber", "الرقم التسلسلي للجسم (EXIF قياسي)"),
                               ("CameraSerialNumber", "الرقم التسلسلي للكاميرا (EXIF قياسي)"),
                               ("LensSerialNumber", "الرقم التسلسلي للعدسة (EXIF قياسي)"),
                               ("LensModel", "طراز العدسة (EXIF قياسي)"),
                               ("CameraOwnerName", "اسم مالك الكاميرا (EXIF قياسي)"),
                               ("ImageUniqueID", "المعرّف الفريد للصورة (EXIF قياسي)")):
                v = ((_std_src.get(sect) or {}).get(tag) or {}).get("raw")
                if isinstance(v, str) and v.strip():
                    _std[label] = v.strip()
    if _std:
        mn["standard_exif_identity"] = _std
        for k, v in _std.items():
            rep["metadata"][f"🔧 {k}"] = {"value": v, "source": "EXIF قياسي"}
        if not mn.get("present"):
            mn["verdict"] = (mn.get("verdict", "") +
                             " لكن EXIF القياسي يحوي محدِّدات جهاز: " + "، ".join(_std)).strip()
    for m in mn.get("makernotes", []):
        if not m.get("decoded"):
            continue
        for label, val in (m.get("identity") or {}).items():
            if label.startswith("_") or not isinstance(val, dict):
                continue
            v = val.get("value")
            if isinstance(v, (str, int, float)):
                rep["metadata"][f"🔧 {label}"] = {
                    "value": v, "source": f"MakerNote ({m.get('vendor')})"}

    # 7) الاسترجاع (الميتاداتا الممسوحة)
    rec = _try("recovery", lambda: recovery.analyze(data, blob, jp), errors) or {}
    emb_bytes = rec.pop("_embedded_image_bytes", [])
    rep["recovery"] = rec

    # حفظ الصور المدمجة المستخرجة كملفات حقيقية
    os.makedirs(artifacts_dir, exist_ok=True)
    saved = []
    for i, b in enumerate(emb_bytes[:20]):
        name = f"embedded_{i}_{rec['embedded_images'][i]['offset']}.jpg"
        with open(os.path.join(artifacts_dir, name), "wb") as f:
            f.write(b)
        rec["embedded_images"][i]["file"] = name
        saved.append(name)
    rep["recovered_files"] = saved

    # 8) النحت
    rep["carving"] = _try("carving", lambda: carver.carve(data, artifacts_dir), errors) or []

    # 9) تحليل الصورة
    im = imaging.load(data) if (tid and tid.mime.startswith("image/")) else None
    if im is not None:
        img_out: dict = {"basic": imaging.basic_info(im)}
        img_out["histogram"] = _try("histogram", lambda: imaging.histogram_stats(im, artifacts_dir), errors)
        if deep:
            img_out["ela"] = _try("ela", lambda: imaging.ela(im, artifacts_dir), errors)
            img_out["noise"] = _try("noise", lambda: imaging.noise_analysis(im, artifacts_dir), errors)
            img_out["copy_move"] = _try("copy_move", lambda: imaging.copy_move(im, artifacts_dir), errors)
            img_out["steganalysis"] = _try("lsb", lambda: imaging.lsb_analysis(im, artifacts_dir), errors)
            if jp:
                img_out["double_compression"] = _try(
                    "dct", lambda: jpegdct.double_compression(data), errors)
                img_out["coefficient_statistics"] = _try(
                    "benford", lambda: jpegdct.coefficient_stats(data), errors)
                img_out["dct_pixel_domain"] = _try(
                    "dct_pixel", lambda: imaging.dct_double_compression(
                        data, (jp.get("quant_tables") or [{}])[0].get("values")), errors)
                img_out["jpeg_ghosts"] = _try("ghost", lambda: imaging.jpeg_ghosts(im, artifacts_dir), errors)
            thumbs = (jp or {}).get("_thumbnails") or []
            if thumbs:
                img_out["thumbnail_check"] = _try(
                    "thumb", lambda: imaging.thumbnail_compare(im, thumbs[0]["bytes"], artifacts_dir), errors)
            # معاينة أصلية
            try:
                prev = im.convert("RGB")
                prev.thumbnail((1400, 1400))
                prev.save(os.path.join(artifacts_dir, "preview.png"))
                img_out["preview"] = "preview.png"
            except Exception:
                pass
            # بصمة ضجيج المستشعر PRNU (ومطابقتها بسجل الكاميرات إن وُجد)
            img_out["prnu"] = _try(
                "prnu", lambda: prnu_mod.analyze(data, registry=prnu_registry), errors)
        rep["image_forensics"] = img_out

    # 10) الخط الزمني
    rep["timeline"] = _try("timeline", lambda: timeline.build(_collect_times(rep)), errors) or {}

    # 11) التقييم النهائي
    rep["assessment"] = _try("assessment", lambda: assess(rep), errors) or {}
    rep["evidence"]["analysis_seconds"] = round(time.time() - t0, 2)
    return jsonable(rep)


def jsonable(obj, _depth: int = 0):
    """تحويل التقرير إلى أنواع قابلة للتسلسل (JSON) دون فقدان أي معلومة مقروءة."""
    if _depth > 40:
        return str(obj)
    if obj is None or isinstance(obj, (bool, int, str)):
        return obj
    if isinstance(obj, float):
        return obj if obj == obj and abs(obj) != float("inf") else str(obj)
    if isinstance(obj, bytes):
        return {"_bytes": len(obj), "hex_preview": obj[:64].hex(" ")}
    if isinstance(obj, dict):
        return {str(k): jsonable(v, _depth + 1) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [jsonable(v, _depth + 1) for v in obj]
    try:
        import numpy as _np
        if isinstance(obj, _np.integer):
            return int(obj)
        if isinstance(obj, _np.floating):
            return float(obj)
        if isinstance(obj, _np.ndarray):
            return jsonable(obj.tolist(), _depth + 1)
    except Exception:
        pass
    for conv in (int, float):          # مثل PIL IFDRational
        try:
            v = conv(obj)
            return round(v, 6) if conv is float else v
        except Exception:
            continue
    return str(obj)


def _strip_bytes(d: dict) -> dict:
    out = {k: v for k, v in d.items() if not k.startswith("_")}
    if "_thumbnails" in d:
        out["thumbnails"] = [{"source": t["source"], "size": len(t["bytes"])} for t in d["_thumbnails"]]
    return out


def _audio_tags(data: bytes) -> dict:
    try:
        import mutagen
    except ImportError:
        return {"error": "mutagen غير مثبت"}
    f = mutagen.File(io.BytesIO(data))
    if f is None:
        return {}
    info = {}
    if getattr(f, "info", None):
        for attr in ("length", "bitrate", "sample_rate", "channels", "codec", "bits_per_sample"):
            v = getattr(f.info, attr, None)
            if v is not None:
                info[attr] = round(v, 3) if isinstance(v, float) else v
    tags = {}
    if f.tags:
        for k, v in dict(f.tags).items():
            tags[str(k)] = str(v)[:500]
    return {"stream_info": info, "tags": tags}


def _unified_metadata(c: dict) -> dict:
    """تجميع كل الحقول الوصفية في جدول واحد مع ذكر المصدر."""
    flat: dict = {}

    def add(src: str, d: dict):
        for k, v in (d or {}).items():
            if isinstance(v, (str, int, float)) or v is None:
                flat[f"{k}"] = {"value": v, "source": src}

    jp = c.get("jpeg") or {}
    ex = (jp.get("app_payloads") or {}).get("Exif")
    if ex:
        add("EXIF (JPEG APP1)", exif_mod.flatten(ex))
        if ex.get("GPS_decoded"):
            flat["📍 الموقع الجغرافي"] = {"value": ex["GPS_decoded"], "source": "EXIF GPS IFD"}
    icc = (jp.get("app_payloads") or {}).get("ICC")
    if icc:
        add("ICC Profile", {k: v for k, v in icc.items() if isinstance(v, (str, int))})
    irb = (jp.get("app_payloads") or {}).get("Photoshop_IRB")
    if irb and irb.get("IPTC"):
        add("IPTC (Photoshop IRB)", irb["IPTC"])
    if (jp.get("app_payloads") or {}).get("JFIF"):
        add("JFIF", jp["app_payloads"]["JFIF"])
    xmp = (jp.get("app_payloads") or {}).get("XMP")
    if xmp:
        parsed = recovery.parse_xmp(xmp)
        add("XMP", {k: v for k, v in parsed["key_fields"].items() if isinstance(v, str)})

    png = c.get("png") or {}
    if png.get("text"):
        add("PNG text chunks", png["text"])
    if png.get("exif"):
        add("PNG eXIf", exif_mod.flatten(png["exif"]))
    if png.get("last_modified_chunk"):
        flat["PNG tIME"] = {"value": png["last_modified_chunk"], "source": "PNG tIME chunk"}

    tif = c.get("tiff") or {}
    if tif.get("ok"):
        add("TIFF", exif_mod.flatten(tif))

    riff = c.get("riff") or {}
    if riff.get("metadata"):
        add("RIFF", {k: v for k, v in riff["metadata"].items() if isinstance(v, (str, int))})
    if riff.get("exif"):
        add("WebP EXIF", exif_mod.flatten(riff["exif"]))

    bmff = c.get("iso_bmff") or {}
    if bmff.get("metadata"):
        m = bmff["metadata"]
        for k, v in m.items():
            if isinstance(v, (str, int, float)):
                flat[k] = {"value": v, "source": "ISO-BMFF"}
        if m.get("movie"):
            for k, v in m["movie"].items():
                flat[f"movie.{k}"] = {"value": v, "source": "ISO-BMFF mvhd"}
        if m.get("tags"):
            add("ISO-BMFF tags", m["tags"])
        if m.get("tracks"):
            for i, t in enumerate(m["tracks"]):
                for k, v in t.items():
                    flat[f"track{i}.{k}"] = {"value": v, "source": "ISO-BMFF tkhd"}
    if bmff.get("exif"):
        add("HEIC EXIF", exif_mod.flatten(bmff["exif"]))

    pdf = c.get("pdf") or {}
    if pdf.get("info"):
        add("PDF Info Dictionary", pdf["info"])
    ooxml = c.get("ooxml_zip") or {}
    if ooxml.get("metadata"):
        add("OOXML docProps", ooxml["metadata"])
    au = c.get("audio_tags") or {}
    if au.get("tags"):
        add("وسوم صوتية", au["tags"])
    if au.get("stream_info"):
        add("خصائص التيار الصوتي", au["stream_info"])
    return flat


def _collect_times(rep: dict) -> list[dict]:
    ev = []
    c = rep.get("containers", {})
    jp = c.get("jpeg") or {}
    ex = (jp.get("app_payloads") or {}).get("Exif")
    for src in (ex, (c.get("png") or {}).get("exif"), (c.get("riff") or {}).get("exif"),
                (c.get("iso_bmff") or {}).get("exif"), c.get("tiff")):
        if src:
            for d in exif_mod.exif_datetimes(src):
                ev.append({"label": d["label"], "source": d["source"], "value": d["iso"]})
    for frag in (rep.get("recovery") or {}).get("exif_fragments", []):
        for d in frag.get("datetimes", []):
            ev.append({"label": f"{d['label']} (شظية مستعادة @{frag['offset']})",
                       "source": d["source"], "value": d["iso"]})
    for pkt in (rep.get("recovery") or {}).get("xmp_packets", []):
        for k, v in (pkt.get("parsed", {}).get("key_fields") or {}).items():
            if "تاريخ" in k and isinstance(v, str):
                ev.append({"label": k, "source": "XMP", "value": v})
    png = c.get("png") or {}
    if png.get("last_modified_chunk"):
        ev.append({"label": "وقت تعديل PNG", "source": "PNG tIME", "value": png["last_modified_chunk"]})
    bm = (c.get("iso_bmff") or {}).get("metadata", {})
    if bm.get("movie"):
        for k, label in (("created_utc", "إنشاء الفيلم"), ("modified_utc", "تعديل الفيلم")):
            if bm["movie"].get(k):
                ev.append({"label": label, "source": "ISO-BMFF mvhd", "value": bm["movie"][k]})
    for t in bm.get("tracks", [])[:4]:
        if t.get("created_utc"):
            ev.append({"label": f"إنشاء المسار {t.get('track_id')}", "source": "tkhd", "value": t["created_utc"]})
    pdf = c.get("pdf") or {}
    for k, label in (("CreationDate", "إنشاء PDF"), ("ModDate", "تعديل PDF")):
        if (pdf.get("info") or {}).get(k):
            ev.append({"label": label, "source": f"PDF {k}", "value": pdf["info"][k]})
    ooxml = c.get("ooxml_zip") or {}
    for label, v in (ooxml.get("metadata") or {}).items():
        if "تاريخ" in label and isinstance(v, str):
            ev.append({"label": label, "source": "OOXML", "value": v})
    if (ooxml.get("zip_timestamp_range") or {}).get("earliest"):
        ev.append({"label": "أقدم إدخال ZIP", "source": "ZIP local header",
                   "value": ooxml["zip_timestamp_range"]["earliest"]})
        ev.append({"label": "أحدث إدخال ZIP", "source": "ZIP local header",
                   "value": ooxml["zip_timestamp_range"]["latest"]})
    pe = (rep.get("type") or {}).get("pe") or {}
    if pe.get("compile_timestamp_utc"):
        ev.append({"label": "وقت تصريف الملف التنفيذي", "source": "PE header",
                   "value": datetime.fromtimestamp(pe["compile_timestamp_utc"], timezone.utc)
                   .strftime("%Y-%m-%dT%H:%M:%S")})
    return ev


# -------------------------------------------------------------- التقييم النهائي

def assess(rep: dict) -> dict:
    """مؤشر شبهة مبني على أدلة فعلية فقط، مع وزن ومرجع لكل دليل."""
    findings: list[dict] = []

    def add(sev: str, weight: int, title: str, detail: str, evidence: str):
        findings.append({"severity": sev, "weight": weight, "title": title,
                         "detail": detail, "evidence": evidence})

    t = rep.get("type", {})
    if t.get("extension_mismatch"):
        add("عالية", 20, "تمويه نوع الملف",
            "الامتداد المعلن لا يطابق التوقيع الثنائي الحقيقي.",
            f"التوقيع المرصود: {t.get('signature_hex')} عند الإزاحة {t.get('signature_offset')}")

    c = rep.get("containers", {})
    jp = c.get("jpeg") or {}
    for cont, key in ((jp, "trailing_data"), (c.get("png") or {}, "trailing_data"),
                      (c.get("gif") or {}, "trailing_data"), (c.get("iso_bmff") or {}, "trailing_data"),
                      (c.get("pdf") or {}, "trailing_data")):
        td = cont.get(key)
        if td:
            add("عالية", 18, "بيانات ملحقة بعد نهاية الملف المنطقية",
                "توجد بايتات بعد علامة نهاية الملف — مكان شائع لإخفاء ملفات أو أرشيفات.",
                f"إزاحة {td['offset']}, حجم {td['size']} بايت")
            break
    zs = c.get("zip_structure") or {}
    if zs.get("appended_data") or zs.get("prepended_data"):
        add("عالية", 15, "أرشيف مُدمج مع بيانات خارجية",
            "الأرشيف محاط ببيانات إضافية (polyglot / self-extracting).", str(zs)[:200])

    png = c.get("png") or {}
    bad_crc = [w for w in png.get("warnings", []) if "CRC" in w]
    if bad_crc:
        add("حرجة", 25, "فشل تحقق CRC داخل PNG",
            "إحدى كتل PNG لا تطابق مجموع تحققها — تعديل مباشر على بايتات الملف.",
            bad_crc[0])

    # تضارب بصمة المصنّع: ترويسة MakerNote تكشف جهازًا غير المُعلن في EXIF
    mnr = rep.get("makernote") or {}
    ex_make = ""
    _ex = (jp.get("app_payloads") or {}).get("Exif") or {}
    if isinstance(_ex, dict):
        ex_make = str(((_ex.get("IFD0") or {}).get("Make") or {}).get("raw") or "")
    for m in mnr.get("makernotes", []):
        v = (m.get("vendor") or "").lower()
        if not m.get("decoded") or not v or not ex_make:
            continue
        mk = ex_make.lower()
        alias = {"nikon": "nikon", "canon": "canon", "sony": "sony", "apple": "apple",
                 "panasonic": "panasonic", "fujifilm": "fuji", "olympus": "olympus",
                 "samsung": "samsung"}.get(v, v)
        if alias not in mk:
            add("عالية", 20, "⚠️ تضارب بين المصنّع المعلن وبنية MakerNote",
                f"حقل Make في EXIF يقول «{ex_make}» بينما بنية MakerNote تخص {m.get('vendor_ar') or v}. "
                "هذا يحدث عند تزوير حقول EXIF أو لصق ميتاداتا من صورة أخرى.",
                f"ترويسة MakerNote: {m.get('header_ascii')} | {m.get('header_hex')}")
        break
    for m in mnr.get("makernotes", []):
        rej = [k for k, f in (m.get("fields") or {}).items() if f.get("_rejected")]
        if rej:
            add("متوسطة", 8, "⚠️ مؤشرات تالفة داخل MakerNote",
                "بعض مؤشرات الوسوم داخل MakerNote تشير خارج حدود البيانات — علامة على بتر "
                "الكتلة أو إعادة كتابة الملف بأداة لا تحافظ على الإزاحات.",
                "الوسوم المرفوضة: " + "، ".join(rej[:6]))
            break

    pr = ((rep.get("image_forensics") or {}).get("prnu") or {}).get("identification") or {}
    for r in pr.get("results", []):
        if r.get("level") in ("strong", "probable"):
            # تحديد المصدر ليس «شبهة» بحد ذاته ⇒ وزن صفر، يُعرض كتعريف لا كإنذار
            add("معلوماتية", 0,
                "🎯 تحديد الكاميرا ببصمة ضجيج المستشعر (PRNU)",
                f"الصورة تطابق بصمة الكاميرا المسجّلة «{r.get('camera_name')}». "
                "هذه الإحصائية فيزيائية ولا تتأثر بتزوير الميتاداتا.",
                f"PCE = {r.get('pce', 0):.1f} (عتبة التطابق القوي 60) · "
                f"بصمة مبنية من {r.get('fingerprint_images')} صورة")
        elif r.get("level") == "strong_shifted":
            add("عالية", 18, "⚠️ مطابقة PRNU مع إزاحة — الصورة مقصوصة",
                f"الصورة من الكاميرا «{r.get('camera_name')}» لكن إطارها مزاح "
                f"بمقدار {r.get('detected_shift')} بكسل عن الأصل — دليل قصّ.",
                f"PCE عند الإزاحة = {r.get('pce_best_shift', 0):.1f}")

    rec = rep.get("recovery", {})
    has_main = bool((jp.get("app_payloads") or {}).get("Exif") or png.get("exif")
                    or (c.get("tiff") or {}).get("ok") or (c.get("iso_bmff") or {}).get("exif"))
    if rec.get("exif_fragments") and not has_main:
        add("عالية", 18, "آثار بيانات وصفية ممسوحة",
            "لا يوجد EXIF في موضعه القياسي، لكن استُرجعت شظايا EXIF حقيقية من داخل البايتات.",
            f"عدد الشظايا: {len(rec['exif_fragments'])}")
    if rec.get("embedded_images"):
        add("معلوماتية", 5, "صور مدمجة مستخرجة",
            "استُخرجت صور/مصغّرات مدمجة قد تحمل محتوى أو ميتاداتا قبل التعديل.",
            f"العدد: {len(rec['embedded_images'])}")

    imgf = rep.get("image_forensics", {})
    tc = imgf.get("thumbnail_check") or {}
    if tc.get("applicable") and any("⚠️" in v for v in tc.get("verdict", [])):
        add("حرجة", 28, "تعارض الصورة المصغّرة مع الصورة",
            " ".join(tc["verdict"]),
            f"ارتباط = {tc.get('correlation')} ، MSE = {tc.get('mse')}")
    dc = imgf.get("double_compression") or {}
    if dc.get("applicable") and dc.get("flag_ratio", 0) >= 0.35:
        add("عالية", 16, "ضغط JPEG مزدوج", dc.get("verdict", ""),
            f"معاملات دورية: {dc['periodic_flags']}/{dc.get('tested')} — "
            f"كتل مُحلَّلة: {dc.get('blocks_analyzed')}")
    elif dc.get("applicable") and dc.get("flag_ratio", 0) >= 0.2:
        add("متوسطة", 8, "اشتباه بضغط JPEG مزدوج", dc.get("verdict", ""),
            f"نسبة المعاملات الدورية: {dc.get('flag_ratio')}")
    bf = imgf.get("coefficient_statistics") or {}
    tv = (bf.get("generalized_benford_fit") or {}).get("total_variation")
    if bf.get("applicable") and tv is not None and tv > 0.05:
        add("متوسطة", 10, "انحراف معاملات DCT عن قانون بنفورد المعمّم",
            bf.get("interpretation", ""),
            f"مسافة التباين الكلي عن النموذج الملائم: {tv} (الحد الطبيعي < 0.05)")
    cm = imgf.get("copy_move") or {}
    if cm.get("detected"):
        add("حرجة", 30, "نسخ ولصق داخلي (Copy-Move)",
            cm.get("interpretation", ""),
            f"متجه الإزاحة الأقوى: {cm['top_shift_vectors'][0] if cm.get('top_shift_vectors') else ''}")
    noise = imgf.get("noise") or {}
    if len(noise.get("anomalous_regions", [])) >= 5:
        add("متوسطة", 12, "مناطق ضجيج شاذة",
            "عدة مناطق يختلف فيها الضجيج جوهريًا عن محيطها — احتمال إدراج/تنعيم موضعي.",
            f"عدد المناطق: {len(noise['anomalous_regions'])}")
    ela_r = imgf.get("ela") or {}
    if ela_r.get("regions_found", 0) >= 8:
        add("منخفضة", 8, "مناطق ELA مرتفعة",
            "مناطق ذات مستوى خطأ أعلى بكثير من محيطها (تحتاج تأييدًا من أدلة أخرى).",
            f"عدد المناطق: {ela_r['regions_found']}")
    steg = imgf.get("steganalysis") or {}
    if any("⚠️" in v for v in steg.get("verdict", [])):
        add("عالية", 16, "مؤشرات إخفاء معلومات (Steganography)",
            " ".join(steg["verdict"]),
            f"كاي-تربيع: {steg.get('chi_square', {}).get('suspicious_fraction')}")
    hist = imgf.get("histogram") or {}
    if (hist.get("comb_artifact", {}).get("avg_empty_bins") or 0) > 40:
        add("متوسطة", 10, "أثر معالجة على المدرج التكراري",
            hist["comb_artifact"]["note"],
            f"متوسط الفجوات: {hist['comb_artifact']['avg_empty_bins']}")

    pdf = c.get("pdf") or {}
    if pdf.get("incremental_updates", 0) > 0:
        add("عالية", 15, "تحديثات تزايدية في PDF", pdf.get("incremental_note", ""),
            f"عدد مؤشرات %%EOF: {pdf.get('eof_markers')}")
    for r in pdf.get("risk_indicators", []):
        if r["marker"] in ("/JavaScript", "/Launch", "/OpenAction", "/EmbeddedFile"):
            add("عالية", 14, f"عنصر خطر في PDF: {r['marker']}", r["risk"], f"عدد التكرارات: {r['count']}")
    if (pdf.get("document_id") or {}).get("changed"):
        add("متوسطة", 10, "تغيّر معرّف مستند PDF", pdf["document_id"]["note"], str(pdf["document_id"]))

    ooxml = c.get("ooxml_zip") or {}
    if ooxml.get("has_macros"):
        add("عالية", 18, "ماكرو VBA داخل المستند", ooxml["macro_warning"], "vbaProject.bin")
    if ooxml.get("tracked_changes"):
        add("متوسطة", 12, "تعديلات متتبّعة غير مقبولة", ooxml.get("tracked_note", ""),
            f"المحرّرون: {', '.join(ooxml.get('revision_authors', [])[:5])}")

    ent = rep.get("entropy", {})
    for a in ent.get("anomalies", [])[:3]:
        add("متوسطة", 9, "شذوذ في العشوائية", a["note"],
            f"إزاحة {a['offset']} ، إنتروبيا {a['entropy']}")

    # استبعاد الملفات التي تنتمي أصلًا لبنية الحاوية نفسها (مثل إدخالات ZIP داخل أرشيف)
    own = {"zip": {"zip"}, "docx": {"zip", "xml"}, "xlsx": {"zip", "xml"}, "pptx": {"zip", "xml"},
           "apk": {"zip", "xml", "dex"}, "jar": {"zip", "xml"}, "epub": {"zip", "xml"},
           "odf": {"zip", "xml"}, "jpg": {"jpeg"}, "jpeg": {"jpeg"}, "png": {"png"},
           "pdf": {"pdf", "xml"}, "tif": {"tiff"}, "gz": {"gzip"}}.get(
               (rep.get("type") or {}).get("extension_real", ""), set())
    carved = [x for x in rep.get("carving", []) if x.get("extracted") and x["type"] not in own]
    if carved:
        add("عالية", 16, "ملفات مدمجة مستخرجة بالنحت",
            "عُثر على ملفات كاملة مخبّأة داخل الدليل واستُخرجت فعليًا.",
            ", ".join(f"{x['type']}@{x['offset']}" for x in carved[:6]))

    for conf in (rep.get("timeline") or {}).get("conflicts", []):
        if conf["severity"] == "عالية":
            add("عالية", 16, f"تضارب زمني: {conf['event']}", conf["issue"], "مقارنة الطوابع الزمنية")
        elif conf["severity"] == "متوسطة":
            add("متوسطة", 8, f"ملاحظة زمنية: {conf['event']}", conf["issue"], "مقارنة الطوابع الزمنية")

    iocs = (rep.get("strings") or {}).get("iocs", {})
    if iocs:
        add("معلوماتية", 3, "مؤشرات مستخرجة من النص الخام",
            "استُخرجت مؤشرات هوية/شبكة من بايتات الملف.",
            "، ".join(f"{k}: {len(v)}" for k, v in list(iocs.items())[:6]))

    score = min(100, sum(f["weight"] for f in findings))
    if score >= 60:
        level, color = "مرتفع جدًا — مؤشرات تلاعب قوية", "critical"
    elif score >= 35:
        level, color = "مرتفع — يستدعي فحصًا يدويًا معمّقًا", "high"
    elif score >= 15:
        level, color = "متوسط — ملاحظات تستحق المتابعة", "medium"
    elif score > 0:
        level, color = "منخفض — ملاحظات طفيفة", "low"
    else:
        level, color = "لا مؤشرات تلاعب مرصودة", "clean"

    findings.sort(key=lambda f: -f["weight"])
    return {
        "suspicion_score": score, "level": level, "level_class": color,
        "findings": findings,
        "findings_count": len(findings),
        "disclaimer": (
            "هذا المؤشر أداة فرز تقني مبنية على قياسات فعلية للملف، وليس حكمًا قضائيًا. "
            "كل نتيجة مرفقة بالدليل البايتي أو الإحصائي الذي بُنيت عليه ليتحقق منه الخبير يدويًا، "
            "ويجب تأييد أي استنتاج بأكثر من دليل مستقل قبل اعتماده."
        ),
    }


def _hsize(n: int) -> str:
    for u in ("بايت", "ك.بايت", "م.بايت", "غ.بايت"):
        if n < 1024 or u == "غ.بايت":
            return f"{n:.2f} {u}" if u != "بايت" else f"{n} {u}"
        n /= 1024
    return str(n)
