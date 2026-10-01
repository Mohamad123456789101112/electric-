"""
تعريف أنواع الملفات عن طريق التوقيعات الثنائية (Magic bytes) — بدون الاعتماد على الامتداد.
المراجع: Gary Kessler File Signature Table + مواصفات الصيغ الرسمية.
كل التحليل هنا حقيقي ويقرأ البايتات فعليًا.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Optional

# (التوقيع بالهكس, الإزاحة, الامتداد, النوع MIME, الوصف العربي, توقيع النهاية إن وُجد)
SIGNATURES: list[tuple[bytes, int, str, str, str, Optional[bytes]]] = [
    (b"\xFF\xD8\xFF", 0, "jpg", "image/jpeg", "صورة JPEG", b"\xFF\xD9"),
    (b"\x89PNG\r\n\x1a\n", 0, "png", "image/png", "صورة PNG", b"IEND\xaeB`\x82"),
    (b"GIF87a", 0, "gif", "image/gif", "صورة GIF87a", b"\x00\x3B"),
    (b"GIF89a", 0, "gif", "image/gif", "صورة GIF89a", b"\x00\x3B"),
    (b"BM", 0, "bmp", "image/bmp", "صورة BMP", None),
    (b"II*\x00", 0, "tif", "image/tiff", "صورة TIFF (Little Endian)", None),
    (b"MM\x00*", 0, "tif", "image/tiff", "صورة TIFF (Big Endian)", None),
    (b"II+\x00", 0, "tif", "image/tiff", "صورة BigTIFF", None),
    (b"RIFF", 0, "riff", "application/octet-stream", "حاوية RIFF", None),
    (b"\x00\x00\x01\x00", 0, "ico", "image/x-icon", "أيقونة ICO", None),
    (b"8BPS", 0, "psd", "image/vnd.adobe.photoshop", "ملف فوتوشوب PSD", None),
    (b"qoif", 0, "qoi", "image/qoi", "صورة QOI", None),
    (b"\x76\x2F\x31\x01", 0, "exr", "image/x-exr", "صورة OpenEXR", None),
    (b"%PDF-", 0, "pdf", "application/pdf", "مستند PDF", b"%%EOF"),
    (b"PK\x03\x04", 0, "zip", "application/zip", "أرشيف ZIP / حاوية OOXML", None),
    (b"PK\x05\x06", 0, "zip", "application/zip", "أرشيف ZIP فارغ", None),
    (b"Rar!\x1a\x07\x00", 0, "rar", "application/x-rar", "أرشيف RAR v4", None),
    (b"Rar!\x1a\x07\x01\x00", 0, "rar", "application/x-rar", "أرشيف RAR v5", None),
    (b"7z\xbc\xaf\x27\x1c", 0, "7z", "application/x-7z-compressed", "أرشيف 7-Zip", None),
    (b"\x1f\x8b\x08", 0, "gz", "application/gzip", "أرشيف GZIP", None),
    (b"BZh", 0, "bz2", "application/x-bzip2", "أرشيف BZIP2", None),
    (b"\xfd7zXZ\x00", 0, "xz", "application/x-xz", "أرشيف XZ", None),
    (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", 0, "ole", "application/x-ole-storage",
     "حاوية OLE2 (مستندات أوفيس قديمة / MSI)", None),
    (b"{\\rtf", 0, "rtf", "application/rtf", "مستند RTF", None),
    (b"MZ", 0, "exe", "application/x-dosexec", "ملف تنفيذي Windows (PE)", None),
    (b"\x7fELF", 0, "elf", "application/x-executable", "ملف تنفيذي Linux (ELF)", None),
    (b"\xca\xfe\xba\xbe", 0, "class", "application/java-vm", "Java class / Mach-O Fat", None),
    (b"\xcf\xfa\xed\xfe", 0, "macho", "application/x-mach-binary", "ملف تنفيذي macOS (Mach-O)", None),
    (b"dex\n", 0, "dex", "application/x-dex", "Android Dalvik DEX", None),
    (b"ID3", 0, "mp3", "audio/mpeg", "صوت MP3 بوسم ID3", None),
    (b"\xff\xfb", 0, "mp3", "audio/mpeg", "صوت MP3 (MPEG-1 Layer III)", None),
    (b"fLaC", 0, "flac", "audio/flac", "صوت FLAC", None),
    (b"OggS", 0, "ogg", "audio/ogg", "حاوية OGG", None),
    (b"ftyp", 4, "mp4", "video/mp4", "حاوية ISO-BMFF (MP4/MOV/HEIC)", None),
    (b"moov", 4, "mov", "video/quicktime", "فيديو QuickTime", None),
    (b"\x1aE\xdf\xa3", 0, "mkv", "video/x-matroska", "حاوية Matroska/WebM", None),
    (b"FLV\x01", 0, "flv", "video/x-flv", "فيديو Flash FLV", None),
    (b"\x00\x00\x01\xba", 0, "mpg", "video/mpeg", "تيار MPEG-PS", None),
    (b"SQLite format 3\x00", 0, "sqlite", "application/vnd.sqlite3", "قاعدة بيانات SQLite", None),
    (b"regf", 0, "dat", "application/x-ms-registry", "خلية سجل ويندوز (Registry Hive)", None),
    (b"\x00\x01\x00\x00Standard Jet DB", 0, "mdb", "application/x-msaccess", "قاعدة Access", None),
    (b"-----BEGIN ", 0, "pem", "application/x-pem-file", "مفتاح/شهادة PEM", None),
    (b"\x30\x82", 0, "der", "application/x-x509-ca-cert", "بنية ASN.1 DER (شهادة/مفتاح)", None),
    (b"EVF\x09\x0d\x0a\xff\x00", 0, "e01", "application/x-ewf", "صورة قرص جنائية EnCase E01", None),
    (b"AFF", 0, "aff", "application/x-aff", "صورة قرص AFF", None),
    (b"KDMV", 0, "vmdk", "application/x-vmdk", "قرص VMware VMDK", None),
    (b"conectix", 0, "vhd", "application/x-vhd", "قرص VHD", None),
    (b"\xd4\xc3\xb2\xa1", 0, "pcap", "application/vnd.tcpdump.pcap", "التقاط شبكة PCAP", None),
    (b"\xa1\xb2\xc3\xd4", 0, "pcap", "application/vnd.tcpdump.pcap", "التقاط شبكة PCAP (BE)", None),
    (b"\x0a\x0d\x0d\x0a", 0, "pcapng", "application/x-pcapng", "التقاط شبكة PCAPNG", None),
    (b"\x25\x21PS", 0, "ps", "application/postscript", "PostScript", None),
    (b"wOFF", 0, "woff", "font/woff", "خط WOFF", None),
    (b"wOF2", 0, "woff2", "font/woff2", "خط WOFF2", None),
    (b"\x00\x01\x00\x00\x00", 0, "ttf", "font/ttf", "خط TrueType", None),
    (b"OTTO", 0, "otf", "font/otf", "خط OpenType", None),
    (b"CWS", 0, "swf", "application/x-shockwave-flash", "Flash SWF مضغوط", None),
    (b"FWS", 0, "swf", "application/x-shockwave-flash", "Flash SWF", None),
]

# توقيعات تُستخدم في نحت الملفات (carving) داخل الملفات الأخرى
CARVE_SIGS: list[tuple[str, bytes, Optional[bytes], str]] = [
    ("jpeg", b"\xFF\xD8\xFF\xE0", b"\xFF\xD9", "صورة JPEG/JFIF"),
    ("jpeg", b"\xFF\xD8\xFF\xE1", b"\xFF\xD9", "صورة JPEG/Exif"),
    ("jpeg", b"\xFF\xD8\xFF\xDB", b"\xFF\xD9", "صورة JPEG خام"),
    ("jpeg", b"\xFF\xD8\xFF\xEE", b"\xFF\xD9", "صورة JPEG/Adobe"),
    ("png", b"\x89PNG\r\n\x1a\n", b"IEND\xaeB`\x82", "صورة PNG"),
    ("gif", b"GIF89a", b"\x00\x3B", "صورة GIF"),
    ("zip", b"PK\x03\x04", None, "أرشيف ZIP / OOXML"),
    ("pdf", b"%PDF-", b"%%EOF", "مستند PDF"),
    ("rar", b"Rar!\x1a\x07", None, "أرشيف RAR"),
    ("gzip", b"\x1f\x8b\x08", None, "أرشيف GZIP"),
    ("ole", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", None, "مستند OLE2"),
    ("exe", b"MZ\x90\x00", None, "ملف تنفيذي PE"),
    ("elf", b"\x7fELF", None, "ملف تنفيذي ELF"),
    ("sqlite", b"SQLite format 3\x00", None, "قاعدة SQLite"),
    ("tiff", b"II*\x00", None, "صورة TIFF"),
    ("icc", b"acsp", None, "ملف تعريف ألوان ICC"),
    ("xml", b"<?xml", None, "مستند XML"),
]

EXT_TO_MIME = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "gif": "image/gif",
    "bmp": "image/bmp", "tif": "image/tiff", "tiff": "image/tiff", "webp": "image/webp",
    "heic": "image/heic", "pdf": "application/pdf", "docx": "application/zip",
    "xlsx": "application/zip", "pptx": "application/zip", "zip": "application/zip",
    "mp4": "video/mp4", "mov": "video/quicktime", "mp3": "audio/mpeg", "txt": "text/plain",
}


@dataclass
class TypeID:
    mime: str = "application/octet-stream"
    ext: str = "bin"
    description: str = "بيانات ثنائية غير معروفة"
    confidence: float = 0.0
    matched_signature: str = ""
    offset: int = 0
    extension_mismatch: bool = False
    notes: list[str] = field(default_factory=list)


def _riff_subtype(data: bytes) -> tuple[str, str, str]:
    sub = data[8:12]
    table = {
        b"WEBP": ("webp", "image/webp", "صورة WebP"),
        b"WAVE": ("wav", "audio/wav", "صوت WAV"),
        b"AVI ": ("avi", "video/x-msvideo", "فيديو AVI"),
        b"ANI ": ("ani", "application/x-navi-animation", "مؤشر متحرك ANI"),
    }
    return table.get(sub, ("riff", "application/octet-stream", "حاوية RIFF غير معروفة"))


def _ftyp_subtype(data: bytes) -> tuple[str, str, str]:
    brand = data[8:12]
    table = {
        b"isom": ("mp4", "video/mp4", "فيديو MP4 (ISO Base Media)"),
        b"mp41": ("mp4", "video/mp4", "فيديو MP4 v1"),
        b"mp42": ("mp4", "video/mp4", "فيديو MP4 v2"),
        b"qt  ": ("mov", "video/quicktime", "فيديو QuickTime MOV"),
        b"heic": ("heic", "image/heic", "صورة HEIC (آيفون)"),
        b"heix": ("heic", "image/heic", "صورة HEIC"),
        b"mif1": ("heif", "image/heif", "صورة HEIF"),
        b"avif": ("avif", "image/avif", "صورة AVIF"),
        b"3gp4": ("3gp", "video/3gpp", "فيديو 3GP"),
        b"M4A ": ("m4a", "audio/mp4", "صوت M4A"),
        b"M4V ": ("m4v", "video/x-m4v", "فيديو M4V"),
        b"crx ": ("cr3", "image/x-canon-cr3", "صورة Canon RAW CR3"),
    }
    return table.get(brand, ("mp4", "video/mp4", f"حاوية ISO-BMFF (العلامة {brand.decode('latin1')})"))


def _zip_subtype(data: bytes) -> tuple[str, str, str]:
    head = data[:4096]
    if b"word/" in head or b"word/document.xml" in data[:65536]:
        return ("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "مستند Word (docx)")
    if b"xl/" in head or b"xl/workbook.xml" in data[:65536]:
        return ("xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "جدول Excel (xlsx)")
    if b"ppt/" in head or b"ppt/presentation.xml" in data[:65536]:
        return ("pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation", "عرض PowerPoint (pptx)")
    if b"mimetypeapplication/vnd.oasis.opendocument" in data[:200]:
        return ("odf", "application/vnd.oasis.opendocument", "مستند OpenDocument")
    if b"AndroidManifest.xml" in data[:65536]:
        return ("apk", "application/vnd.android.package-archive", "تطبيق أندرويد APK")
    if b"META-INF/MANIFEST.MF" in data[:65536]:
        return ("jar", "application/java-archive", "أرشيف Java JAR")
    if b"mimetypeapplication/epub+zip" in data[:200]:
        return ("epub", "application/epub+zip", "كتاب EPUB")
    return ("zip", "application/zip", "أرشيف ZIP")


def identify(data: bytes, filename: str = "") -> TypeID:
    """تعريف نوع الملف من محتواه الفعلي، ومقارنته بالامتداد المعلن لكشف التمويه."""
    best: Optional[TypeID] = None
    for sig, off, ext, mime, desc, _end in SIGNATURES:
        if len(data) >= off + len(sig) and data[off:off + len(sig)] == sig:
            tid = TypeID(mime=mime, ext=ext, description=desc,
                         confidence=min(0.55 + 0.05 * len(sig), 0.99),
                         matched_signature=sig.hex(" ").upper(), offset=off)
            if best is None or len(sig) > len(best.matched_signature.split()):
                best = tid

    if best is None:
        # نص؟ (نحاول فك الترميز فعليًا ونقيس نسبة المحارف المطبوعة)
        sample = data[:8192]
        if sample:
            txt = None
            enc = None
            for e in ("utf-8", "utf-16-le", "utf-16-be"):
                for cut in (0, 1, 2, 3):      # قد تُقطع العيّنة داخل محرف متعدد البايتات
                    try:
                        txt = sample[:len(sample) - cut].decode(e)
                        enc = e
                        break
                    except UnicodeDecodeError:
                        txt = None
                if txt is not None:
                    break
            if txt is not None:
                printable = sum(1 for ch in txt if ch.isprintable() or ch in "\t\n\r")
                if printable / max(1, len(txt)) > 0.95:
                    low = txt.lstrip()[:200].lower()
                    kind, desc = "txt", f"ملف نصي ({enc.upper()})"
                    if low.startswith(("<?xml", "<!doctype", "<html", "<svg")):
                        kind, desc = "xml", "مستند XML/HTML"
                    elif low.startswith(("{", "[")) and ('":' in txt[:2000] or "': " in txt[:2000]):
                        kind, desc = "json", "بيانات JSON"
                    elif low.startswith(("#!/", "import ", "from ", "def ", "#include", "package ",
                                         "using ", "<?php", "function ")):
                        kind, desc = "src", "شيفرة مصدرية نصية"
                    best = TypeID("text/plain" if kind != "xml" else "text/xml",
                                  kind, desc, 0.7, "", 0)
    if best is None:
        best = TypeID()
        best.notes.append("لم يُطابق أي توقيع معروف — قد يكون ملفًا مشفرًا أو مضغوطًا أو تالفًا أو خامًا.")
        return best

    if best.ext == "riff":
        e, m, d = _riff_subtype(data)
        best.ext, best.mime, best.description = e, m, d
    elif best.ext in ("mp4", "mov") and data[4:8] == b"ftyp":
        e, m, d = _ftyp_subtype(data)
        best.ext, best.mime, best.description = e, m, d
    elif best.ext == "zip":
        e, m, d = _zip_subtype(data)
        best.ext, best.mime, best.description = e, m, d
    elif best.ext == "ole":
        low = data[:8192]
        if b"W\x00o\x00r\x00d\x00D\x00o\x00c\x00u\x00m\x00e\x00n\x00t" in data[:65536]:
            best.ext, best.mime, best.description = "doc", "application/msword", "مستند Word 97-2003 (doc)"
        elif b"W\x00o\x00r\x00k\x00b\x00o\x00o\x00k" in data[:65536]:
            best.ext, best.mime, best.description = "xls", "application/vnd.ms-excel", "جدول Excel 97-2003 (xls)"
        del low

    declared = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if declared:
        # عائلات الامتدادات المتكافئة (لا تُعد تمويهًا)
        families = [
            {"jpg", "jpeg", "jpe", "jfif"},
            {"tif", "tiff"},
            {"htm", "html", "xhtml", "xml", "svg", "rss", "plist"},
            {"txt", "src", "md", "csv", "tsv", "log", "ini", "cfg", "conf", "yml", "yaml",
             "py", "js", "mjs", "ts", "css", "c", "h", "cpp", "hpp", "java", "cs", "go",
             "rs", "rb", "php", "pl", "sh", "bash", "bat", "ps1", "sql", "r", "m", "lua",
             "swift", "kt", "toml", "env", "gitignore", "srt", "vtt", "asc", "pem", "json",
             "geojson", "ndjson", "properties", "gradle", "make", "mk", "dockerfile", "tex"},
            {"zip", "docx", "xlsx", "pptx", "apk", "jar", "epub", "odf", "odt", "ods", "odp"},
            {"mp4", "m4v", "m4a", "mov", "3gp", "heic", "heif", "avif", "cr3"},
            {"ole", "doc", "xls", "ppt", "msi", "msg"},
            {"exe", "dll", "sys", "ocx", "scr", "cpl"},
            {"sqlite", "sqlite3", "db", "db3"},
            {"pcap", "pcapng", "cap"},
            {"riff", "wav", "avi", "webp"},
        ]
        same = declared == best.ext or any(
            declared in f and best.ext in f for f in families)
        if not same:
            best.extension_mismatch = True
            best.notes.append(
                f"⚠️ تضارب خطير: الامتداد المعلن «.{declared}» لا يطابق المحتوى الحقيقي «{best.description}». "
                "هذا مؤشر كلاسيكي على إخفاء متعمّد لنوع الملف.")
    return best


def pe_info(data: bytes) -> dict:
    """قراءة ترويسة PE حقيقية (للملفات التنفيذية) — وقت التصريف يُستخدم كدليل زمني."""
    out: dict = {}
    if data[:2] != b"MZ" or len(data) < 0x40:
        return out
    e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
    if e_lfanew + 24 > len(data) or data[e_lfanew:e_lfanew + 4] != b"PE\x00\x00":
        return out
    machine, nsec, tstamp = struct.unpack_from("<HHI", data, e_lfanew + 4)
    out["machine"] = {0x014c: "i386", 0x8664: "x86-64", 0x01c0: "ARM", 0xaa64: "ARM64"}.get(machine, hex(machine))
    out["sections"] = nsec
    out["compile_timestamp_utc"] = tstamp
    return out
