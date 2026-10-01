"""
فكّ تشفير بنية MakerNote الخاصة بالمصنّعين (Canon · Nikon · Sony · Apple · وغيرهم).

لماذا هذه الوحدة هي الأهم في ربط صورة بجهاز بعينه؟
لأن MakerNote يحمل ما لا يحمله EXIF القياسي: **الرقم التسلسلي لجسم الكاميرا**،
**عدّاد الغالق** (كم صورة التقطها هذا الجسم طوال عمره)، الرقم التسلسلي الداخلي،
طراز العدسة ورقمها، ومعرّفات الجلسة في أجهزة آبل.

التحدي التقني الحقيقي هنا ليس أسماء الوسوم، بل **قاعدة الإزاحات (offset base)**:
كل مصنّع يكتب مؤشرات داخل MakerNote منسوبة إلى مرجع مختلف — بعضها إلى بداية
TIFF الرئيسي، وبعضها إلى بداية كتلة MakerNote نفسها، وبعضها يبدأ بترويسة TIFF
مستقلة. الخطأ في المرجع يُنتج قيمًا عشوائية تبدو «صحيحة» وهي كاذبة — ولهذا
نحدد المرجع لكل مصنّع صراحةً، ونرفض أي قيمة لا تقع داخل حدود البيانات.

كل قيمة تُقرأ من بايتاتها فعليًا؛ وأي وسم غير موثّق يُعرض كما هو (خام) ويُوسم
بأنه «غير معروف» — لا تخمين ولا اختلاق.
"""
from __future__ import annotations

import struct
from datetime import datetime, timedelta, timezone

from .exif import TYPE_NAMES, TYPE_SIZES, _read_value

# ---------------------------------------------------------------- قواميس الوسوم

CANON_TAGS = {
    0x0001: "CanonCameraSettings", 0x0002: "CanonFocalLength", 0x0003: "CanonFlashInfo",
    0x0004: "CanonShotInfo", 0x0005: "CanonPanorama", 0x0006: "CanonImageType",
    0x0007: "CanonFirmwareVersion", 0x0008: "FileNumber", 0x0009: "OwnerName",
    0x000C: "SerialNumber", 0x000D: "CanonCameraInfo", 0x000F: "CanonCustomFunctions",
    0x0010: "CanonModelID", 0x0012: "CanonAFInfo", 0x0013: "ThumbnailImageValidArea",
    0x0015: "SerialNumberFormat", 0x001C: "DateStampMode", 0x001D: "MyColors",
    0x001E: "FirmwareRevision", 0x0024: "FaceDetect1", 0x0026: "CanonAFInfo2",
    0x0028: "ContrastInfo", 0x0035: "TimeInfo", 0x0038: "BatteryType",
    0x0093: "CanonFileInfo", 0x0095: "LensModel", 0x0096: "InternalSerialNumber",
    0x0097: "DustRemovalData", 0x0099: "CustomFunctions2", 0x009A: "AspectInfo",
    0x00A0: "ProcessingInfo", 0x00AA: "MeasuredColor", 0x00B4: "ColorSpace",
    0x00D0: "VRDOffset", 0x00E0: "SensorInfo", 0x4001: "ColorData",
    0x4008: "BlackLevel", 0x4010: "CustomPictureStyleFileName", 0x4013: "AFMicroAdj",
    0x4019: "LensInfo", 0x4024: "FilterInfo", 0x4025: "HDRInfo",
}

# فهارس مصفوفة CanonCameraSettings (0x0001) — قيم int16 مفهرسة من 1
CANON_CAMERA_SETTINGS = {
    1: "MacroMode", 2: "SelfTimer", 3: "Quality", 4: "CanonFlashMode",
    5: "ContinuousDrive", 7: "FocusMode", 9: "RecordMode", 10: "CanonImageSize",
    11: "EasyMode", 12: "DigitalZoom", 13: "Contrast", 14: "Saturation",
    15: "Sharpness", 16: "CameraISO", 17: "MeteringMode", 18: "FocusRange",
    19: "AFPoint", 20: "CanonExposureMode", 22: "LensType", 23: "MaxFocalLength",
    24: "MinFocalLength", 25: "FocalUnits", 26: "MaxAperture", 27: "MinAperture",
    28: "FlashActivity", 29: "FlashBits", 32: "FocusContinuous", 33: "AESetting",
    34: "ImageStabilization", 35: "DisplayAperture", 39: "SpotMeteringMode",
    40: "PhotoEffect", 41: "ManualFlashOutput", 42: "ColorTone", 46: "SRAWQuality",
}

