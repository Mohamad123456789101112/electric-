"""
محلّلات الحاويات: PNG, GIF, WebP/RIFF, ISO-BMFF (MP4/MOV/HEIC/AVIF), Matroska.
قراءة فعلية للـ chunks/atoms واستخراج كل البيانات الوصفية والطوابع الزمنية.
"""
from __future__ import annotations

import struct
import zlib
from datetime import datetime, timedelta, timezone

from . import exif as exif_mod
from . import jpeg as jpeg_mod

# ------------------------------------------------------------------------ PNG

PNG_CHUNK_DESC = {
    b"IHDR": "ترويسة الصورة", b"PLTE": "لوحة الألوان", b"IDAT": "بيانات البكسل",
    b"IEND": "نهاية الصورة", b"tEXt": "نص لاتيني", b"zTXt": "نص مضغوط",
    b"iTXt": "نص دولي (UTF-8) — يحمل XMP غالبًا", b"tIME": "وقت آخر تعديل",
    b"pHYs": "الأبعاد الفيزيائية", b"gAMA": "جاما", b"cHRM": "إحداثيات اللون",
    b"sRGB": "فضاء sRGB", b"iCCP": "ملف تعريف ICC مضغوط", b"bKGD": "لون الخلفية",
    b"tRNS": "الشفافية", b"sBIT": "بتات ذات دلالة", b"hIST": "مدرج تكراري",
    b"eXIf": "بيانات EXIF مدمجة", b"acTL": "تحكم الحركة (APNG)", b"fcTL": "إطار APNG",
    b"fdAT": "بيانات إطار APNG", b"caBX": "صندوق C2PA (توثيق المحتوى)",
    b"prVW": "معاينة", b"vpAg": "صفحة افتراضية (ImageMagick)",
}
COLOR_TYPES = {0: "تدرج رمادي", 2: "RGB", 3: "لوحة ألوان", 4: "رمادي + ألفا", 6: "RGBA"}


def parse_png(data: bytes) -> dict:
    out: dict = {"is_png": False, "chunks": [], "text": {}, "warnings": []}
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return out
    out["is_png"] = True
    i = 8
    n = len(data)
    while i + 8 <= n:
        ln = struct.unpack_from(">I", data, i)[0]
        ctype = data[i + 4:i + 8]
        body = data[i + 8:i + 8 + ln]
        crc_at = i + 8 + ln
        if crc_at + 4 > n:
            out["warnings"].append(f"كتلة {ctype.decode('latin-1','replace')} مبتورة عند {i} — الملف تالف أو مقطوع.")
            break
        stored_crc = struct.unpack_from(">I", data, crc_at)[0]
        calc_crc = zlib.crc32(ctype + body) & 0xFFFFFFFF
        entry = {"type": ctype.decode("latin-1", "replace"), "offset": i, "length": ln,
                 "desc": PNG_CHUNK_DESC.get(ctype, "كتلة غير قياسية/خاصة"),
                 "crc_ok": stored_crc == calc_crc}
        if not entry["crc_ok"]:
            out["warnings"].append(
                f"⚠️ CRC غير مطابق للكتلة {entry['type']} عند {i} — دليل قوي على تعديل/حقن بيانات داخل الملف.")
        out["chunks"].append(entry)

        if ctype == b"IHDR" and ln >= 13:
            w, h, depth, ct, comp, filt, inter = struct.unpack_from(">IIBBBBB", body, 0)
            out["header"] = {"width": w, "height": h, "bit_depth": depth,
                             "color_type": COLOR_TYPES.get(ct, ct), "interlaced": bool(inter)}
        elif ctype == b"tEXt":
            k, _, v = body.partition(b"\x00")
            out["text"][k.decode("latin-1", "replace")] = v.decode("latin-1", "replace")[:5000]
        elif ctype == b"zTXt":
            k, _, rest = body.partition(b"\x00")
            try:
                v = zlib.decompress(rest[1:]).decode("utf-8", "replace")
            except Exception:
                v = "<تعذّر فك الضغط>"
            out["text"][k.decode("latin-1", "replace") + " (مضغوط)"] = v[:5000]
        elif ctype == b"iTXt":
            parts = body.split(b"\x00", 5)
            if len(parts) >= 6:
                key, cflag, cmethod, lang, tkey, val = parts[0], parts[1][:1], parts[1][1:2], parts[2], parts[3], parts[-1]
                try:
                    if parts[1][:1] == b"\x01":
                        val = zlib.decompress(val)
                except Exception:
                    pass
                out["text"][key.decode("latin-1", "replace")] = val.decode("utf-8", "replace")[:20000]
        elif ctype == b"tIME" and ln >= 7:
            y, mo, d, h, mi, s = struct.unpack_from(">HBBBBB", body, 0)
            out["last_modified_chunk"] = f"{y:04d}-{mo:02d}-{d:02d}T{h:02d}:{mi:02d}:{s:02d}Z"
        elif ctype == b"pHYs" and ln >= 9:
            px, py, unit = struct.unpack_from(">IIB", body, 0)
            out["physical"] = {"x_per_unit": px, "y_per_unit": py,
                               "unit": "متر" if unit == 1 else "غير محدد",
                               "dpi": round(px * 0.0254) if unit == 1 else None}
        elif ctype == b"eXIf":
            out["exif"] = exif_mod.parse_tiff(body, 0)
        elif ctype == b"iCCP":
            name, _, rest = body.partition(b"\x00")
            try:
                icc = zlib.decompress(rest[1:])
                out["icc"] = jpeg_mod.parse_icc(icc)
                out["icc"]["profile_name"] = name.decode("latin-1", "replace")
            except Exception:
                pass
        i = crc_at + 4
        if ctype == b"IEND":
            trailing = data[i:]
            if trailing:
                out["trailing_data"] = {
                    "offset": i, "size": len(trailing),
                    "preview_hex": trailing[:256].hex(" "),
                    "preview_text": trailing[:512].decode("utf-8", "replace"),
                    "note": "⚠️ بيانات بعد IEND — إخفاء محتمل أو بقايا ملف أصلي أكبر."}
            break
    if "XML:com.adobe.xmp" in out["text"]:
        out["xmp"] = out["text"]["XML:com.adobe.xmp"]
    return out


