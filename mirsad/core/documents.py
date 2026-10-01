"""
تحليل المستندات جنائيًا: PDF (كائنات، تحديثات تزايدية، جافاسكربت، ملفات مدمجة، توقيعات)
و OOXML (docx/xlsx/pptx) و ZIP (طوابع زمنية للإدخالات = مؤشر زمني قوي).
"""
from __future__ import annotations

import io
import re
import struct
import zipfile
from datetime import datetime

# ------------------------------------------------------------------------ PDF

_PDF_DATE = re.compile(rb"D:(\d{4})(\d{2})?(\d{2})?(\d{2})?(\d{2})?(\d{2})?([+\-Z])?(\d{2})?'?(\d{2})?")
_INFO_KEYS = ["Title", "Author", "Subject", "Keywords", "Creator", "Producer",
              "CreationDate", "ModDate", "Company", "SourceModified", "Trapped"]
_RISKY = {
    b"/JavaScript": "يحتوي جافاسكربت — قد يُنفّذ كودًا عند الفتح",
    b"/JS": "مرجع جافاسكربت",
    b"/OpenAction": "إجراء تلقائي عند الفتح",
    b"/AA": "إجراء إضافي تلقائي",
    b"/Launch": "تشغيل برنامج خارجي",
    b"/EmbeddedFile": "ملف مدمج داخل المستند",
    b"/RichMedia": "وسائط تفاعلية (Flash/Video)",
    b"/XFA": "نموذج XFA",
    b"/URI": "روابط خارجية",
    b"/SubmitForm": "إرسال بيانات نموذج لجهة خارجية",
    b"/GoToR": "انتقال لملف خارجي",
    b"/ObjStm": "كائنات مضغوطة داخل تيار (تُخفي المحتوى عن الفحص السطحي)",
}


def _pdf_date(raw: bytes) -> str:
    m = _PDF_DATE.search(raw)
    if not m:
        return raw.decode("latin-1", "replace")
    g = [x.decode() if x else None for x in m.groups()]
    s = f"{g[0]}-{g[1] or '01'}-{g[2] or '01'}T{g[3] or '00'}:{g[4] or '00'}:{g[5] or '00'}"
    if g[6] and g[6] != "Z":
        s += f"{g[6]}{g[7] or '00'}:{g[8] or '00'}"
    elif g[6] == "Z":
        s += "Z"
    return s


def parse_pdf(data: bytes) -> dict:
    out: dict = {"is_pdf": False}
    if not data.lstrip()[:5] == b"%PDF-":
        return out
    out["is_pdf"] = True
    out["version"] = data[5:8].decode("latin-1", "replace")
    out["objects_declared"] = len(re.findall(rb"\n?\d+\s+\d+\s+obj\b", data))
    out["streams"] = len(re.findall(rb"\bstream\b", data))
    eofs = [m.start() for m in re.finditer(rb"%%EOF", data)]
    out["eof_markers"] = len(eofs)
    xrefs = [m.start() for m in re.finditer(rb"\bxref\b", data)]
    out["incremental_updates"] = max(0, len(eofs) - 1)
    if out["incremental_updates"] > 0:
        out["incremental_note"] = (
            f"⚠️ المستند يحتوي {out['incremental_updates']} تحديثًا تزايديًا (Incremental Update) — "
            "أي أنه عُدّل بعد إنشائه الأول، والنسخ السابقة لا تزال موجودة فعليًا داخل الملف "
            "ويمكن استرجاع محتواها القديم.")
        out["revision_offsets"] = eofs
    if eofs and eofs[-1] + 6 < len(data) - 2:
        out["trailing_data"] = {"offset": eofs[-1] + 5, "size": len(data) - eofs[-1] - 5,
                                "preview_hex": data[eofs[-1] + 5:eofs[-1] + 133].hex(" "),
                                "note": "بيانات بعد آخر %%EOF."}

    info: dict = {}
    for m in re.finditer(rb"/Info\s+(\d+)\s+(\d+)\s*R", data):
        num = int(m.group(1))
        om = re.search(rb"(?<![0-9])" + str(num).encode() + rb"\s+0\s+obj(.{0,4000}?)endobj", data, re.S)
        if om:
            info.update(_parse_info_dict(om.group(1)))
    if not info:
        for m in re.finditer(rb"/(Title|Author|Creator|Producer|CreationDate|ModDate|Subject|Keywords)\s*\(((?:[^()\\]|\\.)*)\)", data):
            info[m.group(1).decode()] = _decode_pdf_string(m.group(2))
    for k in ("CreationDate", "ModDate", "SourceModified"):
        if k in info and isinstance(info[k], str) and info[k].startswith("D:"):
            info[k] = _pdf_date(info[k].encode("latin-1", "replace"))
    out["info"] = info

    xmp = re.search(rb"<x:xmpmeta.*?</x:xmpmeta>", data, re.S)
    if xmp:
        out["xmp"] = xmp.group().decode("utf-8", "replace")[:200000]

    risk = []
    for key, desc in _RISKY.items():
        c = data.count(key)
        if c:
            risk.append({"marker": key.decode(), "count": c, "risk": desc})
    out["risk_indicators"] = risk

    out["encrypted"] = b"/Encrypt" in data
    out["signed"] = b"/Sig" in data or b"adbe.pkcs7" in data
    pages = re.findall(rb"/Type\s*/Page[^s]", data)
    out["page_count_estimate"] = len(pages)
    emb = re.findall(rb"/F\s*\((?:[^()\\]|\\.){1,200}\)", data)
    out["embedded_file_names"] = sorted({_decode_pdf_string(x[3:-1]) for x in emb})[:50]
    fonts = sorted({m.group(1).decode("latin-1", "replace")
                    for m in re.finditer(rb"/BaseFont\s*/([A-Za-z0-9+\-,._]{1,60})", data)})
    out["fonts"] = fonts[:60]
    ids = re.search(rb"/ID\s*\[\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", data)
    if ids:
        out["document_id"] = {"original": ids.group(1).decode(), "current": ids.group(2).decode(),
                              "changed": ids.group(1) != ids.group(2)}
        if out["document_id"]["changed"]:
            out["document_id"]["note"] = "معرّفا المستند مختلفان ⇒ المستند عُدّل بعد الإنشاء."
    return out


