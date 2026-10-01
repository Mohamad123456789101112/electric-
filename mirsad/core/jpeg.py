"""
تشريح ملف JPEG على مستوى المقاطع (markers) — تحليل حقيقي بالبايت:
جداول التكميم (بصمة الكاميرا/البرنامج)، جودة الضغط، ترتيب المقاطع، XMP/IPTC/ICC/MPF،
البيانات الملحقة بعد نهاية الصورة، والصور المصغّرة المدمجة.
"""
from __future__ import annotations

import hashlib
import struct
import zlib
from . import exif as exif_mod

MARKERS = {
    0xC0: ("SOF0", "بداية إطار — خط أساس (Baseline DCT)"),
    0xC1: ("SOF1", "بداية إطار — متتابع ممتد"),
    0xC2: ("SOF2", "بداية إطار — تقدمي (Progressive DCT)"),
    0xC3: ("SOF3", "بداية إطار — بدون فقد"),
    0xC4: ("DHT", "جدول هوفمان"),
    0xC8: ("JPG", "امتداد JPEG"),
    0xC9: ("SOF9", "إطار حسابي متتابع"),
    0xCA: ("SOF10", "إطار حسابي تقدمي"),
    0xCC: ("DAC", "تعريف الترميز الحسابي"),
    0xD8: ("SOI", "بداية الصورة"),
    0xD9: ("EOI", "نهاية الصورة"),
    0xDA: ("SOS", "بداية المسح (بيانات الصورة)"),
    0xDB: ("DQT", "جدول التكميم"),
    0xDC: ("DNL", "تعريف عدد الأسطر"),
    0xDD: ("DRI", "فاصل إعادة التشغيل"),
    0xE0: ("APP0", "JFIF"),
    0xE1: ("APP1", "Exif / XMP"),
    0xE2: ("APP2", "ICC Profile / MPF"),
    0xE3: ("APP3", "Meta / Kodak"),
    0xE4: ("APP4", "Scalado / بيانات مُصنّع"),
    0xE5: ("APP5", "بيانات مُصنّع"),
    0xE6: ("APP6", "NITF / EPPIM"),
    0xE7: ("APP7", "Pentax / بيانات مُصنّع"),
    0xE8: ("APP8", "SPIFF"),
    0xE9: ("APP9", "MediaJukebox"),
    0xEA: ("APP10", "تعليق PhotoStudio"),
    0xEB: ("APP11", "HELIOS / JUMBF"),
    0xEC: ("APP12", "Ducky / Picture Info (Photoshop «Save for Web»)"),
    0xED: ("APP13", "Photoshop IRB / IPTC"),
    0xEE: ("APP14", "Adobe (DCTDecode)"),
    0xEF: ("APP15", "بيانات مُصنّع"),
    0xFE: ("COM", "تعليق نصي"),
}

# جداول التكميم القياسية (JPEG Annex K) للإضاءة واللون — تُستخدم لتقدير الجودة
STD_LUMA = [
    16, 11, 10, 16, 24, 40, 51, 61, 12, 12, 14, 19, 26, 58, 60, 55,
    14, 13, 16, 24, 40, 57, 69, 56, 14, 17, 22, 29, 51, 87, 80, 62,
    18, 22, 37, 56, 68, 109, 103, 77, 24, 35, 55, 64, 81, 104, 113, 92,
    49, 64, 78, 87, 103, 121, 120, 101, 72, 92, 95, 98, 112, 100, 103, 99]
STD_CHROMA = [
    17, 18, 24, 47, 99, 99, 99, 99, 18, 21, 26, 66, 99, 99, 99, 99,
    24, 26, 56, 99, 99, 99, 99, 99, 47, 66, 99, 99, 99, 99, 99, 99,
    99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99,
    99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99]


# ترتيب الزجزاج: جداول DQT تُخزَّن به داخل الملف بينما جداول Annex K أعلاه صفّية
ZIGZAG_ORDER = [
    0, 1, 8, 16, 9, 2, 3, 10, 17, 24, 32, 25, 18, 11, 4, 5,
    12, 19, 26, 33, 40, 48, 41, 34, 27, 20, 13, 6, 7, 14, 21, 28,
    35, 42, 49, 56, 57, 50, 43, 36, 29, 22, 15, 23, 30, 37, 44, 51,
    58, 59, 52, 45, 38, 31, 39, 46, 53, 60, 61, 54, 47, 55, 62, 63]


