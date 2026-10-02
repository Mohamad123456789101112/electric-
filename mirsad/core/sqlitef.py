"""
تحليل جنائي عميق لقواعد بيانات SQLite — بما فيها **السجلات المحذوفة**.

لماذا هذه الوحدة؟ لأن كل ما يهمّ في الهاتف تقريبًا مخزَّن في SQLite: رسائل
واتساب والمحادثات، سجل المكالمات، جهات الاتصال، سجل المتصفح، الإشعارات،
مواقع الصور في معرض الصور… وهذه هي القدرة التي تبيعها الأدوات التجارية
(Cellebrite / AXIOM) بآلاف الدولارات.

الحقيقة الفنية التي تجعل الاسترجاع ممكنًا: عند تنفيذ `DELETE` لا يمحو SQLite
البايتات. يفعل أحد ثلاثة أشياء فقط:
  1) يضع الخلية في قائمة «الكتل الحرة» (freeblocks) داخل نفس الصفحة،
  2) أو يُلحق الصفحة كلها بقائمة الصفحات الحرة (freelist) بمحتواها كما هو،
  3) أو يترك البيانات في المساحة غير المخصَّصة بين مؤشرات الخلايا ومحتواها.
وفي كل الحالات يبقى السجل القديم مكتوبًا على القرص حتى يُعاد استخدام المكان.

وكذلك ملفا `-wal` و`-journal` يحتفظان بنسخ **سابقة** من الصفحات، فيكشفان
التعديلات والحذف حتى بعد أن تبدو القاعدة نظيفة.

كل شيء هنا مكتوب بقراءة البايتات مباشرة وفق توصيف صيغة ملف SQLite الرسمي:
لا نستخدم محرّك sqlite3 إطلاقًا في التحليل (نستخدمه في الاختبارات فقط لبناء
حقيقة مرجعية نقارن بها).
"""
from __future__ import annotations

import datetime
import re
import struct

MAGIC = b"SQLite format 3\x00"
WAL_MAGIC = (0x377F0682, 0x377F0683)

PAGE_TYPES = {
    2: ("فهرس داخلي", "interior index"),
    5: ("جدول داخلي", "interior table"),
    10: ("فهرس ورقي", "leaf index"),
    13: ("جدول ورقي", "leaf table"),
}

TEXT_ENCODINGS = {1: "UTF-8", 2: "UTF-16LE", 3: "UTF-16BE"}


# ===================================================================
#   أدوات القراءة الأساسية (varint وأنواع السجل)
# ===================================================================

def read_varint(data: bytes, off: int) -> tuple[int, int]:
    """عدد متغيّر الطول (big-endian، 7 بت لكل بايت، 9 بايت كحدّ أقصى)."""
    val = 0
    for i in range(9):
        if off + i >= len(data):
            return 0, 0
        b = data[off + i]
        if i == 8:
            val = (val << 8) | b
            return val, 9
        val = (val << 7) | (b & 0x7F)
        if not (b & 0x80):
            return val, i + 1
    return val, 9


def _twos(v: int, bits: int) -> int:
    return v - (1 << bits) if v >= (1 << (bits - 1)) else v


def serial_size(t: int) -> int:
    if t in (0, 8, 9):
        return 0
    if t in (1, 2, 3, 4):
        return t
    if t == 5:
        return 6
    if t in (6, 7):
        return 8
    if t in (10, 11):
        return 0
    return (t - 12) // 2 if t % 2 == 0 else (t - 13) // 2


def decode_value(data: bytes, off: int, t: int, encoding: str = "UTF-8"):
    n = serial_size(t)
    raw = data[off:off + n]
    if len(raw) < n:
        return None, n
    if t == 0:
        return None, 0
    if t in (1, 2, 3, 4, 5, 6):
        v = int.from_bytes(raw, "big")
        return _twos(v, n * 8), n
    if t == 7:
        return struct.unpack(">d", raw)[0] if n == 8 else None, n
    if t == 8:
        return 0, 0
    if t == 9:
        return 1, 0
    if t % 2 == 0:                      # BLOB
        return {"_blob": len(raw), "hex": raw[:64].hex(" "),
                "text_preview": _printable(raw[:64])}, n
    enc = {"UTF-8": "utf-8", "UTF-16LE": "utf-16-le", "UTF-16BE": "utf-16-be"}.get(
        encoding, "utf-8")
    try:
        return raw.decode(enc, "replace"), n
    except Exception:
        return raw.decode("utf-8", "replace"), n


def _printable(b: bytes) -> str:
    return "".join(chr(c) if 32 <= c < 127 else "." for c in b)


def parse_record(data: bytes, off: int, encoding: str = "UTF-8",
                 limit: int = 2000) -> dict | None:
    """
    فكّ سجل بصيغة SQLite: ترويسة فيها أنواع الأعمدة ثم القيم.

    يُستخدم للسجلات الحيّة وللمحذوفة على السواء — نفس البنية بالضبط.
    """
    if off >= len(data):
        return None
    hdr_size, n = read_varint(data, off)
    if n == 0 or hdr_size < 1 or hdr_size > limit or off + hdr_size > len(data):
        return None
    types: list[int] = []
    p = off + n
    end_hdr = off + hdr_size
    while p < end_hdr:
        t, m = read_varint(data, p)
        if m == 0:
            return None
        types.append(t)
        p += m
    if not types or len(types) > 500:
        return None
    vals = []
    vp = end_hdr
    for t in types:
        v, used = decode_value(data, vp, t, encoding)
        vals.append(v)
        vp += used
        if vp > len(data):
            return None
    return {"serial_types": types, "values": vals, "header_size": hdr_size,
            "total_size": vp - off, "offset": off}