def _decode_pdf_string(b: bytes) -> str:
    b = re.sub(rb"\\([()\\])", rb"\1", b)
    if b[:2] == b"\xfe\xff":
        return b[2:].decode("utf-16-be", "replace")
    if b[:3] == b"\xef\xbb\xbf":
        return b[3:].decode("utf-8", "replace")
    if any(c > 127 for c in b):
        try:
            return b.decode("utf-8")      # كثير من المنتجين يكتبون UTF-8 دون علامة ترتيب
        except UnicodeDecodeError:
            pass
    return b.decode("latin-1", "replace")


def _parse_info_dict(blob: bytes) -> dict:
    out = {}
    for m in re.finditer(rb"/([A-Za-z]+)\s*(?:\(((?:[^()\\]|\\.)*)\)|<([0-9A-Fa-f\s]+)>)", blob):
        key = m.group(1).decode()
        if key not in _INFO_KEYS:
            continue
        if m.group(2) is not None:
            out[key] = _decode_pdf_string(m.group(2))
        else:
            hexs = re.sub(rb"\s", b"", m.group(3))
            try:
                out[key] = _decode_pdf_string(bytes.fromhex(hexs.decode()))
            except Exception:
                pass
    return out


# ---------------------------------------------------------------------- OOXML

_OOXML_CORE = {
    "dc:title": "العنوان", "dc:subject": "الموضوع", "dc:creator": "المُنشئ (اسم المستخدم)",
    "cp:keywords": "كلمات مفتاحية", "dc:description": "الوصف",
    "cp:lastModifiedBy": "آخر من عدّل (اسم المستخدم)", "cp:revision": "رقم المراجعة",
    "dcterms:created": "تاريخ الإنشاء", "dcterms:modified": "تاريخ آخر تعديل",
    "cp:category": "التصنيف", "cp:contentStatus": "حالة المحتوى",
    "cp:lastPrinted": "تاريخ آخر طباعة",
}
_OOXML_APP = {
    "Application": "التطبيق", "AppVersion": "إصدار التطبيق", "Company": "الشركة",
    "Manager": "المدير", "TotalTime": "إجمالي وقت التحرير (دقائق)", "Pages": "عدد الصفحات",
    "Words": "عدد الكلمات", "Characters": "عدد الأحرف", "Lines": "الأسطر",
    "Paragraphs": "الفقرات", "Template": "القالب", "DocSecurity": "حماية المستند",
}