# ------------------------------------------------------------------------ GIF

def parse_gif(data: bytes) -> dict:
    out: dict = {"is_gif": False, "comments": [], "app_extensions": [], "frames": 0}
    if data[:6] not in (b"GIF87a", b"GIF89a"):
        return out
    out["is_gif"] = True
    out["version"] = data[:6].decode()
    w, h, flags, bg, par = struct.unpack_from("<HHBBB", data, 6)
    out["screen"] = {"width": w, "height": h, "global_color_table": bool(flags & 0x80),
                     "color_resolution_bits": ((flags >> 4) & 7) + 1,
                     "gct_size": 2 ** ((flags & 7) + 1) if flags & 0x80 else 0}
    i = 13 + (3 * out["screen"]["gct_size"] if flags & 0x80 else 0)
    n = len(data)
    delays = []
    while i < n:
        b = data[i]
        if b == 0x3B:
            i += 1
            break
        if b == 0x21:  # extension
            label = data[i + 1]
            i += 2
            blocks = []
            while i < n and data[i]:
                ln = data[i]
                blocks.append(data[i + 1:i + 1 + ln])
                i += 1 + ln
            i += 1
            payload = b"".join(blocks)
            if label == 0xFE:
                out["comments"].append(payload.decode("utf-8", "replace")[:2000])
            elif label == 0xFF:
                out["app_extensions"].append(payload[:11].decode("latin-1", "replace"))
            elif label == 0xF9 and len(payload) >= 4:
                delays.append(struct.unpack_from("<H", payload, 1)[0] * 10)
        elif b == 0x2C:
            out["frames"] += 1
            lflags = data[i + 9]
            i += 10 + (3 * 2 ** ((lflags & 7) + 1) if lflags & 0x80 else 0)
            i += 1  # LZW min code size
            while i < n and data[i]:
                i += 1 + data[i]
            i += 1
        else:
            i += 1
    if delays:
        out["animation"] = {"frames": out["frames"], "total_ms": sum(delays),
                            "frame_delays_ms": delays[:200]}
    if i < n:
        out["trailing_data"] = {"offset": i, "size": n - i,
                                "preview_hex": data[i:i + 128].hex(" "),
                                "note": "⚠️ بيانات بعد نهاية GIF."}
    return out


# ----------------------------------------------------------------------- RIFF