NIKON_TAGS = {
    0x0001: "MakerNoteVersion", 0x0002: "ISO", 0x0003: "ColorMode", 0x0004: "Quality",
    0x0005: "WhiteBalance", 0x0006: "Sharpness", 0x0007: "FocusMode",
    0x0008: "FlashSetting", 0x0009: "FlashType", 0x000B: "WhiteBalanceFineTune",
    0x000D: "ProgramShift", 0x000E: "ExposureDifference", 0x0011: "PreviewIFD",
    0x0012: "FlashExposureComp", 0x0013: "ISOSetting", 0x0016: "ImageBoundary",
    0x0017: "ExternalFlashExposureComp", 0x0018: "FlashExposureBracketValue",
    0x0019: "ExposureBracketValue", 0x001A: "ImageProcessing", 0x001B: "CropHiSpeed",
    0x001C: "ExposureTuning", 0x001D: "SerialNumber", 0x001E: "ColorSpace",
    0x001F: "VRInfo", 0x0020: "ImageAuthentication", 0x0022: "ActiveD-Lighting",
    0x0023: "PictureControlData", 0x0024: "WorldTime", 0x0025: "ISOInfo",
    0x002A: "VignetteControl", 0x002B: "DistortInfo", 0x0032: "UnknownInfo",
    0x0035: "HDRInfo", 0x003B: "WB_RBLevels", 0x0080: "ImageAdjustment",
    0x0081: "ToneComp", 0x0082: "AuxiliaryLens", 0x0083: "LensType", 0x0084: "Lens",
    0x0085: "ManualFocusDistance", 0x0086: "DigitalZoom", 0x0087: "FlashMode",
    0x0088: "AFInfo", 0x0089: "ShootingMode", 0x008B: "LensFStops",
    0x008C: "ContrastCurve", 0x0091: "ShotInfo", 0x0092: "HueAdjustment",
    0x0093: "NEFCompression", 0x0095: "NoiseReduction", 0x0097: "ColorBalance",
    0x0098: "LensData", 0x0099: "RawImageCenter", 0x009A: "SensorPixelSize",
    0x00A0: "SerialNumber2", 0x00A2: "ImageDataSize", 0x00A5: "ImageCount",
    0x00A6: "DeletedImageCount", 0x00A7: "ShutterCount", 0x00A8: "FlashInfo",
    0x00A9: "ImageOptimization", 0x00AB: "VariProgram", 0x00B0: "MultiExposure",
    0x00B1: "HighISONoiseReduction", 0x00B6: "PowerUpTime", 0x00B7: "AFInfo2",
    0x00B8: "FileInfo", 0x00BB: "RetouchInfo", 0x00BF: "SceneAssist",
    0x00C3: "BarometerInfo", 0x0E01: "NikonCaptureData", 0x0E09: "NikonCaptureVersion",
    0x0E13: "NikonCaptureEditVersions",
}

SONY_TAGS = {
    0x0102: "Quality", 0x0104: "FlashExposureComp", 0x0105: "Teleconverter",
    0x0112: "WhiteBalanceFineTune", 0x0114: "CameraSettings", 0x0115: "WhiteBalance",
    0x0E00: "PrintIM", 0x1000: "MultiBurstMode", 0x2001: "PreviewImage",
    0x2002: "Rating", 0x2004: "Contrast", 0x2005: "Saturation", 0x2006: "Sharpness",
    0x2007: "Brightness", 0x2008: "LongExposureNoiseReduction",
    0x2009: "HighISONoiseReduction", 0x200A: "AutoHDR", 0x201B: "FileFormat",
    0x3000: "ShotInfo", 0x9050: "EncryptedTag_9050", 0xB000: "FileFormat",
    0xB001: "SonyModelID", 0xB020: "ColorReproduction", 0xB021: "ColorTemperature",
    0xB023: "SceneMode", 0xB024: "ZoneMatching", 0xB025: "DynamicRangeOptimizer",
    0xB026: "ImageStabilization", 0xB027: "LensType", 0xB029: "ColorMode",
    0xB02B: "FullImageSize", 0xB02C: "PreviewImageSize", 0xB040: "Macro",
    0xB041: "ExposureMode", 0xB042: "FocusMode", 0xB043: "AFAreaMode",
    0xB044: "AFIlluminator", 0xB047: "JPEGQuality", 0xB048: "FlashLevel",
    0xB049: "ReleaseMode", 0xB04A: "SequenceNumber", 0xB04B: "AntiBlur",
    0xB04E: "LongExposureNoiseReduction2", 0xB04F: "DynamicRangeOptimizer2",
    0xB052: "IntelligentAuto", 0xB054: "WhiteBalance2",
}

APPLE_TAGS = {
    0x0001: "MakerNoteVersion", 0x0002: "AEMatrix", 0x0003: "RunTime",
    0x0004: "AEStable", 0x0005: "AETarget", 0x0006: "AEAverage", 0x0007: "AFStable",
    0x0008: "AccelerationVector", 0x000A: "HDRImageType", 0x000B: "BurstUUID",
    0x000C: "FocusDistanceRange", 0x000E: "OrientationInfo", 0x000F: "OISMode",
    0x0011: "ContentIdentifier", 0x0014: "ImageCaptureType", 0x0015: "ImageUniqueID",
    0x0017: "LivePhotoVideoIndex", 0x0019: "ImageProcessingFlags",
    0x001A: "QualityHint", 0x001F: "ColorTemperature", 0x0020: "CameraType",
    0x0021: "FocusPosition", 0x0023: "ImageCaptureRequestID",
    0x0025: "SemanticStyle", 0x002B: "PhotoIdentifier",
}

PANASONIC_TAGS = {
    0x0001: "ImageQuality", 0x0002: "FirmwareVersion", 0x0003: "WhiteBalance",
    0x0007: "FocusMode", 0x000F: "AFAreaMode", 0x001A: "ImageStabilization",
    0x001C: "MacroMode", 0x001F: "ShootingMode", 0x0020: "Audio",
    0x0021: "DataDump", 0x0023: "WhiteBalanceBias", 0x0024: "FlashBias",
    0x0025: "InternalSerialNumber", 0x0026: "PanasonicExifVersion",
    0x0028: "ColorEffect", 0x0029: "TimeSincePowerOn", 0x002A: "BurstMode",
    0x002B: "SequenceNumber", 0x002C: "ContrastMode", 0x002D: "NoiseReduction",
    0x0051: "LensType", 0x0052: "LensSerialNumber", 0x0053: "AccessoryType",
    0x008C: "ContrastMode2", 0x009D: "FNumber", 0x9201: "Exposure",
}

FUJI_TAGS = {
    0x0000: "Version", 0x0010: "InternalSerialNumber", 0x1000: "Quality",
    0x1001: "Sharpness", 0x1002: "WhiteBalance", 0x1003: "Saturation",
    0x1004: "Contrast", 0x1010: "FujiFlashMode", 0x1011: "FlashExposureComp",
    0x1020: "Macro", 0x1021: "FocusMode", 0x1030: "SlowSync", 0x1031: "PictureMode",
    0x1100: "AutoBracketing", 0x1101: "SequenceNumber", 0x1401: "FilmMode",
    0x1404: "MinFocalLength", 0x1405: "MaxFocalLength", 0x1422: "ImageCount",
    0x3803: "VideoRecordingMode",
}

