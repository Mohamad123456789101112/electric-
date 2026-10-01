"""
محلّل TIFF/EXIF مكتوب من الصفر (بدون مكتبات خارجية) — يقرأ كل الـ IFDs:
IFD0, Exif IFD, GPS IFD, Interoperability IFD, IFD1 (المصغّرة), وMakerNote.
يُستخدم على الملفات السليمة وعلى الشظايا المستخرجة من ملفات «ممسوحة الميتاداتا».
المرجع: Exif 2.32 / TIFF 6.0 specification.
"""
from __future__ import annotations

import struct
from datetime import datetime, timedelta, timezone

TIFF_TAGS = {
    0x00FE: "NewSubfileType", 0x0100: "ImageWidth", 0x0101: "ImageLength",
    0x0102: "BitsPerSample", 0x0103: "Compression", 0x0106: "PhotometricInterpretation",
    0x010D: "DocumentName", 0x010E: "ImageDescription", 0x010F: "Make", 0x0110: "Model",
    0x0111: "StripOffsets", 0x0112: "Orientation", 0x0115: "SamplesPerPixel",
    0x0116: "RowsPerStrip", 0x0117: "StripByteCounts", 0x011A: "XResolution",
    0x011B: "YResolution", 0x011C: "PlanarConfiguration", 0x0128: "ResolutionUnit",
    0x0131: "Software", 0x0132: "DateTime", 0x013B: "Artist", 0x013E: "WhitePoint",
    0x013F: "PrimaryChromaticities", 0x0142: "TileWidth", 0x0143: "TileLength",
    0x014A: "SubIFDs", 0x0153: "SampleFormat",
    0x0201: "JPEGInterchangeFormat", 0x0202: "JPEGInterchangeFormatLength",
    0x0211: "YCbCrCoefficients", 0x0212: "YCbCrSubSampling", 0x0213: "YCbCrPositioning",
    0x0214: "ReferenceBlackWhite", 0x02BC: "XMLPacket(XMP)",
    0x4746: "Rating", 0x4749: "RatingPercent",
    0x8298: "Copyright", 0x829A: "ExposureTime", 0x829D: "FNumber",
    0x83BB: "IPTC-NAA", 0x8649: "PhotoshopSettings", 0x8769: "ExifIFDPointer",
    0x8773: "ICC_Profile", 0x8822: "ExposureProgram", 0x8824: "SpectralSensitivity",
    0x8825: "GPSInfoIFDPointer", 0x8827: "ISOSpeedRatings", 0x8828: "OECF",
    0x8830: "SensitivityType", 0x8831: "StandardOutputSensitivity",
    0x8832: "RecommendedExposureIndex", 0x8833: "ISOSpeed",
    0x9000: "ExifVersion", 0x9003: "DateTimeOriginal", 0x9004: "DateTimeDigitized",
    0x9010: "OffsetTime", 0x9011: "OffsetTimeOriginal", 0x9012: "OffsetTimeDigitized",
    0x9101: "ComponentsConfiguration", 0x9102: "CompressedBitsPerPixel",
    0x9201: "ShutterSpeedValue", 0x9202: "ApertureValue", 0x9203: "BrightnessValue",
    0x9204: "ExposureBiasValue", 0x9205: "MaxApertureValue", 0x9206: "SubjectDistance",
    0x9207: "MeteringMode", 0x9208: "LightSource", 0x9209: "Flash",
    0x920A: "FocalLength", 0x9214: "SubjectArea", 0x927C: "MakerNote",
    0x9286: "UserComment", 0x9290: "SubSecTime", 0x9291: "SubSecTimeOriginal",
    0x9292: "SubSecTimeDigitized", 0x9400: "AmbientTemperature", 0x9401: "Humidity",
    0x9402: "Pressure", 0x9403: "WaterDepth", 0x9404: "Acceleration",
    0x9405: "CameraElevationAngle",
    0xA000: "FlashpixVersion", 0xA001: "ColorSpace", 0xA002: "PixelXDimension",
    0xA003: "PixelYDimension", 0xA004: "RelatedSoundFile", 0xA005: "InteropIFDPointer",
    0xA20B: "FlashEnergy", 0xA20E: "FocalPlaneXResolution", 0xA20F: "FocalPlaneYResolution",
    0xA210: "FocalPlaneResolutionUnit", 0xA214: "SubjectLocation",
    0xA215: "ExposureIndex", 0xA217: "SensingMethod", 0xA300: "FileSource",
    0xA301: "SceneType", 0xA302: "CFAPattern", 0xA401: "CustomRendered",
    0xA402: "ExposureMode", 0xA403: "WhiteBalance", 0xA404: "DigitalZoomRatio",
    0xA405: "FocalLengthIn35mmFilm", 0xA406: "SceneCaptureType", 0xA407: "GainControl",
    0xA408: "Contrast", 0xA409: "Saturation", 0xA40A: "Sharpness",
    0xA40B: "DeviceSettingDescription", 0xA40C: "SubjectDistanceRange",
    0xA420: "ImageUniqueID", 0xA430: "CameraOwnerName", 0xA431: "BodySerialNumber",
    0xA432: "LensSpecification", 0xA433: "LensMake", 0xA434: "LensModel",
    0xA435: "LensSerialNumber", 0xA460: "CompositeImage",
    0xC4A5: "PrintIM", 0xC612: "DNGVersion", 0xC614: "UniqueCameraModel",
    0xC62F: "CameraSerialNumber", 0xEA1C: "Padding",
}