def parse_riff(data: bytes) -> dict:
    out: dict = {"is_riff": False, "chunks": [], "metadata": {}}
    if data[:4] != b"RIFF":
        return out
    out["is_riff"] = True
    size = struct.unpack_from("<I", data, 4)[0]
    out["form"] = data[8:12].decode("latin-1", "replace")
    out["declared_size"] = size + 8
    out["actual_size"] = len(data)
    if size + 8 != len(data):
        out.setdefault("warnings", []).append(
            f"⚠️ الحجم المعلن في الترويسة ({size + 8}) يخالف الحجم الفعلي ({len(data)}) — "
            "بيانات ملحقة أو بتر.")
    i = 12
    while i + 8 <= len(data):
        cid = data[i:i + 4]
        clen = struct.unpack_from("<I", data, i + 4)[0]
        body = data[i + 8:i + 8 + clen]
        out["chunks"].append({"id": cid.decode("latin-1", "replace"), "offset": i, "size": clen})
        if cid == b"EXIF":
            out["exif"] = exif_mod.parse_tiff(body[6:] if body[:6] == b"Exif\x00\x00" else body, 0)
        elif cid == b"XMP ":
            out["xmp"] = body.decode("utf-8", "replace")
        elif cid == b"VP8X" and len(body) >= 10:
            f = body[0]
            out["metadata"]["webp_flags"] = {
                "has_icc": bool(f & 0x20), "has_alpha": bool(f & 0x10),
                "has_exif": bool(f & 0x08), "has_xmp": bool(f & 0x04),
                "is_animated": bool(f & 0x02)}
            wv = int.from_bytes(body[4:7], "little") + 1
            hv = int.from_bytes(body[7:10], "little") + 1
            out["metadata"]["dimensions"] = f"{wv}x{hv}"
        elif cid == b"VP8 " and len(body) >= 10:
            out["metadata"]["codec"] = "VP8 (ضياعي)"
        elif cid == b"VP8L":
            out["metadata"]["codec"] = "VP8L (بدون فقد)"
        elif cid == b"LIST":
            sub = body[:4]
            if sub in (b"INFO", b"Info"):
                j = 4
                while j + 8 <= len(body):
                    k = body[j:j + 4].decode("latin-1", "replace")
                    kl = struct.unpack_from("<I", body, j + 4)[0]
                    out["metadata"][k] = body[j + 8:j + 8 + kl].split(b"\x00")[0].decode("utf-8", "replace")
                    j += 8 + kl + (kl % 2)
        elif cid == b"fmt " and len(body) >= 16:
            af, ch, sr, br, ba, bps = struct.unpack_from("<HHIIHH", body, 0)
            out["metadata"]["audio"] = {"format": af, "channels": ch, "sample_rate": sr,
                                        "bitrate_bps": br * 8, "bits_per_sample": bps}
        i += 8 + clen + (clen % 2)
    return out


# ------------------------------------------------------------------ ISO-BMFF

BMFF_DESC = {
    "ftyp": "نوع الملف والعلامات المتوافقة", "moov": "حاوية بيانات الفيلم",
    "mvhd": "ترويسة الفيلم (أوقات الإنشاء/التعديل)", "trak": "مسار",
    "tkhd": "ترويسة المسار", "mdia": "وسائط المسار", "mdhd": "ترويسة الوسائط",
    "hdlr": "نوع المعالج", "minf": "معلومات الوسائط", "stbl": "جدول العيّنات",
    "stsd": "وصف العيّنة (الكوديك)", "udta": "بيانات المستخدم (GPS/أسماء)",
    "meta": "بيانات وصفية", "ilst": "قائمة وسوم iTunes/Apple", "mdat": "بيانات الوسائط الفعلية",
    "free": "مساحة حرة (قد تحوي بقايا)", "skip": "مساحة متخطّاة", "uuid": "صندوق ممتد (XMP غالبًا)",
    "iinf": "معلومات العناصر (HEIF)", "iloc": "مواقع العناصر", "infe": "إدخال عنصر",
    "pitm": "العنصر الأساسي", "iprp": "خصائص العناصر", "Exif": "بيانات EXIF",
}
_BMFF_EPOCH = datetime(1904, 1, 1, tzinfo=timezone.utc)


def _bmff_time(v: int) -> str | None:
    if not v:
        return None
    try:
        return (_BMFF_EPOCH + timedelta(seconds=v)).isoformat()
    except Exception:
        return None