OLYMPUS_TAGS = {
    0x0100: "ThumbnailImage", 0x0200: "SpecialMode", 0x0201: "Quality",
    0x0202: "Macro", 0x0203: "BWMode", 0x0204: "DigitalZoom", 0x0207: "CameraType",
    0x0208: "TextInfo", 0x0209: "CameraID", 0x020B: "EpsonImageWidth",
    0x0404: "SerialNumber", 0x0405: "Firmware", 0x1001: "ShutterSpeedValue",
    0x1002: "ISOValue", 0x1007: "CameraTemperature", 0x1020: "Unknown",
    0x1029: "ShutterCount", 0x2010: "Equipment", 0x2020: "CameraSettings",
    0x2030: "RawDevelopment", 0x2040: "ImageProcessing", 0x2050: "FocusInfo",
}

SAMSUNG_TAGS = {
    0x0001: "MakerNoteVersion", 0x0002: "DeviceType", 0x0003: "SamsungModelID",
    0x0011: "OrientationInfo", 0x0021: "PictureWizard", 0x0030: "LocalLocationName",
    0x0031: "LocationName", 0x0035: "PreviewIFD", 0x0040: "RawDataByteOrder",
    0x0043: "CameraTemperature", 0xA001: "FirmwareName", 0xA003: "LensType",
    0xA004: "LensFirmware", 0xA010: "SensorAreas", 0xA011: "ColorSpace",
    0xA012: "SmartRange", 0xA013: "ExposureBiasValue", 0xA014: "ISO",
    0xA018: "ExposureTime", 0xA019: "FNumber", 0xA01A: "FocalLengthIn35mmFormat",
    0xA020: "EncryptionKey", 0xA021: "WB_RGGBLevelsUncorrected",
    0xA028: "BlackLevel", 0xA030: "AFInfo",
}

# ------------------------------------------------- تعريف المصنّع وقاعدة الإزاحة
# (المعرّف, نمط الترويسة, إزاحة بداية الـIFD داخل الكتلة, مرجع الإزاحات, قاموس الوسوم)
# مرجع الإزاحات: "tiff" = بداية TIFF الرئيسي · "maker" = بداية كتلة MakerNote
#                 "inner" = ترويسة TIFF مستقلة داخل الكتلة


def detect_vendor(mn: bytes, make: str = "", model: str = "") -> dict | None:
    """تحديد المصنّع وبنية MakerNote من بايتات الكتلة نفسها أولًا، ثم من حقل Make."""
    m = (make or "").upper()

    if mn[:10] == b"Apple iOS\x00":
        return {"vendor": "Apple", "vendor_ar": "آبل", "ifd_offset": 14,
                "base": "maker", "endian_at": 12, "tags": APPLE_TAGS,
                "note": "ترويسة Apple iOS — الإزاحات منسوبة لبداية كتلة MakerNote."}
    if mn[:6] == b"Nikon\x00":
        if len(mn) > 10 and mn[10:12] in (b"II", b"MM"):
            return {"vendor": "Nikon", "vendor_ar": "نيكون", "ifd_offset": None,
                    "base": "inner", "inner_tiff_at": 10, "tags": NIKON_TAGS,
                    "version": mn[6:8].hex(),
                    "note": "Nikon Type 3 — ترويسة TIFF مستقلة عند الإزاحة 10."}
        return {"vendor": "Nikon", "vendor_ar": "نيكون", "ifd_offset": 8,
                "base": "tiff", "tags": NIKON_TAGS,
                "note": "Nikon Type 1 — الإزاحات منسوبة لـTIFF الرئيسي."}
    if mn[:8] == b"FUJIFILM":
        return {"vendor": "FujiFilm", "vendor_ar": "فوجي فيلم", "ifd_offset": None,
                "base": "maker", "ifd_ptr_at": 8, "force_endian": "<", "tags": FUJI_TAGS,
                "note": "FujiFilm — مؤشر الـIFD مخزّن عند الإزاحة 8 ومنسوب لبداية الكتلة."}
    if mn[:12] in (b"SONY DSC \x00\x00\x00", b"SONY CAM \x00\x00\x00", b"SONY MOBILE\x00"):
        return {"vendor": "Sony", "vendor_ar": "سوني", "ifd_offset": 12,
                "base": "tiff", "tags": SONY_TAGS, "note": "ترويسة Sony قياسية."}
    if mn[:8] == b"SONYPI\x00\x00" or mn[:8] == b"PREMI\x00\x00\x00":
        return {"vendor": "Sony", "vendor_ar": "سوني", "ifd_offset": 12,
                "base": "tiff", "tags": SONY_TAGS, "note": "ترويسة Sony قديمة."}
    if mn[:10] == b"Panasonic\x00":
        return {"vendor": "Panasonic", "vendor_ar": "باناسونيك", "ifd_offset": 12,
                "base": "tiff", "tags": PANASONIC_TAGS, "note": "ترويسة Panasonic."}
    if mn[:6] == b"OLYMP\x00":
        return {"vendor": "Olympus", "vendor_ar": "أوليمبوس", "ifd_offset": 8,
                "base": "tiff", "tags": OLYMPUS_TAGS, "note": "Olympus Type 1."}
    if mn[:10] == b"OLYMPUS\x00II":
        return {"vendor": "Olympus", "vendor_ar": "أوليمبوس", "ifd_offset": 12,
                "base": "maker", "force_endian": "<", "tags": OLYMPUS_TAGS,
                "note": "Olympus Type 3 — الإزاحات منسوبة لبداية الكتلة."}
    if mn[:7] == b"SAMSUNG" or (m.startswith("SAMSUNG") and mn[:2] not in (b"II", b"MM")):
        return {"vendor": "Samsung", "vendor_ar": "سامسونج", "ifd_offset": 0,
                "base": "tiff", "tags": SAMSUNG_TAGS,
                "note": "Samsung — IFD مباشر بلا ترويسة."}
    if m.startswith("CANON"):
        return {"vendor": "Canon", "vendor_ar": "كانون", "ifd_offset": 0,
                "base": "tiff", "tags": CANON_TAGS,
                "note": "Canon — IFD مباشر بلا ترويسة، الإزاحات منسوبة لـTIFF الرئيسي."}
    if m.startswith("APPLE"):
        return {"vendor": "Apple", "vendor_ar": "آبل", "ifd_offset": 14,
                "base": "maker", "endian_at": 12, "tags": APPLE_TAGS,
                "note": "Apple (استُنتج من حقل Make)."}
    if m.startswith(("NIKON",)):
        return {"vendor": "Nikon", "vendor_ar": "نيكون", "ifd_offset": 0,
                "base": "tiff", "tags": NIKON_TAGS, "note": "Nikon بلا ترويسة."}
    if m.startswith(("SONY",)):
        return {"vendor": "Sony", "vendor_ar": "سوني", "ifd_offset": 0,
                "base": "tiff", "tags": SONY_TAGS, "note": "Sony بلا ترويسة."}
    return None