GPS_TAGS = {
    0x0000: "GPSVersionID", 0x0001: "GPSLatitudeRef", 0x0002: "GPSLatitude",
    0x0003: "GPSLongitudeRef", 0x0004: "GPSLongitude", 0x0005: "GPSAltitudeRef",
    0x0006: "GPSAltitude", 0x0007: "GPSTimeStamp", 0x0008: "GPSSatellites",
    0x0009: "GPSStatus", 0x000A: "GPSMeasureMode", 0x000B: "GPSDOP",
    0x000C: "GPSSpeedRef", 0x000D: "GPSSpeed", 0x000E: "GPSTrackRef",
    0x000F: "GPSTrack", 0x0010: "GPSImgDirectionRef", 0x0011: "GPSImgDirection",
    0x0012: "GPSMapDatum", 0x0013: "GPSDestLatitudeRef", 0x0014: "GPSDestLatitude",
    0x0015: "GPSDestLongitudeRef", 0x0016: "GPSDestLongitude", 0x0017: "GPSDestBearingRef",
    0x0018: "GPSDestBearing", 0x0019: "GPSDestDistanceRef", 0x001A: "GPSDestDistance",
    0x001B: "GPSProcessingMethod", 0x001C: "GPSAreaInformation", 0x001D: "GPSDateStamp",
    0x001E: "GPSDifferential", 0x001F: "GPSHPositioningError",
}

INTEROP_TAGS = {0x0001: "InteroperabilityIndex", 0x0002: "InteroperabilityVersion"}

TYPE_SIZES = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8, 13: 4, 16: 8, 17: 8, 18: 8}
TYPE_NAMES = {1: "BYTE", 2: "ASCII", 3: "SHORT", 4: "LONG", 5: "RATIONAL", 6: "SBYTE",
              7: "UNDEFINED", 8: "SSHORT", 9: "SLONG", 10: "SRATIONAL", 11: "FLOAT",
              12: "DOUBLE", 13: "IFD", 16: "LONG8", 17: "SLONG8", 18: "IFD8"}

ENUMS = {
    "Orientation": {1: "عادي (0°)", 2: "معكوس أفقيًا", 3: "مقلوب 180°", 4: "معكوس رأسيًا",
                    5: "معكوس + 90° يسار", 6: "مُدار 90° يمين", 7: "معكوس + 90° يمين", 8: "مُدار 90° يسار"},
    "Flash": {0: "لم ينطلق الفلاش", 1: "انطلق الفلاش", 5: "انطلق، لم يُرصد ارتداد",
              7: "انطلق، رُصد ارتداد", 9: "انطلق (إجباري)", 16: "لم ينطلق (وضع إجباري)",
              24: "لم ينطلق (تلقائي)", 25: "انطلق (تلقائي)", 32: "لا يوجد فلاش في الجهاز"},
    "ExposureProgram": {0: "غير محدد", 1: "يدوي", 2: "برنامج عادي", 3: "أولوية الفتحة",
                        4: "أولوية الغالق", 5: "إبداعي", 6: "حركة", 7: "بورتريه", 8: "منظر"},
    "MeteringMode": {0: "غير معروف", 1: "متوسط", 2: "متوسط مرجّح للمركز", 3: "نقطي",
                     4: "متعدد النقاط", 5: "نمطي", 6: "جزئي", 255: "آخر"},
    "WhiteBalance": {0: "تلقائي", 1: "يدوي"},
    "ColorSpace": {1: "sRGB", 2: "Adobe RGB", 0xFFFF: "غير معاير"},
    "SceneCaptureType": {0: "قياسي", 1: "منظر", 2: "بورتريه", 3: "مشهد ليلي"},
    "SensingMethod": {1: "غير معرّف", 2: "مستشعر مساحي أحادي الرقاقة", 3: "مستشعر ثنائي الرقاقة",
                      4: "مستشعر ثلاثي الرقاقة", 5: "مستشعر ألوان متسلسل", 7: "مستشعر ثلاثي الخط", 8: "خطي"},
    "FileSource": {1: "ماسح أفلام", 2: "ماسح انعكاسي", 3: "كاميرا رقمية ساكنة"},
    "CustomRendered": {0: "معالجة عادية", 1: "معالجة مخصصة"},
    "ExposureMode": {0: "تلقائي", 1: "يدوي", 2: "تقويس تلقائي"},
    "ResolutionUnit": {1: "بدون", 2: "بوصة", 3: "سنتيمتر"},
    "Compression": {1: "غير مضغوط", 6: "JPEG (قديم)", 7: "JPEG", 8: "Deflate", 32773: "PackBits"},
}