def estimate_quality(qt: list[int], chroma: bool = False) -> float:
    """تقدير جودة libjpeg من جدول التكميم (معادلة مقياس IJG العكسية)."""
    std = STD_CHROMA if chroma else STD_LUMA
    if len(qt) >= 64:                       # فكّ ترتيب الزجزاج قبل المقارنة
        raster = [0] * 64
        for i, pos in enumerate(ZIGZAG_ORDER):
            raster[pos] = qt[i]
        qt = raster
    scales = []
    for q, s in zip(qt, std):
        if q <= 0:
            continue
        scales.append(q * 100.0 / s)
    if not scales:
        return 0.0
    scale = sum(scales) / len(scales)
    if scale <= 100:
        quality = (200 - scale) / 2.0
    else:
        quality = 5000.0 / scale
    return round(max(0.0, min(100.0, quality)), 2)


def parse(data: bytes) -> dict:
    """تمشية كاملة لمقاطع JPEG."""
    out: dict = {"is_jpeg": False, "segments": [], "warnings": [], "app_payloads": {}}
    if data[:2] != b"\xFF\xD8":
        return out
    out["is_jpeg"] = True
    i = 2
    n = len(data)
    sos_end = None
    dqt_tables: list[dict] = []
    dht_tables: list[dict] = []
    dht_count = 0
    while i < n - 1:
        if data[i] != 0xFF:
            # إعادة تزامن
            j = data.find(b"\xFF", i)
            if j < 0:
                break
            i = j
            continue
        m = data[i + 1]
        if m in (0xFF, 0x00):
            i += 1
            continue
        if m == 0xD8:
            out["segments"].append({"marker": "SOI", "offset": i, "size": 2, "desc": MARKERS[0xD8][1]})
            i += 2
            continue
        if m == 0xD9:
            out["segments"].append({"marker": "EOI", "offset": i, "size": 2, "desc": MARKERS[0xD9][1]})
            out["eoi_offset"] = i
            i += 2
            break
        if 0xD0 <= m <= 0xD7:
            i += 2
            continue
        if i + 4 > n:
            out["warnings"].append(f"مقطع مقطوع عند الإزاحة {i} — الملف تالف أو مبتور.")
            break
        ln = struct.unpack_from(">H", data, i + 2)[0]
        name, desc = MARKERS.get(m, (f"0x{m:02X}", "مقطع غير معروف"))
        payload = data[i + 4:i + 2 + ln]
        seg = {"marker": name, "offset": i, "size": ln + 2, "desc": desc}

        if name == "DQT":
            p = 0
            while p < len(payload):
                pq_tq = payload[p]
                prec, tid = pq_tq >> 4, pq_tq & 15
                p += 1
                cnt = 64
                if prec == 0:
                    tbl = list(payload[p:p + 64]); p += 64
                else:
                    tbl = list(struct.unpack_from(">64H", payload, p)); p += 128
                if len(tbl) < cnt:
                    break
                q = estimate_quality(tbl, chroma=(tid != 0))
                dqt_tables.append({"table_id": tid, "precision_bits": 8 if prec == 0 else 16,
                                   "values": tbl, "estimated_quality": q,
                                   "sum": sum(tbl), "crc32": format(zlib.crc32(bytes(min(x, 255) for x in tbl)) & 0xFFFFFFFF, "08x")})
            seg["tables"] = len(dqt_tables)
        elif name == "DHT":
            dht_count += 1
            # تشريح كامل لجداول هوفمان: بصمتها جزء أصيل من توقيع المُرمِّز
            # (الكاميرات تستخدم الجداول القياسية، وبرامج التحرير غالبًا تُحسّنها)
            q = 0
            while q + 17 <= len(payload):
                tc_th = payload[q]
                tcls, tid = tc_th >> 4, tc_th & 15
                counts = list(payload[q + 1:q + 17])
                total = sum(counts)
                if q + 17 + total > len(payload) or total > 256:
                    break
                symbols = list(payload[q + 17:q + 17 + total])
                dht_tables.append({
                    "class": "DC" if tcls == 0 else "AC", "table_id": tid,
                    "codes_per_length": counts, "symbol_count": total,
                    "sha1": hashlib.sha1(bytes(counts) + bytes(symbols)).hexdigest()[:16],
                })
                q += 17 + total
        elif name.startswith("SOF"):
            if len(payload) >= 6:
                prec = payload[0]
                h, w = struct.unpack_from(">HH", payload, 1)
                nc = payload[5]
                comps = []
                for c in range(nc):
                    base = 6 + c * 3
                    if base + 3 <= len(payload):
                        cid, hv, tq = payload[base], payload[base + 1], payload[base + 2]
                        comps.append({"id": cid, "sampling": f"{hv >> 4}x{hv & 15}", "quant_table": tq})
                out["frame"] = {"precision": prec, "width": w, "height": h,
                                "components": nc, "component_detail": comps,
                                "progressive": name == "SOF2",
                                "subsampling": _subsampling(comps)}
        elif name == "SOS":
            seg["note"] = "بعدها تبدأ بيانات البكسل المضغوطة"
            out["sos_offset"] = i
        elif name.startswith("APP") or name == "COM":
            _handle_app(out, name, payload, i)

        out["segments"].append(seg)
        i += 2 + ln
        if name == "SOS":
            # تخطي بيانات المسح حتى EOI
            j = i
            while j < n - 1:
                if data[j] == 0xFF and data[j + 1] not in (0x00,) and not (0xD0 <= data[j + 1] <= 0xD7):
                    break
                j += 1
            i = j
            sos_end = j
    out["quant_tables"] = dqt_tables
    out["huffman_tables_segments"] = dht_count
    out["huffman_tables"] = dht_tables
    if dqt_tables:
        out["estimated_jpeg_quality"] = max(t["estimated_quality"] for t in dqt_tables)
        out["quant_fingerprint"] = "-".join(t["crc32"] for t in dqt_tables)

    eoi = out.get("eoi_offset")
    if eoi is None:
        last = data.rfind(b"\xFF\xD9")
        eoi = last if last > 0 else None
        if eoi is not None:
            out["eoi_offset"] = eoi
            out["warnings"].append("لم يُعثر على EOI في المسار الطبيعي — استُخدم آخر FFD9 في الملف.")
    if eoi is not None:
        trailing = data[eoi + 2:]
        if trailing:
            out["trailing_data"] = {
                "offset": eoi + 2, "size": len(trailing),
                "preview_hex": trailing[:256].hex(" "),
                "preview_text": trailing[:512].decode("utf-8", "replace"),
                "note": "⚠️ بيانات ملحقة بعد نهاية الصورة (FFD9) — موضع كلاسيكي لإخفاء ملفات "
                        "أو أرشيف مدمج أو بقايا من ملف أكبر.",
            }
    if sos_end:
        out["scan_data_bytes"] = max(0, (eoi or len(data)) - sos_end)
    return out