def _parse_mn_ifd(data: bytes, ifd_off: int, endian: str, base: int,
                  tagmap: dict, limit: int = 512) -> dict:
    """قراءة IFD داخل MakerNote. data = الملف/الكتلة، base = مرجع المؤشرات."""
    out: dict = {}
    if ifd_off < 0 or ifd_off + 2 > len(data):
        return out
    count = struct.unpack_from(endian + "H", data, ifd_off)[0]
    if count == 0 or count > limit:
        return out
    for i in range(count):
        e = ifd_off + 2 + i * 12
        if e + 12 > len(data):
            break
        tag, typ, cnt = struct.unpack_from(endian + "HHI", data, e)
        if typ not in TYPE_SIZES or cnt > 2_000_000:
            continue
        size = TYPE_SIZES[typ] * cnt
        if size <= 4:
            raw = data[e + 8:e + 8 + size]
            ptr = None
        else:
            ptr = struct.unpack_from(endian + "I", data, e + 8)[0] + base
            if ptr < 0 or ptr + size > len(data):
                out[tagmap.get(tag, f"Unknown_0x{tag:04X}")] = {
                    "tag": f"0x{tag:04X}", "type": TYPE_NAMES.get(typ, typ), "count": cnt,
                    "value": None,
                    "_rejected": f"المؤشر {ptr} خارج حدود البيانات — رُفضت القيمة بدل تخمينها",
                }
                continue
            raw = data[ptr:ptr + size]
        val = _decode(raw, typ, cnt, endian)
        name = tagmap.get(tag, f"Unknown_0x{tag:04X}")
        out[name] = {"tag": f"0x{tag:04X}", "type": TYPE_NAMES.get(typ, typ),
                     "count": cnt, "value": val, "offset": ptr,
                     "known": tag in tagmap}
    return out


def _decode(raw: bytes, typ: int, cnt: int, endian: str):
    if typ == 2:
        return raw.split(b"\x00")[0].decode("utf-8", "replace")
    if typ in (1, 6, 7):
        if len(raw) > 256:
            return {"_bytes": len(raw), "hex_preview": raw[:48].hex(" ")}
        if typ == 7 and raw[:1].isalnum() and all(32 <= b < 127 or b == 0 for b in raw[:32]):
            s = raw.split(b"\x00")[0].decode("latin-1", "replace")
            if s.strip():
                return s
        return list(raw)
    fmt = {3: "H", 4: "I", 8: "h", 9: "i", 11: "f", 12: "d"}.get(typ)
    if fmt:
        n = min(cnt, 4096)
        try:
            v = list(struct.unpack_from(endian + fmt * n, raw, 0))
        except struct.error:
            return None
        return v[0] if len(v) == 1 else v
    if typ in (5, 10):
        f = "II" if typ == 5 else "ii"
        v = []
        for i in range(min(cnt, 1024)):
            try:
                num, den = struct.unpack_from(endian + f, raw, i * 8)
            except struct.error:
                break
            v.append([num, den])
        return v[0] if len(v) == 1 else v
    return raw[:128].hex(" ")


# --------------------------------------------------------- مفسّرات خاصة بالمصنّع

def _canon_camera_settings(vals) -> dict:
    out = {}
    if not isinstance(vals, list):
        return out
    for idx, name in CANON_CAMERA_SETTINGS.items():
        if idx < len(vals):
            v = vals[idx]
            if v in (-1, 0xFFFF):
                continue
            out[name] = v
    # تحويلات موثّقة
    fu = out.get("FocalUnits") or 1
    if fu and "MaxFocalLength" in out:
        out["MaxFocalLength_mm"] = round(out["MaxFocalLength"] / fu, 2)
    if fu and "MinFocalLength" in out:
        out["MinFocalLength_mm"] = round(out["MinFocalLength"] / fu, 2)
    for k in ("MaxAperture", "MinAperture"):
        if k in out and out[k] not in (0,):
            out[k + "_fstop"] = round(2 ** (out[k] / 64.0), 2)
    return out


def _apple_runtime(raw) -> dict | None:
    """وسم RunTime في أجهزة آبل هو قاموس bplist يحوي زمن تشغيل الجهاز لحظة الالتقاط."""
    if isinstance(raw, dict) and "hex_preview" in raw:
        return None
    data = bytes(raw) if isinstance(raw, list) else None
    if not data or data[:8] != b"bplist00":
        return None
    d = _bplist(data)
    if not isinstance(d, dict):
        return None
    val, ts = d.get("value"), d.get("timescale")
    out = {"raw_plist": {k: v for k, v in d.items() if isinstance(v, (int, float, str))}}
    if isinstance(val, int) and isinstance(ts, int) and ts:
        sec = val / ts
        out["device_uptime_seconds"] = round(sec, 3)
        out["device_uptime_human"] = str(timedelta(seconds=int(sec)))
        out["forensic_value"] = ("زمن تشغيل الجهاز منذ آخر إقلاع لحظة الالتقاط — "
                                 "يُثبت أن صورتين التُقطتا في نفس جلسة التشغيل ويُرتّبهما "
                                 "زمنيًا حتى لو عُدّلت تواريخ EXIF.")
    return out