def _read_value(data: bytes, off: int, endian: str, typ: int, count: int, tiff_base: int):
    size = TYPE_SIZES.get(typ, 1) * count
    if size <= 4:
        raw = data[off + 8:off + 8 + size]
    else:
        ptr = struct.unpack_from(endian + "I", data, off + 8)[0] + tiff_base
        if ptr < 0 or ptr + size > len(data) or size > 50_000_000:
            return None, (ptr, size)
        raw = data[ptr:ptr + size]
    if typ == 2:
        try:
            return raw.split(b"\x00")[0].decode("utf-8", "replace"), None
        except Exception:
            return raw.decode("latin-1", "replace"), None
    if typ in (1, 6, 7):
        if typ == 7 and len(raw) > 512:
            return {"_undefined_bytes": len(raw), "_preview_hex": raw[:64].hex(" ")}, None
        # وسوم GPS ذات ترويسة مجموعة محارف من 8 بايت (ProcessingMethod/AreaInformation
        # وكذلك UserComment) تحمل النص **بعد** الترويسة؛ القصّ عند أول صفر يضيّعه.
        if len(raw) > 8 and raw[:8] in (b"ASCII\x00\x00\x00", b"UNICODE\x00",
                                        b"JIS\x00\x00\x00\x00\x00", b"\x00" * 8):
            charset = raw[:8].rstrip(b"\x00").decode("latin-1") or "UNDEFINED"
            body = raw[8:]
            if charset == "UNICODE":
                txt = body.decode("utf-16-be" if endian == ">" else "utf-16-le",
                                  "replace").strip("\x00 ")
            else:
                txt = body.decode("utf-8", "replace").strip("\x00 ")
            if txt:
                return f"{charset}:{txt}" if charset != "ASCII" else txt, None
        if all(32 <= b < 127 or b in (0, 9, 10, 13) for b in raw[:64]) and len(raw) > 3:
            txt = raw.split(b"\x00")[0].decode("latin-1", "replace")
            if txt.strip():
                return txt, None
        return list(raw[:256]), None
    fmt = {3: "H", 4: "I", 8: "h", 9: "i", 11: "f", 12: "d"}.get(typ)
    if fmt:
        n = min(count, 4096)
        try:
            vals = list(struct.unpack_from(endian + fmt * n, raw, 0))
        except struct.error:
            return None, None
        return vals[0] if len(vals) == 1 else vals, None
    if typ in (5, 10):
        f = "II" if typ == 5 else "ii"
        vals = []
        for i in range(min(count, 2048)):
            try:
                num, den = struct.unpack_from(endian + f, raw, i * 8)
            except struct.error:
                break
            vals.append([num, den])
        return vals[0] if len(vals) == 1 else vals, None
    return raw[:256].hex(" "), None


def _rational_to_float(v):
    if isinstance(v, list) and len(v) == 2 and all(isinstance(x, int) for x in v):
        return v[0] / v[1] if v[1] else 0.0
    return None