def _subsampling(comps: list[dict]) -> str:
    if not comps:
        return "غير معروف"
    try:
        h0, v0 = comps[0]["sampling"].split("x")
        h0, v0 = int(h0), int(v0)
        if len(comps) == 1:
            return "تدرج رمادي"
        if (h0, v0) == (2, 2):
            return "4:2:0 (ضغط لوني عالي — نمط هواتف/كاميرات)"
        if (h0, v0) == (2, 1):
            return "4:2:2"
        if (h0, v0) == (1, 1):
            return "4:4:4 (بدون تقليل لوني — نمط برامج تحرير/جودة عالية)"
        return f"{h0}x{v0}"
    except Exception:
        return "غير معروف"


def _handle_app(out: dict, name: str, payload: bytes, offset: int) -> None:
    ap = out["app_payloads"]
    if name == "APP0" and payload.startswith(b"JFIF\x00"):
        if len(payload) >= 14:
            vmaj, vmin, units, xd, yd, tw, th = struct.unpack_from(">BBBHHBB", payload, 5)
            ap["JFIF"] = {"version": f"{vmaj}.{vmin:02d}",
                          "density_units": {0: "نسبة فقط", 1: "نقطة/بوصة", 2: "نقطة/سم"}.get(units, units),
                          "x_density": xd, "y_density": yd,
                          "thumbnail": f"{tw}x{th}"}
            if tw and th:
                ap["JFIF"]["embedded_thumb_bytes"] = tw * th * 3
    elif name == "APP1" and payload.startswith(b"Exif\x00\x00"):
        ap.setdefault("Exif_offsets", []).append(offset)
        tiff = exif_mod.parse_tiff(payload[6:], 0)
        thumb = tiff.pop("_thumbnail_bytes", None)
        ap["Exif"] = tiff
        if thumb:
            out.setdefault("_thumbnails", []).append({"source": "EXIF IFD1", "bytes": thumb})
    elif name == "APP1" and (b"<x:xmpmeta" in payload or payload.startswith(b"http://ns.adobe.com/xap/1.0/")):
        txt = payload.split(b"\x00", 1)[-1].decode("utf-8", "replace")
        ap.setdefault("XMP", "")
        ap["XMP"] += txt
    elif name == "APP2" and payload.startswith(b"ICC_PROFILE\x00"):
        icc = payload[14:]
        ap.setdefault("ICC_chunks", 0)
        ap["ICC_chunks"] += 1
        ap["ICC"] = parse_icc(icc)
    elif name == "APP2" and payload.startswith(b"MPF\x00"):
        ap["MPF"] = {"note": "صورة متعددة الصور (MPF) — شائعة في هواتف سامسونج/أبل (وضع الصور المزدوجة)",
                     "size": len(payload)}
    elif name == "APP12":
        ap["Ducky_APP12"] = payload[:200].decode("latin-1", "replace")
    elif name == "APP13" and payload.startswith(b"Photoshop 3.0\x00"):
        ap["Photoshop_IRB"] = parse_irb(payload[14:])
    elif name == "APP14" and payload.startswith(b"Adobe"):
        ap["Adobe_APP14"] = {
            "version": struct.unpack_from(">H", payload, 5)[0] if len(payload) >= 7 else None,
            "transform": payload[11] if len(payload) > 11 else None,
            "note": "وجود مقطع Adobe APP14 يدل غالبًا على حفظ الملف ببرنامج أدوبي.",
        }
    elif name == "COM":
        ap.setdefault("Comments", []).append(payload[:1000].decode("utf-8", "replace"))
    elif name.startswith("APP"):
        ap.setdefault("other_app_segments", []).append(
            {"marker": name, "offset": offset, "size": len(payload),
             "ascii_head": payload[:32].decode("latin-1", "replace")})