def parse_ooxml(data: bytes) -> dict:
    out: dict = {"is_zip": False}
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except Exception as e:
        return {"is_zip": False, "error": str(e)}
    out["is_zip"] = True
    entries = []
    for zi in zf.infolist():
        entries.append({
            "name": zi.filename, "size": zi.file_size, "compressed": zi.compress_size,
            "modified": "%04d-%02d-%02dT%02d:%02d:%02d" % zi.date_time,
            "crc32": format(zi.CRC & 0xFFFFFFFF, "08x"),
            "method": {0: "مخزّن", 8: "Deflate", 14: "LZMA", 93: "Zstd"}.get(zi.compress_type, zi.compress_type),
            "encrypted": bool(zi.flag_bits & 0x1),
            "created_by": zi.create_system,
        })
    out["entries"] = entries
    out["entry_count"] = len(entries)
    names = {e["name"] for e in entries}
    kind = ("docx" if any(n.startswith("word/") for n in names) else
            "xlsx" if any(n.startswith("xl/") for n in names) else
            "pptx" if any(n.startswith("ppt/") for n in names) else
            "apk" if "AndroidManifest.xml" in names else "zip")
    out["kind"] = kind

    meta: dict = {}
    for part, mapping in (("docProps/core.xml", _OOXML_CORE), ("docProps/app.xml", _OOXML_APP)):
        if part in names:
            try:
                xml = zf.read(part).decode("utf-8", "replace")
            except Exception:
                continue
            for tag, label in mapping.items():
                m = re.search(rf"<{re.escape(tag)}[^>]*>(.*?)</{re.escape(tag)}>", xml, re.S)
                if m and m.group(1).strip():
                    meta[label] = m.group(1).strip()[:500]
            out.setdefault("raw_xml", {})[part] = xml[:20000]
    if "docProps/custom.xml" in names:
        xml = zf.read("docProps/custom.xml").decode("utf-8", "replace")
        for m in re.finditer(r'name="([^"]+)"[^>]*>\s*<[^>]+>([^<]*)<', xml):
            meta[f"خاصية مخصصة: {m.group(1)}"] = m.group(2)
    out["metadata"] = meta

    media = [e for e in entries if re.search(r"/(media|embeddings)/", e["name"])]
    out["embedded_media"] = media
    out["has_macros"] = any("vbaProject.bin" in n for n in names)
    if out["has_macros"]:
        out["macro_warning"] = "⚠️ المستند يحتوي ماكرو VBA (vbaProject.bin) — خطر تنفيذ كود."
    out["external_links"] = sorted({m for n in names if n.endswith(".rels")
                                    for m in re.findall(r'Target="(https?://[^"]+)"',
                                                        zf.read(n).decode("utf-8", "replace"))})[:100]
    out["tracked_changes"] = False
    if kind == "docx" and "word/document.xml" in names:
        doc = zf.read("word/document.xml").decode("utf-8", "replace")
        out["tracked_changes"] = ("<w:ins " in doc) or ("<w:del " in doc)
        out["comments_present"] = "word/comments.xml" in names
        text = re.sub(r"<[^>]+>", " ", doc)
        out["text_preview"] = re.sub(r"\s+", " ", text).strip()[:4000]
        if out["tracked_changes"]:
            authors = sorted(set(re.findall(r'w:author="([^"]+)"', doc)))
            out["revision_authors"] = authors
            out["tracked_note"] = "⚠️ يحتوي تعديلات متتبّعة غير مقبولة — النص المحذوف ما زال داخل الملف."

    ts = [e["modified"] for e in entries]
    if ts:
        out["zip_timestamp_range"] = {"earliest": min(ts), "latest": max(ts),
                                      "note": "طوابع ZIP زمنية بتوقيت محلي للجهاز الذي أنشأ الملف."}
    return out


def zip_structure(data: bytes) -> dict:
    """فحص بنية ZIP على مستوى البايت: كشف البيانات قبل/بعد الأرشيف والتعليقات."""
    out: dict = {}
    eocd = data.rfind(b"PK\x05\x06")
    if eocd < 0:
        return out
    try:
        _, _, _, _, cd_size, cd_off, clen = struct.unpack_from("<HHHHIIH", data, eocd + 4)
    except struct.error:
        return out
    out["eocd_offset"] = eocd
    out["central_directory_offset"] = cd_off
    out["central_directory_size"] = cd_size
    first_local = data.find(b"PK\x03\x04")
    expected_start = cd_off + cd_size + 22 + clen
    if first_local > 0:
        out["prepended_data"] = {"size": first_local,
                                 "note": "⚠️ توجد بيانات قبل بداية الأرشيف — ملف مُدمج (polyglot) أو self-extracting."}
    if eocd + 22 + clen < len(data):
        out["appended_data"] = {"offset": eocd + 22 + clen, "size": len(data) - (eocd + 22 + clen),
                                "note": "⚠️ بيانات بعد نهاية الأرشيف."}
    if clen:
        out["archive_comment"] = data[eocd + 22:eocd + 22 + clen].decode("utf-8", "replace")
    return out