def _humanize(tag: str, value):
    f = _rational_to_float(value)
    if tag in ENUMS and isinstance(value, int):
        return ENUMS[tag].get(value, value)
    if tag == "ExposureTime" and f:
        return f"{f:.6g} ثانية" + (f" (1/{round(1/f)})" if f and f < 1 else "")
    if tag == "FNumber" and f:
        return f"f/{f:.3g}"
    if tag == "FocalLength" and f:
        return f"{f:.4g} مم"
    if tag in ("XResolution", "YResolution") and f:
        return f"{f:.6g}"
    if tag == "ApertureValue" and f:
        return f"f/{round(2 ** (f / 2), 2)}"
    if tag == "ShutterSpeedValue" and f is not None:
        try:
            return f"1/{round(2 ** f)} ثانية"
        except OverflowError:
            return value
    if tag == "ExposureBiasValue" and f is not None:
        return f"{f:+.3g} EV"
    if tag == "GPSAltitude" and f is not None:
        return f"{f:.4g} متر"
    return value


def parse_ifd(data: bytes, ifd_off: int, endian: str, tiff_base: int, tagmap: dict,
              depth: int = 0, seen: set | None = None) -> tuple[dict, dict]:
    """يرجع (الحقول, المؤشرات لباقي الـ IFDs)."""
    seen = seen if seen is not None else set()
    fields: dict = {}
    pointers: dict = {}
    if ifd_off in seen or depth > 6 or ifd_off + 2 > len(data) or ifd_off < 0:
        return fields, pointers
    seen.add(ifd_off)
    try:
        count = struct.unpack_from(endian + "H", data, ifd_off)[0]
    except struct.error:
        return fields, pointers
    if count > 2048:
        return fields, pointers
    for i in range(count):
        e = ifd_off + 2 + i * 12
        if e + 12 > len(data):
            break
        tag, typ, cnt = struct.unpack_from(endian + "HHI", data, e)
        name = tagmap.get(tag, TIFF_TAGS.get(tag, f"Unknown_0x{tag:04X}"))
        if cnt > 10_000_000:
            continue
        if name in ("ExifIFDPointer", "GPSInfoIFDPointer", "InteropIFDPointer", "SubIFDs"):
            val, _ = _read_value(data, e, endian, typ, cnt, tiff_base)
            pointers[name] = val
            continue
        val, unres = _read_value(data, e, endian, typ, cnt, tiff_base)
        if val is None and unres:
            fields[name] = {"_unresolved_pointer": unres[0], "_size": unres[1],
                            "_note": "المؤشر يقع خارج حدود البيانات المتاحة (شظية مقطوعة)"}
            continue
        fields[name] = {
            "tag": f"0x{tag:04X}", "type": TYPE_NAMES.get(typ, str(typ)), "count": cnt,
            "raw": val, "value": _humanize(name, val),
        }
    try:
        next_off = struct.unpack_from(endian + "I", data, ifd_off + 2 + count * 12)[0]
    except struct.error:
        next_off = 0
    pointers["_next_ifd"] = next_off
    return fields, pointers


def _gps_decimal(coord, ref) -> float | None:
    try:
        if not isinstance(coord, list) or len(coord) != 3:
            return None
        d = coord[0][0] / coord[0][1] if coord[0][1] else 0
        m = coord[1][0] / coord[1][1] if coord[1][1] else 0
        s = coord[2][0] / coord[2][1] if coord[2][1] else 0
        val = d + m / 60 + s / 3600
        if isinstance(ref, str) and ref.upper().startswith(("S", "W")):
            val = -val
        return round(val, 8)
    except Exception:
        return None