def _bplist(data: bytes):
    """قارئ مبسّط لقوائم الخصائص الثنائية (bplist00) — يكفي لوسوم آبل."""
    if len(data) < 40 or data[:8] != b"bplist00":
        return None
    trailer = data[-32:]
    off_size, ref_size = trailer[6], trailer[7]
    num_objs = struct.unpack_from(">Q", trailer, 8)[0]
    top = struct.unpack_from(">Q", trailer, 16)[0]
    table_off = struct.unpack_from(">Q", trailer, 24)[0]
    if num_objs > 10000:
        return None
    offsets = []
    for i in range(num_objs):
        p = table_off + i * off_size
        if p + off_size > len(data):
            return None
        offsets.append(int.from_bytes(data[p:p + off_size], "big"))

    def obj(idx):
        if idx >= len(offsets):
            return None
        o = offsets[idx]
        if o >= len(data):
            return None
        marker = data[o]
        t, n = marker >> 4, marker & 0x0F

        def count_and_start(o, n):
            if n != 0x0F:
                return n, o + 1
            sz = 1 << (data[o + 1] & 0x0F)
            c = int.from_bytes(data[o + 2:o + 2 + sz], "big")
            return c, o + 2 + sz

        if t == 0:
            return {0: None, 8: False, 9: True}.get(n)
        if t == 1:
            ln = 1 << n
            return int.from_bytes(data[o + 1:o + 1 + ln], "big", signed=(ln == 8))
        if t == 2:
            ln = 1 << n
            return struct.unpack_from(">f" if ln == 4 else ">d", data, o + 1)[0]
        if t == 5:
            c, s = count_and_start(o, n)
            return data[s:s + c].decode("ascii", "replace")
        if t == 6:
            c, s = count_and_start(o, n)
            return data[s:s + c * 2].decode("utf-16-be", "replace")
        if t == 0x0A:
            c, s = count_and_start(o, n)
            return [obj(int.from_bytes(data[s + i * ref_size:s + (i + 1) * ref_size], "big"))
                    for i in range(c)]
        if t == 0x0D:
            c, s = count_and_start(o, n)
            keys = [int.from_bytes(data[s + i * ref_size:s + (i + 1) * ref_size], "big")
                    for i in range(c)]
            vals = [int.from_bytes(data[s + (c + i) * ref_size:s + (c + i + 1) * ref_size], "big")
                    for i in range(c)]
            return {obj(k): obj(v) for k, v in zip(keys, vals)}
        return None

    return obj(top)


def _rat(v):
    if isinstance(v, list) and len(v) == 2 and all(isinstance(x, int) for x in v):
        return v[0] / v[1] if v[1] else None
    return None


# --------------------------------------------------------------- الواجهة العامة

def decode(file_data: bytes, tiff_base: int, mn_offset: int, mn_length: int,
           endian: str, make: str = "", model: str = "") -> dict:
    """
    file_data: البيانات التي تحوي TIFF (أي حمولة APP1 بعد "Exif\\0\\0").
    tiff_base: إزاحة بداية ترويسة TIFF داخل file_data.
    mn_offset: إزاحة بايتات MakerNote داخل file_data.
    """
    mn = file_data[mn_offset:mn_offset + mn_length]
    out: dict = {"present": True, "size": len(mn),
                 "header_hex": mn[:16].hex(" "),
                 "header_ascii": "".join(chr(c) if 32 <= c < 127 else "." for c in mn[:16])}
    v = detect_vendor(mn, make, model)
    if not v:
        out.update({"vendor": None, "decoded": False,
                    "reason": "لم تُطابق أي بنية MakerNote معروفة — تُعرض البايتات الخام فقط "
                              "(لا نخمّن بنية غير مؤكدة لأن ذلك يُنتج قيمًا كاذبة)."})
        return out
    out["vendor"] = v["vendor"]
    out["vendor_ar"] = v["vendor_ar"]
    out["structure_note"] = v["note"]
    tagmap = v["tags"]
    e = v.get("force_endian") or endian

    try:
        if v["base"] == "inner":
            start = mn_offset + v["inner_tiff_at"]
            bo = file_data[start:start + 2]
            e = "<" if bo == b"II" else ">"
            first = struct.unpack_from(e + "I", file_data, start + 4)[0]
            fields = _parse_mn_ifd(file_data, start + first, e, start, tagmap)
            out["offset_base"] = "ترويسة TIFF مستقلة داخل MakerNote"
        elif v["base"] == "maker":
            if v.get("endian_at") is not None:
                bo = mn[v["endian_at"]:v["endian_at"] + 2]
                e = "<" if bo == b"II" else ">"
            if v.get("ifd_ptr_at") is not None:
                ptr = struct.unpack_from(e + "I", mn, v["ifd_ptr_at"])[0]
                ifd = mn_offset + ptr
            else:
                ifd = mn_offset + v["ifd_offset"]
            fields = _parse_mn_ifd(file_data, ifd, e, mn_offset, tagmap)
            out["offset_base"] = "بداية كتلة MakerNote"
        else:
            fields = _parse_mn_ifd(file_data, mn_offset + v["ifd_offset"], e, tiff_base, tagmap)
            out["offset_base"] = "بداية TIFF الرئيسي"
    except Exception as ex:
        out["decoded"] = False
        out["reason"] = f"فشل التحليل البنيوي: {type(ex).__name__}: {ex}"
        return out

    if not fields:
        out["decoded"] = False
        out["reason"] = "لم يُقرأ أي وسم صالح — البنية غير مطابقة للمتوقع."
        return out

    out["decoded"] = True
    out["byte_order"] = "Little Endian" if e == "<" else "Big Endian"
    out["tag_count"] = len(fields)
    out["unknown_tags"] = sum(1 for f in fields.values() if not f.get("known", True))
    out["fields"] = fields
    out["identity"] = _extract_identity(v["vendor"], fields)
    out["interpreted"] = _interpret(v["vendor"], fields)
    _compact(fields)                      # اختصار المصفوفات الطويلة بعد استخلاص المعاني
    out["summary"] = _summary(out)
    return out