# ===================================================================
#   ترويسة الملف والصفحات
# ===================================================================

def parse_header(data: bytes) -> dict:
    if len(data) < 100 or data[:16] != MAGIC:
        return {"ok": False, "reason": "ليس ملف SQLite (التوقيع غير مطابق)."}
    ps = struct.unpack_from(">H", data, 16)[0]
    page_size = 65536 if ps == 1 else ps
    (wv, rv, reserved) = data[18], data[19], data[20]
    (change_counter, db_pages, free_trunk, free_count, schema_cookie,
     schema_format, cache_size, largest_root, text_enc, user_version,
     inc_vacuum, app_id) = struct.unpack_from(">IIIIIIIIIIII", data, 24)
    version_valid = struct.unpack_from(">I", data, 92)[0]
    sqlite_version = struct.unpack_from(">I", data, 96)[0]
    v = sqlite_version
    return {
        "ok": True,
        "page_size": page_size,
        "write_version": "WAL" if wv == 2 else "rollback journal",
        "read_version": "WAL" if rv == 2 else "legacy",
        "reserved_space": reserved,
        "file_change_counter": change_counter,
        "pages_in_header": db_pages,
        "pages_actual": len(data) // page_size if page_size else 0,
        "freelist_trunk_page": free_trunk,
        "freelist_page_count": free_count,
        "schema_cookie": schema_cookie,
        "schema_format": schema_format,
        "text_encoding": TEXT_ENCODINGS.get(text_enc, f"غير معروف ({text_enc})"),
        "user_version": user_version,
        "incremental_vacuum": bool(inc_vacuum),
        "application_id": app_id,
        "version_valid_for": version_valid,
        "sqlite_version_number": v,
        "sqlite_version": f"{v // 1000000}.{(v // 1000) % 1000}.{v % 1000}" if v else "—",
        "size_mismatch": (db_pages and page_size
                          and db_pages != len(data) // page_size),
    }


def page_bounds(page_no: int, page_size: int) -> tuple[int, int]:
    start = (page_no - 1) * page_size
    return start, start + page_size


def parse_btree_page(data: bytes, page_no: int, page_size: int) -> dict | None:
    """ترويسة صفحة شجرة B وتحديد المساحات غير المخصَّصة والكتل الحرة."""
    start, end = page_bounds(page_no, page_size)
    if start >= len(data):
        return None
    page = data[start:min(end, len(data))]
    hdr_off = 100 if page_no == 1 else 0
    if len(page) < hdr_off + 8:
        return None
    ptype = page[hdr_off]
    if ptype not in PAGE_TYPES:
        return {"page": page_no, "type_byte": ptype, "valid_btree": False,
                "offset": start}
    first_free = struct.unpack_from(">H", page, hdr_off + 1)[0]
    ncells = struct.unpack_from(">H", page, hdr_off + 3)[0]
    content_start = struct.unpack_from(">H", page, hdr_off + 5)[0] or 65536
    frag = page[hdr_off + 7]
    interior = ptype in (2, 5)
    cell_ptr_off = hdr_off + (12 if interior else 8)
    right_ptr = (struct.unpack_from(">I", page, hdr_off + 8)[0] if interior else None)
    cells = []
    for i in range(min(ncells, (len(page) - cell_ptr_off) // 2)):
        cp = struct.unpack_from(">H", page, cell_ptr_off + i * 2)[0]
        if 0 < cp < len(page):
            cells.append(cp)
    unalloc_start = cell_ptr_off + ncells * 2
    unalloc = (unalloc_start, max(unalloc_start, content_start))
    # سلسلة الكتل الحرة داخل الصفحة
    freeblocks = []
    fb = first_free
    guard = 0
    while 0 < fb < len(page) - 3 and guard < 200:
        nxt = struct.unpack_from(">H", page, fb)[0]
        size = struct.unpack_from(">H", page, fb + 2)[0]
        if size < 4 or fb + size > len(page):
            break
        freeblocks.append({"offset": fb, "size": size})
        if nxt == 0 or nxt <= fb:
            break
        fb = nxt
        guard += 1
    return {
        "page": page_no, "offset": start,
        "type_byte": ptype, "valid_btree": True,
        "type": PAGE_TYPES[ptype][0], "type_en": PAGE_TYPES[ptype][1],
        "cell_count": ncells, "cells_parsed": len(cells),
        "cell_offsets": cells,
        "content_area_start": content_start,
        "fragmented_free_bytes": frag,
        "right_most_pointer": right_ptr,
        "unallocated_region": {"start": unalloc[0], "end": unalloc[1],
                               "size": max(0, unalloc[1] - unalloc[0])},
        "freeblocks": freeblocks,
        "freeblock_bytes": sum(f["size"] for f in freeblocks),
    }


def read_table_leaf_cells(data: bytes, page_no: int, page_size: int,
                          encoding: str) -> list[dict]:
    """قراءة السجلات الحيّة من صفحة جدول ورقية (مع تتبّع صفحات الفيض)."""
    info = parse_btree_page(data, page_no, page_size)
    if not info or not info.get("valid_btree") or info["type_byte"] != 13:
        return []
    start, _ = page_bounds(page_no, page_size)
    page = data[start:start + page_size]
    usable = page_size
    out = []
    for cp in info["cell_offsets"]:
        payload_size, n1 = read_varint(page, cp)
        if n1 == 0:
            continue
        rowid, n2 = read_varint(page, cp + n1)
        if n2 == 0:
            continue
        body = cp + n1 + n2
        local_max = usable - 35
        if payload_size <= local_max:
            payload = page[body:body + payload_size]
        else:                                  # حمولة ممتدة على صفحات فيض
            min_local = ((usable - 12) * 32 // 255) - 23
            k = min_local + (payload_size - min_local) % (usable - 4)
            local = k if k <= local_max else min_local
            payload = page[body:body + local]
            ovf_off = body + local
            if ovf_off + 4 <= len(page):
                nxt = struct.unpack_from(">I", page, ovf_off)[0]
                guard = 0
                while nxt and len(payload) < payload_size and guard < 500:
                    ps, _pe = page_bounds(nxt, page_size)
                    if ps + 4 > len(data):
                        break
                    chunk = data[ps + 4:ps + page_size]
                    payload += chunk[:payload_size - len(payload)]
                    nxt = struct.unpack_from(">I", data, ps)[0]
                    guard += 1
        rec = parse_record(payload, 0, encoding)
        if rec:
            rec["rowid"] = rowid
            rec["page"] = page_no
            rec["cell_offset"] = cp
            rec["state"] = "حيّ"
            out.append(rec)
    return out


def walk_table(data: bytes, root: int, page_size: int, encoding: str,
               max_pages: int = 20000) -> list[dict]:
    """المرور على شجرة جدول كاملة من جذرها وجمع كل سجلاته الحيّة."""
    rows: list[dict] = []
    stack = [root]
    seen: set[int] = set()
    while stack and len(seen) < max_pages:
        pg = stack.pop()
        if pg in seen or pg < 1:
            continue
        seen.add(pg)
        info = parse_btree_page(data, pg, page_size)
        if not info or not info.get("valid_btree"):
            continue
        if info["type_byte"] == 13:
            rows.extend(read_table_leaf_cells(data, pg, page_size, encoding))
        elif info["type_byte"] == 5:
            start, _ = page_bounds(pg, page_size)
            page = data[start:start + page_size]
            for cp in info["cell_offsets"]:
                if cp + 4 <= len(page):
                    stack.append(struct.unpack_from(">I", page, cp)[0])
            if info.get("right_most_pointer"):
                stack.append(info["right_most_pointer"])
    return rows


# ===================================================================
#   المخطّط (sqlite_master)
# ===================================================================

COLS_RE = re.compile(r"\((.*)\)\s*$", re.S)


def _split_columns(sql: str) -> list[str]:
    m = COLS_RE.search(sql or "")
    if not m:
        return []
    inner = m.group(1)
    parts, depth, cur = [], 0, ""
    for ch in inner:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    cols = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        head = p.split()[0].strip('`"[]')
        if head.upper() in ("PRIMARY", "UNIQUE", "CHECK", "FOREIGN", "CONSTRAINT"):
            continue
        cols.append(head)
    return cols


def read_schema(data: bytes, page_size: int, encoding: str) -> list[dict]:
    out = []
    for rec in walk_table(data, 1, page_size, encoding):
        v = rec["values"]
        if len(v) < 5:
            continue
        out.append({"type": v[0], "name": v[1], "tbl_name": v[2],
                    "rootpage": v[3], "sql": v[4],
                    "columns": _split_columns(v[4] if isinstance(v[4], str) else "")})
    return out


# ===================================================================
#   استرجاع السجلات المحذوفة
# ===================================================================

def _plausible(rec: dict, min_cols: int, min_text: int,
               strict: bool = False) -> bool:
    """
    مرشّح صرامة ضد القمامة: نقبل السجل فقط إن كان شكله شكل سجل حقيقي.

    بلا هذا المرشّح يُنتج أي ماسح آلاف «السجلات» الوهمية من بايتات عشوائية —
    وهذا أسوأ ما يمكن أن يحدث في تقرير جنائي.
    """
    types = rec["serial_types"]
    vals = rec["values"]
    if len(types) < min_cols:
        return False
    if all(t == 0 for t in types):
        return False
    if any(t in (10, 11) for t in types):            # أنواع محجوزة = قمامة
        return False
    nonnull = sum(1 for v in vals if v is not None)
    if strict:
        # مسار «إعادة البناء» أخطر من القراءة المباشرة لأن بداية السجل مجهولة،
        # فنرفع السقف: لا أعمدة فارغة إطلاقًا، ولا محارف تحكّم، ونصّ أطول.
        if any(v is None for v in vals):
            return False
        if any(isinstance(v, str) and any(ord(c) < 32 for c in v) for v in vals):
            return False
        if sum(len(v) for v in vals if isinstance(v, str)) < 10:
            return False
    # سجل معظم أعمدته NULL = ناتج محاذاة خاطئة على بايتات أصفار.
    # (عمود واحد غير فارغ مقبول في الجداول الصغيرة: المفتاح الأساسي يُخزَّن
    #  NULL في جداول rowid، فسجل «id, نص» قيمته غير الفارغة واحدة فقط.)
    if nonnull < 1 or nonnull / len(vals) < 0.25:
        return False
    texts = [v for v in vals if isinstance(v, str)]
    joined = "".join(texts)
    if len(joined) < min_text:
        return False
    if max((sum(1 for ch in t if ch.isalpha()) for t in texts), default=0) < 4:
        return False
    if "\ufffd" in joined:        # ترميز مكسور ⇒ بداية خاطئة للسجل
        return False
    bad = sum(1 for ch in joined if ord(ch) < 32 and ch not in "\n\r\t")
    if bad:
        return False
    # علامة الإزاحة بايتًا أو أكثر: «كتلة ثنائية» محتواها في الحقيقة نص سليم.
    # السجل الصحيح لا يضع نصًا مقروءًا داخل عمود BLOB، فنرفض القراءة كلها
    # بدل أن نعرض على المحقق سجلًا يبدو حقيقيًا وهو ناتج محاذاة خاطئة.
    for v in vals:
        if isinstance(v, dict) and v.get("_blob"):
            raw = bytes.fromhex(v["hex"].replace(" ", ""))
            # الاقتصاص قد يقطع حرفًا عربيًا متعدّد البايتات، فنجرّب إسقاط
            # حتى 3 بايتات من الطرفين قبل الحكم بأن المحتوى ليس نصًا
            for a in range(4):
                for b in range(4):
                    seg = raw[a:len(raw) - b] if b else raw[a:]
                    if len(seg) < 4:
                        continue
                    try:
                        txt = seg.decode("utf-8")
                    except UnicodeDecodeError:
                        continue
                    if sum(1 for ch in txt if ch.isalpha()) >= 4:
                        return False
    return True


def _score(rec: dict) -> float:
    """
    ترجيح بين قراءات متنافسة لنفس المنطقة.

    عند الحذف يطمس SQLite أول أربعة بايتات من الخلية (يكتب مكانها رأس الكتلة
    الحرة)، فتضيع بداية السجل ويصبح لنفس البايتات أكثر من قراءة ممكنة.
    نختار القراءة التي تُنتج نصًا سليمًا وأعمدة أكثر وتستهلك بايتات أكثر —
    وهذا هو المعيار المعتمد في أدوات الاسترجاع المنشورة.
    """
    vals = rec["values"]
    text_chars = sum(len(v) for v in vals if isinstance(v, str))
    # النص العربي/اللاتيني المقروء أثقل من الأعداد في الترجيح
    readable = sum(1 for v in vals if isinstance(v, str) and v.strip())
    nonnull = sum(1 for v in vals if v is not None)
    blobs = sum(1 for v in vals if isinstance(v, dict))
    return (text_chars * 1.0 + readable * 8 + nonnull * 3
            + rec["total_size"] * 0.3 - blobs * 6)


def _scan_region(blob: bytes, base: int, encoding: str, source: str,
                 page_no: int, min_cols: int, min_text: int,
                 found: list, limit: int, start_limit: int | None = None) -> None:
    """
    مسح منطقة بايتات بحثًا عن سجلات: نجرّب **كل إزاحة ممكنة** ثم نختار
    القراءات الأعلى ترجيحًا وغير المتداخلة، بدل الاكتفاء بأول قراءة تنجح
    (الاكتفاء بالأولى يُنتج سجلات مبتورة أو مُزاحة بايتًا واحدًا).
    """
    cands = []
    # نجرّب بدايات داخل المنطقة فقط، لكن نسمح للسجل بأن يمتد خارجها: الخلية
    # المحذوفة كثيرًا ما تتجاوز حدّ «المساحة غير المخصَّصة» وتتداخل مع منطقة
    # المحتوى الحالية، وقصّها عند الحدّ يُضيّع سجلات سليمة.
    for i in range(min(start_limit if start_limit is not None else len(blob),
                       len(blob))):
        rec = parse_record(blob, i, encoding)
        if not rec or rec["total_size"] < 5:
            continue
        if not _plausible(rec, min_cols, min_text):
            continue
        cands.append((_score(rec), i, rec))
    cands.sort(key=lambda x: (-x[0], x[1]))
    taken: list[tuple[int, int]] = []
    for sc, i, rec in cands:
        if len(found) >= limit:
            break
        a, b = i, i + rec["total_size"]
        if any(a < y and x < b for x, y in taken):      # تداخل مع قراءة أفضل
            continue
        taken.append((a, b))
        rec["offset_in_file"] = base + i
        rec["page"] = page_no
        rec["source"] = source
        rec["state"] = "محذوف (مُستعاد)"
        rec["recovery_score"] = round(sc, 1)
        rec["partial"] = (i > 0 and source.startswith("كتلة حرة"))
        found.append(rec)


def reconstruct_clobbered(region: bytes, base: int, encoding: str,
                         max_start: int = 10) -> list[dict]:
    """
    إعادة بناء سجل فُقدت بدايته — جوهر استرجاع المحذوف في SQLite.

    عند حذف خلية يكتب المحرّك رأس «الكتلة الحرة» (4 بايت: التالي + الحجم) فوق
    أول أربعة بايتات من الخلية، فيضيع: حجم الحمولة، ورقم الصف، وحجم الترويسة،
    وربما أول نوع عمود. لكن **بقية الترويسة والقيم سليمة تمامًا**.

    الحيلة: نفترض أن البايتات من موضع معيّن هي سلسلة «أنواع أعمدة»، ونزيدها
    نوعًا نوعًا، وفي كل خطوة نحسب مجموع أحجام القيم ونتحقق هل ينتهي السجل
    عند نهاية المنطقة بالضبط. التطابق التام قيد قوي جدًا يجعل الحلّ شبه وحيد
    ويمنع القراءات العشوائية.
    """
    out: list[dict] = []
    n = len(region)
    for start in range(0, min(max_start, n)):
        types: list[int] = []
        p = start
        while p < n and len(types) < 64:
            t, m = read_varint(region, p)
            if m == 0 or t in (10, 11) or t > 0x7FFFFF:
                break
            types.append(t)
            p += m
            total = sum(serial_size(x) for x in types)
            if total == 0:
                continue
            for slack in (0, 1, 2, 3):          # قد تبقى بايتات حشو في النهاية
                if p + total + slack == n:
                    vals, vp = [], p
                    ok = True
                    for t2 in types:
                        v, used = decode_value(region, vp, t2, encoding)
                        if isinstance(v, str) and "\ufffd" in v:
                            ok = False
                            break
                        vals.append(v)
                        vp += used
                    if not ok:
                        continue
                    rec = {"serial_types": list(types), "values": vals,
                           "header_size": None, "total_size": n - start,
                           "offset": start, "offset_in_file": base + start,
                           "reconstructed": True,
                           "trailing_slack": slack}
                    if _plausible(rec, 2, 3, strict=True):
                        rec["recovery_score"] = round(_score(rec), 1)
                        out.append(rec)
                    break
    out.sort(key=lambda r: -r["recovery_score"])
    return out[:1]            # أفضل إعادة بناء واحدة لكل منطقة


def deep_reconstruct(blob: bytes, base: int, encoding: str, start_limit: int,
                     min_text: int = 8, max_types: int = 48) -> list[dict]:
    """
    إعادة بناء عميقة لا تشترط انتهاء السجل عند حدّ المنطقة.

    تُستخدم للبقايا التي دُفنت وسط مساحة غير مخصَّصة (بعد إعادة ترتيب الصفحة)،
    حيث لا نعرف أين ينتهي السجل. القيد البديل هنا نوعيّ لا هندسي: نقبل الحلّ
    فقط إن كانت كل القيم النصّية UTF-8 سليمة تمامًا، وبطول نص إجمالي معتبر،
    وبلا أنواع محجوزة — ثم نأخذ الأعلى ترجيحًا وغير المتداخل.
    """
    cands: list[tuple[float, int, dict]] = []
    n = len(blob)
    for s_off in range(min(start_limit, n)):
        types: list[int] = []
        p = s_off
        while p < n and len(types) < max_types:
            t, m = read_varint(blob, p)
            if m == 0 or t in (10, 11) or t > 0x3FFFF:
                break
            types.append(t)
            p += m
            if len(types) < 2:
                continue
            vals, vp, ok = [], p, True
            for t2 in types:
                v, used = decode_value(blob, vp, t2, encoding)
                if isinstance(v, str) and "\ufffd" in v:
                    ok = False
                    break
                vals.append(v)
                vp += used
                if vp > n:
                    ok = False
                    break
            if not ok:
                continue
            rec = {"serial_types": list(types), "values": vals,
                   "header_size": None, "total_size": vp - s_off,
                   "offset": s_off, "offset_in_file": base + s_off,
                   "reconstructed": True}
            if _plausible(rec, 2, min_text, strict=True):
                cands.append((_score(rec), s_off, rec))
    cands.sort(key=lambda x: (-x[0], x[1]))
    out, taken = [], []
    for sc, i, rec in cands:
        a, b = i, i + rec["total_size"]
        if any(a < y and x < b for x, y in taken):
            continue
        taken.append((a, b))
        rec["recovery_score"] = round(sc, 1)
        out.append(rec)
    return out


def recover_deleted(data: bytes, page_size: int, encoding: str,
                    limit: int = 2000, min_cols: int = 2,
                    min_text: int = 3) -> dict:
    """
    مسح المواضع الثلاثة التي يترك فيها SQLite السجلات المحذوفة.

    يُرجع السجلات مع موضعها الدقيق في الملف ومصدرها، ليستطيع خبير مضاد
    التحقق منها بايتًا ببايت.
    """
    found: list[dict] = []
    npages = len(data) // page_size if page_size else 0
    stats = {"pages_scanned": 0, "freeblocks_scanned": 0,
             "unallocated_bytes": 0, "freelist_pages": 0}

    # (1) الكتل الحرة والمساحة غير المخصَّصة داخل كل صفحة
    for pg in range(1, npages + 1):
        info = parse_btree_page(data, pg, page_size)
        if not info or not info.get("valid_btree"):
            continue
        stats["pages_scanned"] += 1
        start, _ = page_bounds(pg, page_size)
        page = data[start:start + page_size]
        ua = info["unallocated_region"]
        if ua["size"] > 4:
            stats["unallocated_bytes"] += ua["size"]
            before_ua = len(found)
            _scan_region(page[ua["start"]:], start + ua["start"],
                         encoding, "مساحة غير مخصَّصة داخل الصفحة", pg,
                         min_cols, min_text, found, limit,
                         start_limit=ua["size"])
            # بقايا مدفونة فقدت بدايتها داخل المساحة غير المخصَّصة
            for rec in deep_reconstruct(page[ua["start"]:], start + ua["start"],
                                        encoding, ua["size"]):
                if len(found) >= limit:
                    break
                if any(abs(f.get("offset_in_file", -1) - rec["offset_in_file"]) < 4
                       for f in found):
                    continue
                rec["page"] = pg
                rec["source"] = ("مساحة غير مخصَّصة داخل الصفحة — "
                                 "أُعيد بناء ترويسة السجل")
                rec["state"] = "محذوف (مُستعاد بإعادة بناء)"
                rec["partial"] = True
                found.append(rec)
                stats["reconstructed"] = stats.get("reconstructed", 0) + 1
        for fb in info["freeblocks"]:
            stats["freeblocks_scanned"] += 1
            region = page[fb["offset"] + 4:fb["offset"] + fb["size"]]
            before = len(found)
            _scan_region(page[fb["offset"] + 4:], start + fb["offset"] + 4,
                         encoding, "كتلة حرة داخل الصفحة (freeblock)", pg,
                         min_cols, min_text, found, limit,
                         start_limit=max(0, fb["size"] - 4))
            if len(found) == before:
                # لم تنجح القراءة المباشرة ⇒ البداية مطموسة، نُعيد بناءها
                for rec in reconstruct_clobbered(region, start + fb["offset"] + 4,
                                                 encoding):
                    rec["page"] = pg
                    rec["source"] = ("كتلة حرة داخل الصفحة (freeblock) — "
                                     "أُعيد بناء ترويسة السجل")
                    rec["state"] = "محذوف (مُستعاد بإعادة بناء)"
                    rec["partial"] = True
                    rec["note"] = ("أول 4 بايتات من الخلية طمسها المحرّك عند الحذف "
                                   "(رقم الصف وحجم الحمولة)، والقيم المعروضة هي "
                                   "الأعمدة الناجية كاملةً.")
                    found.append(rec)
                    stats["reconstructed"] = stats.get("reconstructed", 0) + 1

    # (2) صفحات قائمة الصفحات الحرة — تحتفظ بمحتواها القديم كاملًا
    hdr = parse_header(data)
    trunk = hdr.get("freelist_trunk_page") or 0
    guard = 0
    free_pages: list[int] = []
    while trunk and guard < 10000:
        s, _ = page_bounds(trunk, page_size)
        if s + 8 > len(data):
            break
        nxt, cnt = struct.unpack_from(">II", data, s)
        free_pages.append(trunk)
        for i in range(min(cnt, (page_size - 8) // 4)):
            lp = struct.unpack_from(">I", data, s + 8 + i * 4)[0]
            if 0 < lp <= npages:
                free_pages.append(lp)
        trunk = nxt
        guard += 1
    stats["freelist_pages"] = len(free_pages)
    for pg in free_pages:
        s, _ = page_bounds(pg, page_size)
        _scan_region(data[s + 8:s + page_size], s + 8, encoding,
                     "صفحة في قائمة الصفحات الحرة (freelist)", pg,
                     min_cols, min_text, found, limit)

    # إزالة التكرار بنفس الموضع
    uniq, seen = [], set()
    for r in found:
        k = r["offset_in_file"]
        if k not in seen:
            seen.add(k)
            uniq.append(r)
    return {"records": uniq, "count": len(uniq), "stats": stats}


def carve_text_fragments(data: bytes, page_size: int, encoding: str,
                         live_texts: set[str], min_chars: int = 6,
                         limit: int = 400) -> list[dict]:
    """
    نحت النصوص الباقية في المساحات الحرة والتي لم تُشكّل سجلًا قابلًا لإعادة
    البناء.

    حين يطمس المحرّك ترويسة السجل بما لا يسمح بإعادة بنائها بثقة، يبقى **محتوى
    النص نفسه** سليمًا على القرص. عرضه كـ«شظية نصية» أمانة علمية: نقول إنه
    محتوى محذوف ناجٍ، ولا ندّعي معرفة الصف أو العمود الذي جاء منه.
    """
    frags: list[dict] = []
    npages = len(data) // page_size if page_size else 0
    enc = {"UTF-8": "utf-8", "UTF-16LE": "utf-16-le",
           "UTF-16BE": "utf-16-be"}.get(encoding, "utf-8")
    for pg in range(1, npages + 1):
        info = parse_btree_page(data, pg, page_size)
        if not info or not info.get("valid_btree"):
            continue
        start, _ = page_bounds(pg, page_size)
        page = data[start:start + page_size]
        regions = []
        ua = info["unallocated_region"]
        if ua["size"] > min_chars:
            regions.append((ua["start"], ua["end"], "مساحة غير مخصَّصة"))
        for fb in info["freeblocks"]:
            regions.append((fb["offset"], fb["offset"] + fb["size"],
                            "كتلة حرة (freeblock)"))
        for a, b, label in regions:
            blob = page[a:b]
            for m in re.finditer(
                    rb"(?:[\x20-\x7e]|[\xc2-\xdf][\x80-\xbf]|"
                    rb"[\xe0-\xef][\x80-\xbf]{2}|[\xf0-\xf4][\x80-\xbf]{3}){%d,}"
                    % min_chars, blob):
                try:
                    txt = m.group(0).decode(enc)
                except Exception:
                    continue
                txt = txt.strip()
                if len(txt) < min_chars:
                    continue
                residue = txt
                for lt in live_texts:
                    if len(lt) >= 4 and lt in residue:
                        residue = residue.replace(lt, " ")
                if sum(1 for ch in residue if ch.isalpha()) < 4:
                    continue          # محتواه معروف بالكامل من سجل مُستعاد
                letters = sum(1 for ch in txt if ch.isalpha())
                if letters < max(3, len(txt) // 4):
                    continue
                frags.append({"text": txt[:500], "page": pg,
                              "offset_in_file": start + a + m.start(),
                              "region": label, "length": len(txt)})
                if len(frags) >= limit:
                    return frags
    return frags


# ===================================================================
#   ملفات WAL والـjournal
# ===================================================================

def parse_wal(data: bytes) -> dict:
    """
    ملف -wal يحتفظ بنسخ من الصفحات لم تُدمج بعد في القاعدة.

    وجوده يعني أن القاعدة المضبوطة **ليست الصورة الكاملة**: قد تكون هناك
    تعديلات أحدث (أو نسخ أقدم) موجودة هنا فقط.
    """
    if len(data) < 32:
        return {"ok": False, "reason": "ملف WAL أقصر من ترويسته."}
    magic, fmt, page_size, ckpt, salt1, salt2, c1, c2 = struct.unpack_from(">IIIIIIII", data, 0)
    if magic not in WAL_MAGIC:
        return {"ok": False, "reason": "توقيع WAL غير مطابق."}
    frames = []
    off = 32
    while off + 24 + page_size <= len(data):
        pgno, dbsize, s1, s2, f1, f2 = struct.unpack_from(">IIIIII", data, off)
        frames.append({"page": pgno, "db_size_after_commit": dbsize,
                       "is_commit": dbsize != 0, "offset": off,
                       "salt_matches_header": (s1 == salt1 and s2 == salt2)})
        off += 24 + page_size
    pages = {}
    for f in frames:
        pages.setdefault(f["page"], 0)
        pages[f["page"]] += 1
    return {"ok": True, "format_version": fmt, "page_size": page_size,
            "checkpoint_sequence": ckpt, "salt1": salt1, "salt2": salt2,
            "frame_count": len(frames), "frames": frames[:500],
            "distinct_pages": len(pages),
            "pages_with_multiple_versions": sum(1 for v in pages.values() if v > 1),
            "committed_transactions": sum(1 for f in frames if f["is_commit"]),
            "stale_frames": sum(1 for f in frames if not f["salt_matches_header"]),
            "note": ("كل إطار هنا نسخة من صفحة. تعدّد نسخ نفس الصفحة يعني "
                     "تعديلات متتابعة، والإطارات ذات الملح المختلف بقايا من "
                     "دورة سابقة لم تُمسح — كلاهما مصدر غني للسجلات القديمة.")}


def wal_recover(wal: bytes, db_page_size: int, encoding: str,
                limit: int = 1000) -> list[dict]:
    """استخراج السجلات من صفحات WAL (تشمل نسخًا قديمة اختفت من القاعدة)."""
    info = parse_wal(wal)
    if not info.get("ok"):
        return []
    ps = info["page_size"] or db_page_size
    out: list[dict] = []
    off = 32
    while off + 24 + ps <= len(wal) and len(out) < limit:
        pgno = struct.unpack_from(">I", wal, off)[0]
        page = wal[off + 24:off + 24 + ps]
        tmp: list[dict] = []
        _scan_region(page, off + 24, encoding, f"إطار WAL للصفحة {pgno}",
                     pgno, 2, 3, tmp, limit - len(out))
        for r in tmp:
            r["state"] = "نسخة من WAL"
        out.extend(tmp)
        off += 24 + ps
    return out


def parse_journal(data: bytes) -> dict:
    """ملف -journal (rollback) يحتوي **الصفحات قبل التعديل** — ذهب خالص."""
    if len(data) < 28 or data[:8] != b"\xd9\xd5\x05\xf9\x20\xa1\x63\xd7":
        return {"ok": False, "reason": "ليس ملف journal صالحًا."}
    nrec, nonce, initial_pages, sector, page_size = struct.unpack_from(">IIIII", data, 8)
    return {"ok": True, "record_count_declared": nrec, "nonce": nonce,
            "initial_db_pages": initial_pages, "sector_size": sector,
            "page_size": page_size,
            "note": ("ملف الاستعادة يحفظ الصور **الأصلية** للصفحات قبل الكتابة "
                     "عليها — أي أنه يحتوي حرفيًا الحالة السابقة للقاعدة.")}


# ===================================================================
#   تفسير الطوابع الزمنية الشائعة في قواعد الهواتف
# ===================================================================

def interpret_timestamp(v) -> dict | None:
    """
    التعرّف على صيغ الوقت الشائعة داخل قواعد التطبيقات وتحويلها.

    نعرض كل التفسيرات المعقولة ولا نختار واحدًا تعسّفًا، لأن اختيار الصيغة
    الخطأ يُنتج تاريخًا خاطئًا بسنوات.
    """
    if not isinstance(v, (int, float)) or v <= 0:
        return None
    out = {}

    def add(key, ts, label):
        try:
            dt = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc)
        except (OverflowError, OSError, ValueError):
            return
        if 1990 <= dt.year <= 2100:
            out[key] = {"utc": dt.strftime("%Y-%m-%d %H:%M:%S"), "label": label}

    add("unix_s", v, "ثوانٍ منذ 1970 (Unix)")
    add("unix_ms", v / 1000.0, "أجزاء من الألف منذ 1970 (أندرويد/جافا)")
    add("unix_us", v / 1_000_000.0, "ميكروثانية منذ 1970")
    add("apple_cocoa", v + 978307200, "ثوانٍ منذ 2001 (Apple/Cocoa)")
    add("apple_cocoa_ns", v / 1e9 + 978307200, "نانوثانية منذ 2001 (Apple)")
    add("webkit", v / 1_000_000.0 - 11644473600, "ميكروثانية منذ 1601 (WebKit/Chrome)")
    add("filetime", v / 10_000_000.0 - 11644473600, "ويندوز FILETIME")
    if 2_400_000 < v < 2_500_000:
        add("julian_day", (v - 2440587.5) * 86400, "يوم جولياني (SQLite)")
    return out or None


# ===================================================================
#   نقطة الدخول
# ===================================================================

APP_HINTS = {
    "messages": "رسائل / محادثات", "message": "رسائل / محادثات",
    "chat": "محادثات", "conversation": "محادثات", "whatsapp": "واتساب",
    "contacts": "جهات اتصال", "contact": "جهات اتصال",
    "calls": "سجل مكالمات", "call": "سجل مكالمات", "calllog": "سجل مكالمات",
    "urls": "سجل تصفّح", "history": "سجل تصفّح", "visits": "زيارات مواقع",
    "cookies": "كوكيز", "downloads": "تنزيلات", "bookmarks": "مفضّلة",
    "media": "وسائط", "images": "صور", "location": "مواقع جغرافية",
    "notification": "إشعارات", "account": "حسابات", "sms": "رسائل نصية",
}


def analyze(data: bytes, wal: bytes | None = None, journal: bytes | None = None,
            max_rows_per_table: int = 500, recover: bool = True) -> dict:
    """تحليل كامل: الترويسة، المخطّط، السجلات الحيّة، المحذوفة، وWAL/journal."""
    hdr = parse_header(data)
    if not hdr.get("ok"):
        return {"ok": False, "reason": hdr.get("reason")}
    ps = hdr["page_size"]
    enc = hdr["text_encoding"]
    out: dict = {"ok": True, "header": hdr, "tables": [], "warnings": []}

    if hdr.get("size_mismatch"):
        out["warnings"].append(
            "⚠️ عدد الصفحات في الترويسة يخالف حجم الملف الفعلي — الملف إما مبتور "
            "أو مُستخرج من مساحة غير مخصَّصة أو أُلحقت به بيانات.")

    schema = read_schema(data, ps, enc)
    out["schema_objects"] = len(schema)
    tables = [s for s in schema if s.get("type") == "table" and s.get("rootpage")]
    out["index_count"] = sum(1 for s in schema if s.get("type") == "index")

    total_live = 0
    for t in tables:
        rows = walk_table(data, int(t["rootpage"]), ps, enc)
        total_live += len(rows)
        name = str(t.get("name") or "")
        hint = next((v for k, v in APP_HINTS.items() if k in name.lower()), None)
        sample = []
        for r in rows[:max_rows_per_table]:
            item = {"rowid": r.get("rowid"), "values": r["values"]}
            if t["columns"] and len(t["columns"]) == len(r["values"]):
                item["record"] = dict(zip(t["columns"], r["values"]))
            ts = {}
            for i, v in enumerate(r["values"]):
                got = interpret_timestamp(v)
                if got:
                    col = (t["columns"][i] if t["columns"] and i < len(t["columns"])
                           else f"col{i}")
                    cl = col.lower()
                    if (cl in ("ts", "t", "dt", "tm", "date", "time", "zeit")
                            or any(w in cl for w in
                                   ("time", "date", "stamp", "created", "modified",
                                    "sent", "received", "last", "when", "_at",
                                    "expire", "visit", "epoch"))):
                        ts[col] = got
            if ts:
                item["timestamps"] = ts
            sample.append(item)
        out["tables"].append({
            "name": t.get("name"), "rootpage": t.get("rootpage"),
            "columns": t.get("columns"), "sql": t.get("sql"),
            "live_rows": len(rows), "forensic_hint": hint, "rows": sample,
        })
    out["live_rows_total"] = total_live

    if recover:
        rec = recover_deleted(data, ps, enc)
        out["deleted_records"] = rec["records"][:500]
        out["deleted_count"] = rec["count"]
        out["recovery_stats"] = rec["stats"]
        live_texts = set()
        for t in out["tables"]:
            for row in t["rows"]:
                for v in row["values"]:
                    if isinstance(v, str) and len(v) >= 4:
                        live_texts.add(v)
        for r in rec["records"]:
            for v in r["values"]:
                if isinstance(v, str) and len(v) >= 4:
                    live_texts.add(v)
        frags = carve_text_fragments(data, ps, enc, live_texts)
        out["text_fragments"] = frags
        out["text_fragment_count"] = len(frags)
    else:
        out["deleted_count"] = 0

    if wal:
        out["wal"] = parse_wal(wal)
        wr = wal_recover(wal, ps, enc)
        out["wal_records"] = wr[:300]
        out["wal_record_count"] = len(wr)
    if journal:
        out["journal"] = parse_journal(journal)

    findings = []
    if out.get("deleted_count"):
        findings.append(f"♻️ استُعيد {out['deleted_count']} سجلًا محذوفًا من المساحات "
                        "الحرة داخل القاعدة — محتوى كان يُفترض أنه مُزال.")
    if out.get("text_fragment_count"):
        findings.append(f"🧩 {out['text_fragment_count']} شظية نصية محذوفة ناجية في "
                        "المساحات الحرة (محتوى مؤكد، بلا نسبة مؤكدة لصف بعينه).")
    if hdr["freelist_page_count"]:
        findings.append(f"🗑️ {hdr['freelist_page_count']} صفحة في قائمة الصفحات الحرة "
                        "(أثر حذف كبير أو تفريغ جداول).")
    if out.get("wal", {}).get("ok"):
        w = out["wal"]
        findings.append(f"📄 ملف WAL يحوي {w['frame_count']} إطارًا لـ"
                        f"{w['distinct_pages']} صفحة، منها "
                        f"{w['pages_with_multiple_versions']} صفحة بعدة نسخ — "
                        "القاعدة وحدها لا تعكس الحالة الكاملة.")
    if out.get("journal", {}).get("ok"):
        findings.append("📄 يوجد ملف journal يحمل صور الصفحات **قبل** التعديل.")
    if hdr.get("size_mismatch"):
        findings.append("⚠️ تعارض بين حجم الملف وعدد الصفحات المعلن.")
    out["findings"] = findings
    out["verdict"] = (" · ".join(findings) if findings else
                      f"قاعدة سليمة: {len(tables)} جدولًا و{total_live} سجلًا حيًّا "
                      "بلا آثار حذف قابلة للاسترجاع.")
    return out