def parse_icc(icc: bytes) -> dict:
    """قراءة ترويسة ملف تعريف ألوان ICC — تكشف الجهاز/البرنامج المنتج."""
    if len(icc) < 132:
        return {"error": "ملف تعريف ICC قصير/مقطوع", "size": len(icc)}
    try:
        size, cmm, ver, cls, space, pcs = struct.unpack_from(">I4sI4s4s4s", icc, 0)
        y, mo, d, h, mi, s = struct.unpack_from(">6H", icc, 24)
        sig, plat = struct.unpack_from(">4s4s", icc, 36)
        manuf, model = struct.unpack_from(">4s4s", icc, 48)
        creator = icc[80:84]
        out = {
            "profile_size": size,
            "cmm": cmm.decode("latin-1", "replace").strip("\x00 "),
            "version": f"{ver >> 24}.{(ver >> 20) & 15}.{(ver >> 16) & 15}",
            "device_class": cls.decode("latin-1", "replace").strip(),
            "color_space": space.decode("latin-1", "replace").strip(),
            "pcs": pcs.decode("latin-1", "replace").strip(),
            "created": f"{y:04d}-{mo:02d}-{d:02d} {h:02d}:{mi:02d}:{s:02d}",
            "platform": plat.decode("latin-1", "replace").strip("\x00 "),
            "manufacturer": manuf.decode("latin-1", "replace").strip("\x00 "),
            "model": model.decode("latin-1", "replace").strip("\x00 "),
            "creator": creator.decode("latin-1", "replace").strip("\x00 "),
        }
        # وسم الوصف desc
        tag_count = struct.unpack_from(">I", icc, 128)[0]
        tags = {}
        for i in range(min(tag_count, 100)):
            off = 132 + i * 12
            if off + 12 > len(icc):
                break
            sgn, toff, tsize = struct.unpack_from(">4sII", icc, off)
            tags[sgn.decode("latin-1", "replace")] = (toff, tsize)
        for key in ("desc", "cprt", "dmnd", "dmdd"):
            if key in tags:
                toff, tsize = tags[key]
                blob = icc[toff:toff + min(tsize, 2048)]
                txt = _icc_text(blob)
                if txt:
                    out[{"desc": "description", "cprt": "copyright",
                         "dmnd": "device_manufacturer", "dmdd": "device_model"}[key]] = txt
        out["tags"] = list(tags.keys())
        return out
    except Exception as e:  # pragma: no cover
        return {"error": f"تعذّر تحليل ICC: {e}"}


