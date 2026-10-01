"""
نحت الملفات (File Carving): استخراج الملفات المدمجة/المخفية داخل أي ملف خام،
بالاعتماد على التوقيعات الثنائية وبنية الصيغة — نفس مبدأ أدوات مثل foremost/scalpel.
"""
from __future__ import annotations

import os
import struct
import zlib

from .signatures import CARVE_SIGS


def _png_length(data: bytes, start: int) -> int | None:
    end = data.find(b"IEND\xaeB`\x82", start)
    return (end + 8 - start) if end > 0 else None


def _jpeg_length(data: bytes, start: int) -> int | None:
    end = data.find(b"\xFF\xD9", start + 3)
    return (end + 2 - start) if end > 0 else None


def _zip_length(data: bytes, start: int) -> int | None:
    eocd = data.find(b"PK\x05\x06", start)
    if eocd < 0:
        return None
    try:
        clen = struct.unpack_from("<H", data, eocd + 20)[0]
    except struct.error:
        return None
    return eocd + 22 + clen - start


def _pdf_length(data: bytes, start: int) -> int | None:
    end = data.find(b"%%EOF", start)
    return (end + 5 - start) if end > 0 else None


def _gzip_length(data: bytes, start: int) -> int | None:
    d = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try:
        d.decompress(data[start:start + 50_000_000])
    except Exception:
        return None
    consumed = len(data) - start - len(d.unused_data)
    return consumed if consumed > 18 else None


_LEN = {"png": _png_length, "jpeg": _jpeg_length, "zip": _zip_length,
        "pdf": _pdf_length, "gzip": _gzip_length}


def carve(data: bytes, outdir: str | None = None, skip_offset_zero: bool = True,
          max_items: int = 120) -> list[dict]:
    """يبحث عن كل التوقيعات داخل البيانات ويستخرج ما يمكن تحديد نهايته."""
    found: list[dict] = []
    occupied: list[tuple[int, int]] = []
    for kind, head, tail, desc in CARVE_SIGS:
        pos = 0
        while len(found) < max_items:
            idx = data.find(head, pos)
            if idx < 0:
                break
            pos = idx + 1
            if skip_offset_zero and idx == 0:
                continue
            if any(s <= idx < e for s, e in occupied):
                continue
            ln = None
            fn = _LEN.get(kind)
            if fn:
                ln = fn(data, idx)
            elif tail:
                e = data.find(tail, idx + len(head))
                if e > 0:
                    ln = e + len(tail) - idx
            if ln is None or ln <= len(head):
                found.append({"type": kind, "description": desc, "offset": idx,
                              "size": None, "extracted": False,
                              "note": "تم رصد التوقيع لكن تعذّر تحديد نهاية الملف بدقة."})
                continue
            if idx + ln > len(data):
                ln = len(data) - idx
            if ln < 64:
                continue
            blob = data[idx:idx + ln]
            item = {"type": kind, "description": desc, "offset": idx, "size": ln,
                    "sha256": __import__("hashlib").sha256(blob).hexdigest(),
                    "extracted": False}
            if outdir:
                os.makedirs(outdir, exist_ok=True)
                name = f"carved_{idx}_{kind}.{ 'jpg' if kind=='jpeg' else kind }"
                with open(os.path.join(outdir, name), "wb") as f:
                    f.write(blob)
                item["file"] = name
                item["extracted"] = True
            occupied.append((idx, idx + ln))
            found.append(item)
    found.sort(key=lambda x: x["offset"])
    return found


def slack_and_gaps(data: bytes, known: list[tuple[int, int]]) -> list[dict]:
    """المناطق غير المُفسَّرة داخل الملف (ممكن تحوي بقايا بيانات محذوفة)."""
    known = sorted([k for k in known if k[1] > k[0]])
    gaps = []
    cur = 0
    for s, e in known:
        if s > cur + 16:
            gaps.append((cur, s))
        cur = max(cur, e)
    if cur < len(data) - 16:
        gaps.append((cur, len(data)))
    out = []
    for s, e in gaps[:50]:
        chunk = data[s:e]
        printable = sum(1 for b in chunk[:4096] if 32 <= b < 127)
        out.append({"offset": s, "size": e - s,
                    "printable_ratio": round(printable / max(1, min(len(chunk), 4096)), 3),
                    "preview": chunk[:120].decode("latin-1", "replace")})
    return out