def _compact(fields: dict, keep: int = 24) -> None:
    """استبدال المصفوفات الثنائية الطويلة بمعاينة سداسية عشرية (بعد تفسيرها)."""
    for f in fields.values():
        v = f.get("value")
        if isinstance(v, list) and len(v) > keep and all(isinstance(x, int) and 0 <= x < 256 for x in v):
            f["value"] = {"_bytes": len(v),
                          "hex_preview": bytes(v[:keep]).hex(" ") + " …"}


def _summary(out: dict) -> dict:
    """ملخّص تنفيذي: ما الذي يربط هذه الصورة بجهاز بعينه؟"""
    ident = out.get("identity") or {}
    keys = [k for k in ident if not k.startswith("_")]
    strong = [k for k in keys
              if ("تسلسلي" in k or "عدّاد الغالق" in k or "معرّف" in k)
              and "طراز" not in k and "العدسة" not in k]
    return {
        "vendor": out.get("vendor"),
        "fields_decoded": out.get("tag_count", 0),
        "identity_fields": len(keys),
        "device_linkable": bool(strong),
        "linking_evidence": strong,
        "verdict": ("🟢 يحتوي MakerNote على محدِّدات تربط الصورة بجسم جهاز بعينه: "
                    + "، ".join(strong)) if strong else
                   ("🟡 فُكّ MakerNote لكنه لا يحوي محدِّدات هوية صريحة لهذا الطراز "
                    "(أو أن المصنّع يُعمّيها)."),
    }


# أهم ما يربط الصورة بجهاز بعينه
def _extract_identity(vendor: str, f: dict) -> dict:
    ident: dict = {}

    def g(name):
        return (f.get(name) or {}).get("value")

    if vendor == "Canon":
        sn = g("SerialNumber")
        if isinstance(sn, int):
            ident["الرقم التسلسلي للكاميرا"] = {
                "value": f"{sn:010d}", "raw": sn, "tag": "Canon 0x000C",
                "note": "كانون تكتب الرقم التسلسلي للجسم في MakerNote مباشرة."}
        isn = g("InternalSerialNumber")
        if isn:
            ident["الرقم التسلسلي الداخلي"] = {"value": isn, "tag": "Canon 0x0096"}
        if g("OwnerName"):
            ident["اسم المالك المسجّل في الكاميرا"] = {"value": g("OwnerName"), "tag": "0x0009"}
        if g("LensModel"):
            ident["طراز العدسة"] = {"value": g("LensModel"), "tag": "0x0095"}
        if g("CanonFirmwareVersion"):
            ident["إصدار البرنامج الثابت"] = {"value": g("CanonFirmwareVersion"), "tag": "0x0007"}
        fn = g("FileNumber")
        if isinstance(fn, int) and fn:
            ident["رقم الملف داخل الكاميرا"] = {
                "value": f"{fn >> 22:03d}-{(fn >> 12) & 0x3FF:04d}" if fn > 0xFFFF else fn,
                "raw": fn, "tag": "0x0008",
                "note": "يتضمن رقم المجلد وتسلسل الصورة داخل الكاميرا."}
        ident["_shutter_note"] = ("كانون لا تكتب عدّاد الغالق في EXIF لمعظم الطرازات "
                                  "(يُقرأ من الكاميرا عبر بروتوكولها) — غيابه هنا طبيعي وليس نقصًا في التحليل.")
    elif vendor == "Nikon":
        for key, label, tag in (("SerialNumber", "الرقم التسلسلي للكاميرا", "0x001D"),
                                ("SerialNumber2", "الرقم التسلسلي (بديل)", "0x00A0")):
            v = g(key)
            if v:
                ident[label] = {"value": v, "tag": f"Nikon {tag}"}
        sc = g("ShutterCount")
        if isinstance(sc, int):
            ident["عدّاد الغالق (عدد الصور طوال عمر الجسم)"] = {
                "value": sc, "tag": "Nikon 0x00A7",
                "note": "دليل قوي جدًا: يربط الصورة بجسم كاميرا محدد ويحدد ترتيبها الزمني "
                        "بين صور الجهاز نفسه حتى لو زُوّرت التواريخ."}
        ic = g("ImageCount")
        if isinstance(ic, int):
            ident["عدّاد الصور"] = {"value": ic, "tag": "0x00A5"}
        lens = g("Lens")
        if isinstance(lens, list) and len(lens) == 4:
            fl = [_rat(x) for x in lens]
            if all(x is not None for x in fl):
                ident["العدسة"] = {
                    "value": f"{fl[0]:g}-{fl[1]:g}mm f/{fl[2]:g}-{fl[3]:g}", "tag": "0x0084"}
        if g("LensType") is not None:
            ident["نوع العدسة (رمز)"] = {"value": g("LensType"), "tag": "0x0083"}
    elif vendor == "Sony":
        if g("SonyModelID") is not None:
            ident["معرّف طراز سوني"] = {"value": g("SonyModelID"), "tag": "0xB001"}
        if g("LensType") is not None:
            ident["رمز العدسة"] = {"value": g("LensType"), "tag": "0xB027"}
        ident["_encrypted_note"] = ("سوني تُعمّي كتل 0x9050/0x3000 التي تحوي الرقم التسلسلي "
                                     "وعدّاد الغالق بمفتاح داخلي غير منشور رسميًا — نرصد وجودها "
                                     "ولا نخمّن محتواها.")
    elif vendor == "Apple":
        for key, label in (("ContentIdentifier", "معرّف المحتوى (يربط الصورة بفيديو Live Photo)"),
                           ("BurstUUID", "معرّف جلسة التصوير المتتابع (Burst)"),
                           ("ImageUniqueID", "المعرّف الفريد للصورة"),
                           ("PhotoIdentifier", "معرّف الصورة في مكتبة الصور")):
            if g(key):
                ident[label] = {"value": g(key), "tag": key}
        rt = _apple_runtime((f.get("RunTime") or {}).get("value"))
        if rt:
            ident["زمن تشغيل الجهاز لحظة الالتقاط"] = rt
        av = g("AccelerationVector")
        if isinstance(av, list) and len(av) == 3:
            vals = [_rat(x) for x in av]
            if all(v is not None for v in vals):
                ident["اتجاه الجهاز لحظة الالتقاط (متجه التسارع)"] = {
                    "value": [round(v, 4) for v in vals], "tag": "0x0008",
                    "note": "قياس مقياس التسارع لحظة الضغط — يكشف وضعية الجهاز الفعلية "
                            "ويصعب تزويره لأنه فيزيائي."}
        ict = g("ImageCaptureType")
        if ict is not None:
            ident["نوع الالتقاط"] = {"value": ict, "tag": "0x0014"}
        ident["_serial_note"] = ("آبل لا تكتب الرقم التسلسلي للجهاز في الصور (سياسة خصوصية) — "
                                  "لكن معرّفات الجلسة وزمن التشغيل تؤدي دورًا رابطًا قويًا.")
    elif vendor == "Panasonic":
        if g("InternalSerialNumber"):
            ident["الرقم التسلسلي الداخلي"] = {"value": g("InternalSerialNumber"), "tag": "0x0025"}
        if g("LensSerialNumber"):
            ident["الرقم التسلسلي للعدسة"] = {"value": g("LensSerialNumber"), "tag": "0x0052"}
        if g("LensType"):
            ident["العدسة"] = {"value": g("LensType"), "tag": "0x0051"}
    elif vendor == "FujiFilm":
        if g("InternalSerialNumber"):
            ident["الرقم التسلسلي الداخلي"] = {"value": g("InternalSerialNumber"), "tag": "0x0010"}
        if isinstance(g("ImageCount"), int):
            ident["عدّاد الصور"] = {"value": g("ImageCount"), "tag": "0x1422"}
    elif vendor == "Olympus":
        if g("SerialNumber"):
            ident["الرقم التسلسلي"] = {"value": g("SerialNumber"), "tag": "0x0404"}
        if isinstance(g("ShutterCount"), int):
            ident["عدّاد الغالق"] = {"value": g("ShutterCount"), "tag": "0x1029"}
    elif vendor == "Samsung":
        if g("FirmwareName"):
            ident["البرنامج الثابت"] = {"value": g("FirmwareName"), "tag": "0xA001"}
        if g("LensType") is not None:
            ident["العدسة"] = {"value": g("LensType"), "tag": "0xA003"}
    return ident