def parse_tiff(data: bytes, base: int = 0) -> dict:
    """data: البيانات التي تبدأ عند base بترويسة TIFF (II*\\0 أو MM\\0*)."""
    out: dict = {"ok": False}
    if base + 8 > len(data):
        return out
    bo = data[base:base + 2]
    if bo == b"II":
        endian = "<"
    elif bo == b"MM":
        endian = ">"
    else:
        return out
    magic = struct.unpack_from(endian + "H", data, base + 2)[0]
    if magic not in (42, 43):
        return out
    first = struct.unpack_from(endian + "I", data, base + 4)[0]
    out["ok"] = True
    out["byte_order"] = "Little Endian (Intel)" if endian == "<" else "Big Endian (Motorola)"
    out["tiff_base_offset"] = base

    seen: set = set()
    ifd0, ptr0 = parse_ifd(data, base + first, endian, base, TIFF_TAGS, 0, seen)
    out["IFD0"] = ifd0

    if "ExifIFDPointer" in ptr0 and isinstance(ptr0["ExifIFDPointer"], int):
        ex, pex = parse_ifd(data, base + ptr0["ExifIFDPointer"], endian, base, TIFF_TAGS, 1, seen)
        out["ExifIFD"] = ex
        if "InteropIFDPointer" in pex and isinstance(pex["InteropIFDPointer"], int):
            io, _ = parse_ifd(data, base + pex["InteropIFDPointer"], endian, base, INTEROP_TAGS, 2, seen)
            out["InteropIFD"] = io
    if "GPSInfoIFDPointer" in ptr0 and isinstance(ptr0["GPSInfoIFDPointer"], int):
        gp, _ = parse_ifd(data, base + ptr0["GPSInfoIFDPointer"], endian, base, GPS_TAGS, 1, seen)
        out["GPSIFD"] = gp
        lat = _gps_decimal(gp.get("GPSLatitude", {}).get("raw"), gp.get("GPSLatitudeRef", {}).get("raw"))
        lon = _gps_decimal(gp.get("GPSLongitude", {}).get("raw"), gp.get("GPSLongitudeRef", {}).get("raw"))
        if lat is not None and lon is not None:
            alt = _rational_to_float(gp.get("GPSAltitude", {}).get("raw"))
            ts = gp.get("GPSTimeStamp", {}).get("raw")
            gtime = None
            if isinstance(ts, list) and len(ts) == 3:
                try:
                    gtime = "%02d:%02d:%06.3f UTC" % (ts[0][0] / ts[0][1], ts[1][0] / ts[1][1],
                                                      ts[2][0] / ts[2][1])
                except Exception:
                    gtime = None
            out["GPS_decoded"] = {
                "latitude": lat, "longitude": lon,
                "altitude_m": round(alt, 2) if alt is not None else None,
                "date": gp.get("GPSDateStamp", {}).get("raw"),
                "time_utc": gtime,
                "google_maps": f"https://www.google.com/maps?q={lat},{lon}",
                "osm": f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=17/{lat}/{lon}",
                "horizontal_error_m": _rational_to_float(gp.get("GPSHPositioningError", {}).get("raw")),
            }

    # IFD1 = الصورة المصغّرة المدمجة
    nxt = ptr0.get("_next_ifd", 0)
    if isinstance(nxt, int) and nxt > 0 and base + nxt < len(data):
        ifd1, _ = parse_ifd(data, base + nxt, endian, base, TIFF_TAGS, 1, seen)
        out["IFD1_thumbnail"] = ifd1
        try:
            toff = ifd1["JPEGInterchangeFormat"]["raw"] + base
            tlen = ifd1["JPEGInterchangeFormatLength"]["raw"]
            if 0 < tlen < 20_000_000 and toff + tlen <= len(data):
                out["_thumbnail_bytes"] = data[toff:toff + tlen]
        except Exception:
            pass

    mn = out.get("ExifIFD", {}).get("MakerNote")
    if mn:
        out["MakerNote_present"] = True
    return out


def flatten(tiff: dict) -> dict:
    """تسطيح القيم المهمة في قاموس بسيط اسم → قيمة."""
    flat = {}
    for sect in ("IFD0", "ExifIFD", "GPSIFD", "InteropIFD", "IFD1_thumbnail"):
        for k, v in (tiff.get(sect) or {}).items():
            if isinstance(v, dict) and "value" in v:
                flat[f"{sect}:{k}"] = v["value"]
    return flat


def exif_datetimes(tiff: dict) -> list[dict]:
    res = []
    mapping = [("IFD0", "DateTime", "تاريخ آخر تعديل (ملف)"),
               ("ExifIFD", "DateTimeOriginal", "تاريخ الالتقاط الأصلي"),
               ("ExifIFD", "DateTimeDigitized", "تاريخ الرقمنة")]
    for sect, tag, label in mapping:
        v = (tiff.get(sect) or {}).get(tag, {})
        raw = v.get("raw") if isinstance(v, dict) else None
        if isinstance(raw, str) and len(raw) >= 19:
            try:
                dt = datetime.strptime(raw[:19], "%Y:%m:%d %H:%M:%S")
                res.append({"label": label, "source": f"EXIF {tag}", "iso": dt.isoformat(),
                            "epoch": int(dt.replace(tzinfo=timezone.utc).timestamp())})
            except ValueError:
                res.append({"label": label, "source": f"EXIF {tag}", "iso": raw, "epoch": None,
                            "note": "صيغة تاريخ غير قياسية — مؤشر محتمل على تعديل يدوي"})
    g = tiff.get("GPS_decoded") or {}
    if g.get("date"):
        res.append({"label": "تاريخ GPS (مرجع زمني ذري)", "source": "GPSDateStamp",
                    "iso": f"{g['date']} {g.get('time_utc') or ''}".strip(), "epoch": None})
    return res