def _icc_text(blob: bytes) -> str:
    if blob[:4] == b"desc":
        ln = struct.unpack_from(">I", blob, 8)[0]
        return blob[12:12 + max(0, ln - 1)].decode("latin-1", "replace")
    if blob[:4] in (b"mluc",):
        try:
            n = struct.unpack_from(">I", blob, 8)[0]
            if n:
                ln, off = struct.unpack_from(">II", blob, 20)
                return blob[off:off + ln].decode("utf-16-be", "replace")
        except Exception:
            return ""
    if blob[:4] == b"text":
        return blob[8:].split(b"\x00")[0].decode("latin-1", "replace")
    return ""


IPTC_TAGS = {
    5: "عنوان الكائن (Object Name)", 7: "حالة التحرير", 10: "الأولوية", 15: "الفئة",
    20: "فئات إضافية", 25: "الكلمات المفتاحية", 40: "تعليمات خاصة", 55: "تاريخ الإنشاء",
    60: "وقت الإنشاء", 62: "التاريخ الرقمي", 63: "الوقت الرقمي", 65: "برنامج الإنشاء",
    70: "إصدار البرنامج", 80: "اسم المصوّر (By-line)", 85: "وظيفة المصوّر", 90: "المدينة",
    92: "الموقع التفصيلي", 95: "الولاية/المحافظة", 100: "رمز الدولة", 101: "الدولة",
    103: "مرجع الإرسال الأصلي", 105: "عنوان رئيسي", 110: "جهة التزويد (Credit)",
    115: "المصدر", 116: "إشعار حقوق النشر", 118: "جهة الاتصال", 120: "الوصف/التعليق",
    122: "كاتب الوصف",
}


def parse_irb(blob: bytes) -> dict:
    """قراءة كتل Photoshop Image Resource Blocks بما فيها IPTC (8BIM/0x0404)."""
    out: dict = {"blocks": [], "IPTC": {}}
    i = 0
    while i + 12 <= len(blob):
        if blob[i:i + 4] != b"8BIM":
            break
        rid = struct.unpack_from(">H", blob, i + 4)[0]
        nlen = blob[i + 6]
        pad = nlen + 1 + (1 - ((nlen + 1) % 2))
        p = i + 6 + pad
        if p + 4 > len(blob):
            break
        dlen = struct.unpack_from(">I", blob, p)[0]
        data = blob[p + 4:p + 4 + dlen]
        names = {0x0404: "IPTC-NAA", 0x040F: "ICC Profile", 0x0422: "EXIF data",
                 0x0425: "Caption digest", 0x0426: "Print scale", 0x043A: "Print flags",
                 0x0408: "Grid & guides", 0x041A: "Slices", 0x040C: "Thumbnail",
                 0x0421: "Version info", 0x0424: "XMP metadata", 0x1005: "Resolution info"}
        out["blocks"].append({"id": f"0x{rid:04X}", "name": names.get(rid, "غير معروف"), "size": dlen})
        if rid == 0x0404:
            out["IPTC"] = _parse_iptc(data)
        if rid == 0x040C and len(data) > 28:
            out["_photoshop_thumbnail"] = data[28:]
        i = p + 4 + dlen + (dlen % 2)
    return out


def _parse_iptc(data: bytes) -> dict:
    out: dict = {}
    i = 0
    while i + 5 <= len(data):
        if data[i] != 0x1C:
            i += 1
            continue
        rec, ds = data[i + 1], data[i + 2]
        ln = struct.unpack_from(">H", data, i + 3)[0]
        i += 5
        if ln & 0x8000:
            nb = ln & 0x7FFF
            ln = int.from_bytes(data[i:i + nb], "big")
            i += nb
        val = data[i:i + ln].decode("utf-8", "replace")
        i += ln
        if rec == 2:
            key = IPTC_TAGS.get(ds, f"IPTC 2:{ds}")
            if key in out:
                out[key] = (out[key] if isinstance(out[key], list) else [out[key]]) + [val]
            else:
                out[key] = val
    return out