def _interpret(vendor: str, f: dict) -> dict:
    out = {}
    if vendor == "Canon":
        cs = (f.get("CanonCameraSettings") or {}).get("value")
        if cs:
            out["إعدادات الكاميرا لحظة الالتقاط"] = _canon_camera_settings(cs)
        si = (f.get("CanonShotInfo") or {}).get("value")
        if isinstance(si, list) and len(si) > 24:
            out["معلومات اللقطة"] = {
                "SequenceNumber": si[9] if len(si) > 9 else None,
                "AutoRotate": si[29] if len(si) > 29 else None,
                "CameraType": si[28] if len(si) > 28 else None,
            }
    if vendor == "Nikon":
        enc = [k for k in ("ShotInfo", "LensData", "ColorBalance") if k in f]
        if enc:
            out["كتل مُعمّاة"] = {
                "blocks": enc,
                "note": "نيكون تُعمّي هذه الكتل بمفتاح مشتق من الرقم التسلسلي وعدّاد الغالق. "
                        "المفتاحان متاحان هنا، لكن جداول فك التعمية غير مضمّنة في المشروع — "
                        "نُصرّح بذلك بدل عرض قيم غير موثوقة.",
                "key_material_present": bool(f.get("SerialNumber") and f.get("ShutterCount")),
            }
    return out


def from_exif_app1(app1_payload: bytes, make: str = "", model: str = "") -> dict:
    """نقطة الدخول: حمولة APP1 بعد "Exif\\0\\0" (أي بدايتها ترويسة TIFF)."""
    from . import exif as exif_mod
    if app1_payload[:6] == b"Exif\x00\x00":      # تسامح: قد تُمرَّر الحمولة بالترويسة
        app1_payload = app1_payload[6:]
    t = exif_mod.parse_tiff(app1_payload, 0)
    if not t.get("ok"):
        return {"present": False}
    ex = t.get("ExifIFD") or {}
    mn = ex.get("MakerNote")
    if not mn:
        return {"present": False, "reason": "لا يوجد وسم MakerNote في هذه الصورة."}
    endian = "<" if "Little" in (t.get("byte_order") or "") else ">"
    make = make or (t.get("IFD0", {}).get("Make", {}) or {}).get("raw") or ""
    model = model or (t.get("IFD0", {}).get("Model", {}) or {}).get("raw") or ""
    off = mn.get("offset")
    size = None
    raw = mn.get("raw")
    if isinstance(raw, dict) and "_undefined_bytes" in raw:
        size = raw["_undefined_bytes"]
    elif isinstance(raw, list):
        size = len(raw)
    elif isinstance(raw, str):
        size = len(raw)
    if off is None or not size:
        # نعيد البحث عن الوسم يدويًا للحصول على الإزاحة الدقيقة
        found = _locate_makernote(app1_payload, endian)
        if not found:
            return {"present": True, "decoded": False,
                    "reason": "تعذّر تحديد موقع كتلة MakerNote بدقة."}
        off, size = found
    return decode(app1_payload, 0, off, size, endian, str(make), str(model))


