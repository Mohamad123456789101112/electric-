"""
استخراج السلاسل النصية (ASCII / UTF-16LE) + استخراج مؤشرات الاختراق والهوية (IOC)
من أي ملف خام — هذه من أهم وسائل استرجاع البيانات من ملفات «ممسوحة».
"""
from __future__ import annotations

import re

_ASCII_RE = re.compile(rb"[\x20-\x7E]{4,}")
_UTF16_RE = re.compile(rb"(?:[\x20-\x7E]\x00){4,}")
_ARABIC_RE = re.compile(
    rb"(?:[\xd8-\xdb][\x80-\xbf]){3,}")  # UTF-8 للعربية

IOC_PATTERNS: dict[str, re.Pattern] = {
    "البريد الإلكتروني": re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,24}"),
    "روابط URL": re.compile(r"\b(?:https?|ftp|smb|file)://[^\s\"'<>\\)]{4,200}"),
    "عناوين IPv4": re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\b"),
    "عناوين IPv6": re.compile(r"\b(?:[A-Fa-f0-9]{1,4}:){7}[A-Fa-f0-9]{1,4}\b"),
    "عناوين MAC": re.compile(r"\b(?:[0-9A-Fa-f]{2}[:\-]){5}[0-9A-Fa-f]{2}\b"),
    "أرقام هواتف دولية": re.compile(r"(?<![\d])\+\d{1,3}[\s\-]?\d{6,14}(?![\d])"),
    "مسارات ويندوز": re.compile(r"[A-Za-z]:\\(?:[^\\/:*?\"<>|\r\n]{1,60}\\){0,8}[^\\/:*?\"<>|\r\n]{1,60}"),
    "مسارات يونكس/ماك": re.compile(r"/(?:Users|home|var|private|storage|sdcard|data)/[A-Za-z0-9._\-/]{3,80}"),
    "معرفات GUID": re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"),
    "محافظ بتكوين": re.compile(r"\b(?:bc1[ac-hj-np-z02-9]{11,71}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})\b"),
    "محافظ إيثريوم": re.compile(r"\b0x[a-fA-F0-9]{40}\b"),
    "بطاقات ائتمان (نمط)": re.compile(r"\b(?:4\d{12}(?:\d{3})?|5[1-5]\d{14}|3[47]\d{13}|6(?:011|5\d{2})\d{12})\b"),
    "مفاتيح AWS": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "مفاتيح/توكنات": re.compile(r"(?i)\b(?:api[_\-]?key|secret|token|passw(?:or)?d)\s*[:=]\s*[^\s,;\"']{6,80}"),
    "رموز JWT": re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b"),
    "تواريخ ISO": re.compile(r"\b(?:19|20)\d{2}[:\-/](?:0[1-9]|1[0-2])[:\-/](?:0[1-9]|[12]\d|3[01])(?:[ T]\d{2}:\d{2}:\d{2})?\b"),
    "إحداثيات جغرافية": re.compile(r"[-+]?\d{1,2}\.\d{4,}\s*,\s*[-+]?\d{1,3}\.\d{4,}"),
    "نطاقات onion": re.compile(r"\b[a-z2-7]{16,56}\.onion\b"),
    "معرف IMEI": re.compile(r"(?<!\d)\d{15}(?!\d)"),
}

# مؤشرات برمجيات/أجهزة تُترك داخل الملفات حتى بعد مسح الميتاداتا
DEVICE_HINTS = [
    "Canon", "NIKON", "SONY", "FUJIFILM", "Panasonic", "OLYMPUS", "PENTAX", "Leica",
    "Hasselblad", "GoPro", "DJI", "Apple", "iPhone", "iPad", "samsung", "SM-", "Xiaomi",
    "Redmi", "HUAWEI", "OPPO", "vivo", "realme", "OnePlus", "Pixel", "Google", "Motorola",
    "Nokia", "Infinix", "Tecno", "HONOR", "ZTE", "Lenovo", "LG Electronics",
]
SOFTWARE_HINTS = [
    "Adobe Photoshop", "Adobe Lightroom", "Adobe Illustrator", "GIMP", "Paint.NET",
    "ImageMagick", "Pixelmator", "Affinity Photo", "Snapseed", "PicsArt", "Facetune",
    "Instagram", "WhatsApp", "Telegram", "Snapchat", "Canva", "Microsoft Word",
    "LibreOffice", "ffmpeg", "Lavf", "x264", "x265", "HandBrake", "VSCO", "Capture One",
    "darktable", "RawTherapee", "Photos 3.0", "Google Photos", "Remini", "Stable Diffusion",
    "Midjourney", "DALL", "Firefly", "AI Generated", "Luminar",
]


def extract_strings(data: bytes, min_len: int = 4, limit: int = 4000) -> dict:
    ascii_s, utf16_s, arabic_s = [], [], []
    for m in _ASCII_RE.finditer(data):
        s = m.group().decode("ascii", "ignore")
        if len(s) >= min_len:
            ascii_s.append({"offset": m.start(), "text": s[:300]})
            if len(ascii_s) >= limit:
                break
    for m in _UTF16_RE.finditer(data):
        s = m.group().decode("utf-16-le", "ignore")
        if len(s) >= min_len:
            utf16_s.append({"offset": m.start(), "text": s[:300]})
            if len(utf16_s) >= limit // 2:
                break
    for m in _ARABIC_RE.finditer(data):
        try:
            s = m.group().decode("utf-8")
        except UnicodeDecodeError:
            continue
        arabic_s.append({"offset": m.start(), "text": s[:300]})
        if len(arabic_s) >= 500:
            break
    return {"ascii": ascii_s, "utf16le": utf16_s, "arabic": arabic_s,
            "counts": {"ascii": len(ascii_s), "utf16le": len(utf16_s), "arabic": len(arabic_s)}}


def extract_iocs(strings_blob: str) -> dict:
    out: dict[str, list[str]] = {}
    for name, rx in IOC_PATTERNS.items():
        found = []
        seen = set()
        for m in rx.finditer(strings_blob):
            v = m.group().strip()
            if v not in seen:
                seen.add(v)
                found.append(v)
            if len(found) >= 200:
                break
        if found:
            out[name] = found
    return out


def luhn_valid(number: str) -> bool:
    digits = [int(c) for c in number if c.isdigit()][::-1]
    total = 0
    for i, d in enumerate(digits):
        if i % 2:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0 and len(digits) >= 13


def hints(strings_blob: str) -> dict:
    devs = sorted({h for h in DEVICE_HINTS if h.lower() in strings_blob.lower()})
    sws = sorted({h for h in SOFTWARE_HINTS if h.lower() in strings_blob.lower()})
    return {"أجهزة محتملة": devs, "برمجيات محتملة": sws}


def analyze(data: bytes) -> dict:
    st = extract_strings(data)
    blob = "\n".join(x["text"] for x in st["ascii"]) + "\n" + \
           "\n".join(x["text"] for x in st["utf16le"])
    iocs = extract_iocs(blob)
    if "بطاقات ائتمان (نمط)" in iocs:
        valid = [c for c in iocs["بطاقات ائتمان (نمط)"] if luhn_valid(c)]
        if valid:
            iocs["بطاقات ائتمان (مُتحقق منها بـ Luhn)"] = valid
        else:
            iocs.pop("بطاقات ائتمان (نمط)")
    return {"strings": st, "iocs": iocs, "hints": hints(blob),
            "arabic_text_blob": "\n".join(x["text"] for x in st["arabic"])[:5000]}