def parse_bmff(data: bytes, max_boxes: int = 4000) -> dict:
    out: dict = {"is_bmff": False, "boxes": [], "metadata": {}, "warnings": []}
    if len(data) < 12 or data[4:8] not in (b"ftyp", b"moov", b"mdat", b"free", b"skip", b"styp"):
        return out
    out["is_bmff"] = True
    boxes: list[dict] = []

    def walk(off: int, end: int, depth: int, path: str) -> None:
        i = off
        while i + 8 <= end and len(boxes) < max_boxes:
            size = struct.unpack_from(">I", data, i)[0]
            btype = data[i + 4:i + 8]
            hdr = 8
            if size == 1:
                if i + 16 > end:
                    break
                size = struct.unpack_from(">Q", data, i + 8)[0]
                hdr = 16
            elif size == 0:
                size = end - i
            if size < hdr or i + size > end:
                out["warnings"].append(f"صندوق غير صالح/مبتور عند {i} (النوع {btype.decode('latin-1','replace')})")
                break
            name = btype.decode("latin-1", "replace")
            boxes.append({"type": name, "offset": i, "size": size, "depth": depth,
                          "path": f"{path}/{name}", "desc": BMFF_DESC.get(name, "")})
            body = data[i + hdr:i + size]
            _bmff_leaf(out, name, body, i)
            if name in ("moov", "trak", "mdia", "minf", "stbl", "udta", "edts", "moof", "traf",
                        "mvex", "iprp", "ipco", "dinf"):
                walk(i + hdr, i + size, depth + 1, f"{path}/{name}")
            elif name == "meta":
                walk(i + hdr + 4, i + size, depth + 1, f"{path}/{name}")
            elif name == "ilst":
                _bmff_ilst(out, data, i + hdr, i + size)
            elif name in ("\xa9xyz", "©xyz", "loci") or name.endswith("xyz"):
                # QuickTime/3GPP: الموقع يُكتب داخل udta مباشرة لا داخل ilst
                _bmff_location(out, name, data[i + hdr:i + size])
            i += size

    walk(0, len(data), 0, "")
    out["boxes"] = boxes
    if any(b["type"] == "mdat" for b in boxes):
        last = max(b["offset"] + b["size"] for b in boxes)
        if last < len(data):
            out["trailing_data"] = {"offset": last, "size": len(data) - last,
                                    "note": "⚠️ بيانات بعد آخر صندوق."}
    return out


def _bmff_leaf(out: dict, name: str, body: bytes, off: int) -> None:
    md = out["metadata"]
    try:
        if name == "ftyp":
            md["major_brand"] = body[:4].decode("latin-1", "replace")
            md["minor_version"] = struct.unpack_from(">I", body, 4)[0]
            md["compatible_brands"] = [body[i:i + 4].decode("latin-1", "replace")
                                       for i in range(8, min(len(body), 64), 4)]
        elif name == "mvhd":
            ver = body[0]
            if ver == 1:
                c, m, ts, dur = struct.unpack_from(">QQIQ", body, 4)
            else:
                c, m, ts, dur = struct.unpack_from(">IIII", body, 4)
            md["movie"] = {"created_utc": _bmff_time(c), "modified_utc": _bmff_time(m),
                           "timescale": ts,
                           "duration_sec": round(dur / ts, 3) if ts else None}
        elif name == "tkhd":
            ver = body[0]
            if ver == 1:
                c, m, tid = struct.unpack_from(">QQI", body, 4)
                w, h = struct.unpack_from(">II", body, len(body) - 8)
            else:
                c, m, tid = struct.unpack_from(">III", body, 4)
                w, h = struct.unpack_from(">II", body, len(body) - 8)
            matrix = struct.unpack_from(">9i", body, len(body) - 44)
            rot = _matrix_rotation(matrix)
            md.setdefault("tracks", []).append(
                {"track_id": tid, "created_utc": _bmff_time(c), "modified_utc": _bmff_time(m),
                 "width": w >> 16, "height": h >> 16, "rotation_deg": rot})
        elif name == "hdlr" and len(body) > 12:
            md.setdefault("handlers", []).append(body[8:12].decode("latin-1", "replace"))
        elif name == "stsd" and len(body) >= 16:
            md.setdefault("codecs", []).append(body[12:16].decode("latin-1", "replace"))
        elif name == "uuid":
            if b"<x:xmpmeta" in body:
                out["xmp"] = body[body.find(b"<x:xmpmeta"):].decode("utf-8", "replace")
            else:
                md.setdefault("uuid_boxes", []).append(body[:16].hex())
        elif name == "Exif" or (name == "meta" and body[:6] == b"Exif\x00\x00"):
            idx = body.find(b"Exif\x00\x00")
            if idx >= 0:
                out["exif"] = exif_mod.parse_tiff(body[idx + 6:], 0)
        elif name in ("free", "skip") and len(body) > 64:
            printable = sum(1 for b in body[:512] if 32 <= b < 127)
            if printable > 256:
                md.setdefault("suspicious_free_space", []).append(
                    {"offset": off, "size": len(body),
                     "preview": body[:200].decode("latin-1", "replace"),
                     "note": "مساحة «حرة» تحتوي نصًا مقروءًا — بقايا بيانات أو إخفاء."})
    except Exception:
        pass