def _locate_makernote(data: bytes, endian: str) -> tuple[int, int] | None:
    """بحث مباشر عن إدخال الوسم 0x927C في كل الـIFDs لتحديد إزاحته وطوله بدقة."""
    try:
        first = struct.unpack_from(endian + "I", data, 4)[0]
    except struct.error:
        return None
    stack = [first]
    seen = set()
    while stack:
        ifd = stack.pop()
        if ifd in seen or ifd + 2 > len(data):
            continue
        seen.add(ifd)
        try:
            n = struct.unpack_from(endian + "H", data, ifd)[0]
        except struct.error:
            continue
        if n > 2048:
            continue
        for i in range(n):
            e = ifd + 2 + i * 12
            if e + 12 > len(data):
                break
            tag, typ, cnt = struct.unpack_from(endian + "HHI", data, e)
            if tag == 0x927C and cnt > 8:
                ptr = struct.unpack_from(endian + "I", data, e + 8)[0]
                if 0 <= ptr < len(data):
                    return ptr, min(cnt, len(data) - ptr)
            if tag in (0x8769, 0x8825, 0xA005, 0x014A):
                try:
                    stack.append(struct.unpack_from(endian + "I", data, e + 8)[0])
                except struct.error:
                    pass
    return None


# ===================================================================
#   مسح ملف كامل بحثًا عن كل كتل TIFF/EXIF ثم فكّ MakerNote في كل منها
# ===================================================================

def _tiff_candidates(data: bytes, limit: int = 12) -> list[dict]:
    """
    تحديد كل مواضع ترويسة TIFF الصالحة داخل الملف — بلا افتراض نوع الحاوية.

    يغطي هذا: JPEG APP1، وPNG eXIf، وWebP EXIF، وHEIC، وملف TIFF/RAW خام،
    **وكذلك شظايا EXIF الناجية داخل ملف مُعاد كتابته أو محذوف جزئيًا** —
    وهو بالضبط ما نحتاجه حين تُمسح الميتاداتا الأمامية ويبقى أثرها في الجسم.
    """
    found: list[dict] = []
    seen: set[int] = set()

    def push(off: int, src: str):
        if off in seen or off < 0 or off + 8 > len(data):
            return
        if data[off:off + 4] not in (b"II*\x00", b"MM\x00*"):
            return
        seen.add(off)
        found.append({"offset": off, "source": src})

    if data[:4] in (b"II*\x00", b"MM\x00*"):
        push(0, "ملف TIFF/RAW مباشر")

    pos = 0
    while len(found) < limit:
        i = data.find(b"Exif\x00\x00", pos)
        if i < 0:
            break
        push(i + 6, f"كتلة EXIF عند الإزاحة {i}")
        pos = i + 6

    pos = 0
    while len(found) < limit:                       # PNG eXIf بلا بادئة Exif
        i = data.find(b"eXIf", pos)
        if i < 0:
            break
        push(i + 4, f"مقطع PNG eXIf عند الإزاحة {i}")
        pos = i + 4
    return found[:limit]


def analyze(data: bytes) -> dict:
    """
    الواجهة العليا: فكّ كل MakerNote موجود في الملف (أو في شظاياه).

    لا تعتمد على أي مكتبة خارجية ولا على نوع الملف المعلن — تبحث عن البنية
    نفسها في البايتات. كل قيمة تُقرأ من موضعها الفعلي، وأي مؤشر خارج الحدود
    يُرفض صراحةً بدل تخمينه.
    """
    out: dict = {"scanned_tiff_blocks": 0, "makernotes": [], "present": False}
    if not data or len(data) < 32:
        return out
    cands = _tiff_candidates(data)
    out["scanned_tiff_blocks"] = len(cands)
    seen_sig = set()
    for c in cands:
        payload = data[c["offset"]:]
        try:
            r = from_exif_app1(payload)
        except Exception as ex:                      # لا نُسقط التحليل كله بسبب كتلة تالفة
            out.setdefault("errors", []).append(f"{c['source']}: {type(ex).__name__}: {ex}")
            continue
        if not r.get("present"):
            continue
        sig = (r.get("vendor"), r.get("size"), r.get("header_hex"))
        if sig in seen_sig:
            continue
        seen_sig.add(sig)
        r["container_source"] = c["source"]
        r["tiff_offset_in_file"] = c["offset"]
        out["makernotes"].append(r)

    out["present"] = bool(out["makernotes"])
    decoded = [m for m in out["makernotes"] if m.get("decoded")]
    out["decoded_count"] = len(decoded)
    links: list[str] = []
    for m in decoded:
        links.extend((m.get("summary") or {}).get("linking_evidence") or [])
    out["device_linkable"] = bool(links)
    if not out["present"]:
        out["verdict"] = "لا يوجد MakerNote في هذا الملف (مُزال أو لم يُكتب أصلًا)."
    elif not decoded:
        out["verdict"] = ("⚠️ يوجد MakerNote لكن بنيته لم تُطابق أي مصنّع معروف — "
                          "قد يكون مبتورًا أو مُعاد كتابته بأداة تحرير.")
    else:
        v = decoded[0]
        out["verdict"] = (f"🟢 فُكّ MakerNote الخاص بـ{v.get('vendor_ar') or v.get('vendor')} "
                          f"({v.get('tag_count')} وسمًا)" +
                          (f" — محدِّدات الربط بالجهاز: {'، '.join(sorted(set(links)))}"
                           if links else " — بلا محدِّدات هوية صريحة."))
    return out