def _matrix_rotation(m) -> int:
    a, b = m[0] / 65536.0, m[1] / 65536.0
    if abs(a - 1) < 0.01 and abs(b) < 0.01:
        return 0
    if abs(b - 1) < 0.01:
        return 90
    if abs(a + 1) < 0.01:
        return 180
    if abs(b + 1) < 0.01:
        return 270
    return 0


_ILST_NAMES = {
    "©nam": "العنوان", "©ART": "الفنان", "©alb": "الألبوم", "©day": "التاريخ",
    "©cmt": "تعليق", "©too": "برنامج الترميز (Encoder)", "©gen": "النوع",
    "©xyz": "إحداثيات GPS", "©mak": "صانع الجهاز", "©mod": "طراز الجهاز",
    "©swr": "إصدار البرنامج", "desc": "الوصف", "auth": "المؤلف", "covr": "صورة الغلاف",
}


def _bmff_location(out: dict, name: str, body: bytes) -> None:
    """
    صندوق الموقع في QuickTime (©xyz) و3GPP (loci).

    ©xyz: طول (2 بايت) + رمز لغة (2 بايت) + نص ISO 6709.
    loci: إصدار/أعلام (4) + لغة (2) + اسم المكان بـUTF-8 منتهٍ بصفر + خط الطول
          وخط العرض والارتفاع كأعداد ثابتة الفاصلة 16.16 موقَّعة.
    """
    loc = out["metadata"].setdefault("location_boxes", {})
    try:
        if name.endswith("xyz") and len(body) >= 4:
            ln = struct.unpack_from(">H", body, 0)[0]
            txt = body[4:4 + ln].decode("utf-8", "replace").strip()
            if txt:
                loc[name] = txt
        elif name == "loci" and len(body) >= 6:
            rest = body[6:]
            z = rest.find(b"\x00")
            place = rest[:z].decode("utf-8", "replace") if z >= 0 else ""
            nums = rest[z + 1:] if z >= 0 else rest
            if len(nums) >= 9:
                role = nums[0]
                lon_f, lat_f = struct.unpack_from(">ii", nums, 1)
                lon = lon_f / 65536.0
                lat = lat_f / 65536.0
                loc["loci"] = f"{lat:+010.5f}{lon:+011.5f}/"
                if place:
                    loc["loci_place_name"] = place
                loc["loci_role"] = role
    except Exception:
        pass


def _bmff_ilst(out: dict, data: bytes, start: int, end: int) -> None:
    i = start
    tags = out["metadata"].setdefault("tags", {})
    while i + 8 <= end:
        size = struct.unpack_from(">I", data, i)[0]
        if size < 8 or i + size > end:
            break
        key = data[i + 4:i + 8].decode("latin-1", "replace")
        body = data[i + 8:i + size]
        if body[4:8] == b"data" and len(body) > 16:
            val = body[16:]
            try:
                txt = val.decode("utf-8")
            except UnicodeDecodeError:
                txt = f"<{len(val)} بايت ثنائي>"
            tags[_ILST_NAMES.get(key, key)] = txt[:1000]
        i += size


def parse_matroska(data: bytes) -> dict:
    """قراءة مبسطة لعناصر EBML الأعلى مستوى (Matroska/WebM) لاستخراج المُنتِج والتاريخ."""
    out: dict = {"is_matroska": False, "info": {}}
    if data[:4] != b"\x1aE\xdf\xa3":
        return out
    out["is_matroska"] = True
    for marker, label in ((b"\x4d\x80", "MuxingApp"), (b"\x57\x41", "WritingApp"),
                          (b"\x7b\xa9", "Title")):
        idx = data.find(marker, 0, 1_000_000)
        if idx > 0:
            ln = data[idx + 2]
            if ln < 0x80:
                continue
            ln &= 0x7F
            out["info"][label] = data[idx + 3:idx + 3 + ln].decode("utf-8", "replace")
    idx = data.find(b"\x44\x89", 0, 1_000_000)
    return out
