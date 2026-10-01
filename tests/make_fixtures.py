"""
توليد عيّنات اختبار حقيقية (صور بميتاداتا، صور ممسوحة، صور معدّلة، ملفات مدمجة)
للتحقق من صحة محركات مِرصاد. تُولَّد في tests/fixtures/.
"""
from __future__ import annotations

import io
import os
import struct

import numpy as np
from PIL import Image

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
os.makedirs(OUT, exist_ok=True)


def base_image(w=640, h=480, seed=7) -> Image.Image:
    """صورة اصطناعية ذات إحصاء شبيه بالصور الطبيعية: حقول عشوائية منعّمة متعددة المقاييس
    (طيف 1/f) + ضجيج مستشعر خفيف — بلا أنماط دورية تُربك محركات الكشف."""
    from PIL import ImageFilter
    rng = np.random.default_rng(seed)
    acc = np.zeros((h, w, 3))
    for scale, weight in ((4, 1.0), (8, 0.8), (16, 0.6), (32, 0.4), (64, 0.25)):
        small = rng.normal(0, 1, (max(2, h // scale), max(2, w // scale), 3))
        img = Image.fromarray(((small - small.min()) / (np.ptp(small) + 1e-9) * 255).astype(np.uint8))
        img = img.resize((w, h), Image.BICUBIC).filter(ImageFilter.GaussianBlur(1.2))
        acc += np.asarray(img).astype(np.float64) * weight
    acc = (acc - acc.min()) / (np.ptp(acc) + 1e-9)
    grad = np.linspace(0.75, 1.25, h)[:, None, None]
    acc = np.clip(acc * grad * 235 + 10 + rng.normal(0, 2.2, acc.shape), 0, 255)
    return Image.fromarray(acc.astype(np.uint8), "RGB")


ASCII, SHORT, LONG, RATIONAL, BYTE, SRATIONAL = 2, 3, 4, 5, 1, 10
TYPE_SIZE = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 10: 8}


UNDEFINED = 7


def _enc(typ, val, e="<") -> tuple[int, bytes]:
    """ترميز قيمة وسم TIFF وإرجاع (العدد، البايتات)."""
    if typ == ASCII:
        b = val.encode("utf-8") + b"\x00"
        return len(b), b
    if typ in (BYTE, UNDEFINED):
        b = bytes(val) if not isinstance(val, bytes) else val
        return len(b), b
    if typ == SHORT:
        v = val if isinstance(val, (list, tuple)) else [val]
        return len(v), b"".join(struct.pack(e + "H", x) for x in v)
    if typ == LONG:
        v = val if isinstance(val, (list, tuple)) else [val]
        return len(v), b"".join(struct.pack(e + "I", x) for x in v)
    if typ == RATIONAL:
        v = val if isinstance(val[0], (list, tuple)) else [val]
        return len(v), b"".join(struct.pack(e + "II", n, d) for n, d in v)
    if typ == SRATIONAL:
        v = val if isinstance(val[0], (list, tuple)) else [val]
        return len(v), b"".join(struct.pack(e + "ii", n, d) for n, d in v)
    raise ValueError(typ)


def _ifd(entries, base: int, next_ifd: int = 0, e: str = "<", ptr_origin: int = 0) -> bytes:
    """بناء IFD عند الإزاحة المطلقة base؛ المؤشرات تُكتب منسوبة إلى ptr_origin."""
    entries = sorted(entries, key=lambda x: x[0])
    n = len(entries)
    body_off = base + 2 + n * 12 + 4
    out = struct.pack(e + "H", n)
    tail = b""
    for tag, typ, val in entries:
        cnt, raw = _enc(typ, val, e)
        size = len(raw)
        if size <= 4:
            field = raw + b"\x00" * (4 - size)
        else:
            field = struct.pack(e + "I", body_off + len(tail) - ptr_origin)
            tail += raw + (b"\x00" if len(raw) % 2 else b"")
        out += struct.pack(e + "HHI", tag, typ, cnt) + field
    out += struct.pack(e + "I", next_ifd)
    return out + tail


# ------------------------------------------------ كاتب bplist00 (لوسم RunTime)

def _bplist_dict(d: dict) -> bytes:
    """قائمة خصائص ثنائية مبسّطة: قاموس مفاتيحه نصوص ASCII وقيمه أعداد صحيحة."""
    objs = []
    keys = list(d.keys())
    top_refs = (list(range(1, 1 + len(keys))), list(range(1 + len(keys), 1 + 2 * len(keys))))
    out = bytearray(b"bplist00")
    offsets = []

    def add(b: bytes):
        offsets.append(len(out))
        out.extend(b)

    marker = bytes([0xD0 | len(keys)])
    add(marker + bytes(top_refs[0]) + bytes(top_refs[1]))
    for k in keys:
        add(bytes([0x50 | len(k)]) + k.encode("ascii"))
    for k in keys:
        v = int(d[k])
        if v < 0:
            add(b"\x13" + struct.pack(">q", v))
        elif v < 256:
            add(b"\x10" + bytes([v]))
        elif v < 65536:
            add(b"\x11" + struct.pack(">H", v))
        elif v < 2 ** 32:
            add(b"\x12" + struct.pack(">I", v))
        else:
            add(b"\x13" + struct.pack(">Q", v))
    table_off = len(out)
    for o in offsets:
        out.append(o)                      # حجم إزاحة = بايت واحد (ملف صغير)
    out += b"\x00" * 6 + bytes([1, 1]) + struct.pack(">QQQ", len(offsets), 0, table_off)
    return bytes(out)


def build_exif() -> bytes:
    """بناء كتلة EXIF حقيقية (TIFF 6.0) بـ IFD0 + Exif IFD + GPS IFD."""
    tiff_head = b"II*\x00" + struct.pack("<I", 8)
    exif_entries = [
        (0x9000, 7 if False else ASCII, "0231"),
        (0x9003, ASCII, "2024:03:15 14:22:31"),
        (0x9004, ASCII, "2024:03:15 14:22:31"),
        (0x829A, RATIONAL, (1, 250)),
        (0x829D, RATIONAL, (18, 10)),
        (0x8827, SHORT, 100),
        (0x920A, RATIONAL, (27, 1)),
        (0x9209, SHORT, 0),
        (0x9207, SHORT, 5),
        (0xA431, ASCII, "SN-FORENSIC-00912"),
        (0xA434, ASCII, "MIRSAD 27mm f/1.8"),
        (0xA002, LONG, 640),
        (0xA003, LONG, 480),
        (0xA420, ASCII, "7F3A9C21D4E5B6A0"),
    ]
    gps_entries = [
        (0x0000, BYTE, [2, 3, 0, 0]),
        (0x0001, ASCII, "N"),
        (0x0002, RATIONAL, [(30, 1), (2, 1), (2851, 100)]),   # القاهرة 30°02'28.51"N
        (0x0003, ASCII, "E"),
        (0x0004, RATIONAL, [(31, 1), (14, 1), (1584, 100)]),  # 31°14'15.84"E
        (0x0005, BYTE, [0]),
        (0x0006, RATIONAL, (23, 1)),
        (0x0007, RATIONAL, [(12, 1), (22, 1), (31, 1)]),
        (0x001D, ASCII, "2024:03:15"),
        (0x001F, RATIONAL, (5, 1)),
    ]
    ifd0_entries_stub = [
        (0x010F, ASCII, "ARENA-CAM"),
        (0x0110, ASCII, "MIRSAD-X1 Pro"),
        (0x0131, ASCII, "MirsadFirmware 3.2"),
        (0x0132, ASCII, "2024:03:15 14:22:31"),
        (0x013B, ASCII, "محقق الاختبار"),
        (0x8298, ASCII, "(c) Mirsad Test"),
        (0x0112, SHORT, 1),
        (0x011A, RATIONAL, (72, 1)),
        (0x011B, RATIONAL, (72, 1)),
        (0x0128, SHORT, 2),
    ]
    # نحسب الأحجام لتحديد مؤشرات IFD الفرعية
    stub0 = _ifd(ifd0_entries_stub + [(0x8769, LONG, 0), (0x8825, LONG, 0)], 8)
    exif_off = 8 + len(stub0)
    exif_blob = _ifd(exif_entries, exif_off)
    gps_off = exif_off + len(exif_blob)
    gps_blob = _ifd(gps_entries, gps_off)
    ifd0 = _ifd(ifd0_entries_stub + [(0x8769, LONG, exif_off), (0x8825, LONG, gps_off)], 8)
    assert len(ifd0) == len(stub0)
    return b"Exif\x00\x00" + tiff_head + ifd0 + exif_blob + gps_blob



# ===================================================================
#   بناء كتل MakerNote ببنية مطابقة لمواصفات كل مصنّع (ترويسة + مرجع إزاحات)
# ===================================================================

def _mn_canon(off: int) -> bytes:
    """كانون: IFD مباشر بلا ترويسة، المؤشرات منسوبة لبداية TIFF."""
    settings = [0] * 50
    settings[0] = 100            # طول المصفوفة بالبايت
    settings[1] = 0              # MacroMode
    settings[3] = 3              # Quality
    settings[7] = 1              # FocusMode
    settings[16] = 160           # CameraISO
    settings[17] = 5             # MeteringMode
    settings[20] = 3             # ExposureMode
    settings[22] = 61182         # LensType
    settings[23] = 70            # MaxFocalLength
    settings[24] = 24            # MinFocalLength
    settings[25] = 1             # FocalUnits
    settings[26] = 95            # MaxAperture  (2^(95/64) ≈ f/2.8)
    settings[34] = 1             # ImageStabilization
    entries = [
        (0x0001, SHORT, settings),
        (0x0006, ASCII, "Canon EOS 5D Mark IV"),
        (0x0007, ASCII, "Firmware Version 1.3.3"),
        (0x0008, LONG, 1180632074),
        (0x0009, ASCII, "Mohamed Investigator"),
        (0x000C, LONG, 1230405678),
        (0x0010, LONG, 0x80000349),
        (0x0095, ASCII, "EF24-70mm f/2.8L II USM"),
        (0x0096, ASCII, "IS0123456789ABCD"),
    ]
    return _ifd(entries, off, 0, "<", 0)


def _mn_nikon(off: int) -> bytes:
    """نيكون Type 3: ترويسة + TIFF مستقل عند الإزاحة 10 داخل الكتلة."""
    header = b"Nikon\x00\x02\x10\x00\x00"
    inner = off + 10
    entries = [
        (0x0001, UNDEFINED, b"0210"),
        (0x0002, SHORT, [0, 400]),
        (0x0004, ASCII, "FINE  "),
        (0x0005, ASCII, "AUTO        "),
        (0x0007, ASCII, "AF-S  "),
        (0x0083, BYTE, [14]),
        (0x0084, RATIONAL, [(240, 10), (700, 10), (28, 10), (28, 10)]),
        (0x001D, ASCII, "6001234"),
        (0x00A5, LONG, 48250),
        (0x00A7, LONG, 48213),          # ← عدّاد الغالق الحقيقي
        (0x0098, UNDEFINED, bytes((i * 37 + 11) & 0xFF for i in range(60))),
    ]
    body = _ifd(entries, inner + 8, 0, "<", inner)
    return header + b"II*\x00" + struct.pack("<I", 8) + body


def _mn_apple(off: int) -> bytes:
    """آبل: ترويسة Apple iOS + IFD بترتيب Big Endian، المؤشرات منسوبة لبداية الكتلة."""
    header = b"Apple iOS\x00" + b"\x00\x01" + b"MM"
    runtime = _bplist_dict({"flags": 1, "value": 123456789012345,
                            "timescale": 1000000000, "epoch": 0})
    entries = [
        (0x0001, LONG, 14),
        (0x0003, UNDEFINED, runtime),
        (0x0008, SRATIONAL, [(-32, 1000), (-9512, 10000), (-2993, 10000)]),
        (0x000A, LONG, 3),
        (0x000B, ASCII, "4F2C8E1A-9B3D-4C5E-8A7F-1D2E3B4C5A6D"),
        (0x000C, SRATIONAL, [(340, 1000), (1200, 1000)]),
        (0x0011, ASCII, "9A8B7C6D-5E4F-4321-ABCD-0123456789EF"),
        (0x0014, LONG, 10),
        (0x0015, ASCII, "B7F3A1C94E2D5068"),
    ]
    body = _ifd(entries, off + 14, 0, ">", off)
    return header + body


def _mn_sony(off: int) -> bytes:
    """سوني: ترويسة SONY DSC، المؤشرات منسوبة لبداية TIFF، مع كتلة مُعمّاة."""
    header = b"SONY DSC \x00\x00\x00"
    entries = [
        (0x0102, LONG, 2),
        (0x2002, LONG, 0),
        (0x9050, UNDEFINED, bytes((i * 91 + 7) & 0xFF for i in range(96))),
        (0xB001, SHORT, 349),
        (0xB027, LONG, 50),
        (0xB041, LONG, 1),
        (0xB047, SHORT, 3),
        (0xB04A, LONG, 7),
    ]
    return header + _ifd(entries, off + 12, 0, "<", 0)


_MN_BUILDERS = {"canon": _mn_canon, "nikon": _mn_nikon,
                "apple": _mn_apple, "sony": _mn_sony}

_VENDOR_META = {
    "canon": ("Canon", "Canon EOS 5D Mark IV", "Firmware Version 1.3.3"),
    "nikon": ("NIKON CORPORATION", "NIKON D850", "Ver.1.10"),
    "apple": ("Apple", "iPhone 14 Pro", "16.5.1"),
    "sony":  ("SONY", "ILCE-7RM4", "ILCE-7RM4 v1.20"),
}


def build_exif_with_makernote(vendor: str) -> bytes:
    """بناء كتلة EXIF كاملة تحوي MakerNote حقيقي البنية (تمريرتان لضبط المؤشرات)."""
    make, model, soft = _VENDOR_META[vendor]
    marker = b"\xAB\xCD" + vendor.encode().ljust(6, b"\x00")
    probe = _MN_BUILDERS[vendor](0)
    mn_len = len(probe)

    def assemble(mn_bytes: bytes) -> bytes:
        exif_entries = [
            (0x9000, UNDEFINED, b"0231"),
            (0x9003, ASCII, "2024:07:19 18:42:05"),
            (0x9004, ASCII, "2024:07:19 18:42:05"),
            (0x829A, RATIONAL, (1, 400)),
            (0x829D, RATIONAL, (28, 10)),
            (0x8827, SHORT, 400),
            (0x920A, RATIONAL, (50, 1)),
            (0xA002, LONG, 640),
            (0xA003, LONG, 480),
            (0x927C, UNDEFINED, mn_bytes),
        ]
        ifd0_stub = [
            (0x010F, ASCII, make), (0x0110, ASCII, model), (0x0131, ASCII, soft),
            (0x0132, ASCII, "2024:07:19 18:42:05"), (0x0112, SHORT, 1),
        ]
        stub0 = _ifd(ifd0_stub + [(0x8769, LONG, 0)], 8)
        exif_off = 8 + len(stub0)
        exif_blob = _ifd(exif_entries, exif_off, 0, "<", 0)
        ifd0 = _ifd(ifd0_stub + [(0x8769, LONG, exif_off)], 8)
        return b"Exif\x00\x00" + b"II*\x00" + struct.pack("<I", 8) + ifd0 + exif_blob

    # التمريرة الأولى: علامة فريدة لتحديد الموضع النهائي لكتلة MakerNote
    placeholder = marker + b"\x00" * (mn_len - len(marker))
    first = assemble(placeholder)
    pos = first.find(placeholder)
    assert pos > 0, "تعذّر تحديد موضع MakerNote"
    mn_abs = pos - 6          # الإزاحة داخل TIFF (بعد "Exif\0\0")
    real = _MN_BUILDERS[vendor](mn_abs)
    assert len(real) == mn_len
    return assemble(real)


def main() -> list[str]:
    made = []
    img = base_image()

    # 1) صورة أصلية بميتاداتا كاملة + مصغّرة مدمجة
    exif = build_exif()
    p = os.path.join(OUT, "original_with_exif.jpg")
    img.save(p, "JPEG", quality=92, exif=exif)
    made.append(p)

    # 2) نفس الصورة بعد مسح الميتاداتا (محاكاة أداة إزالة الميتاداتا الحقيقية:
    #    إعادة الحفظ دون أي مقاطع APP)
    p2 = os.path.join(OUT, "stripped_metadata.jpg")
    Image.open(p).convert("RGB").save(p2, "JPEG", quality=75)
    made.append(p2)

    # 3) صورة «ممسوحة» لكن مع بقاء شظية EXIF في الذيل (الحالة الواقعية الأشيع:
    #    أداة حذفت المقطع لكن البيانات بقيت في مساحة الملف)
    raw = open(p2, "rb").read()
    p3 = os.path.join(OUT, "wiped_but_recoverable.jpg")
    with open(p3, "wb") as f:
        f.write(raw + exif)   # شظية EXIF كاملة باقية في ذيل الملف
    made.append(p3)

    # 4) صورة مزوّرة بنسخ ولصق داخلي
    a = np.asarray(img).copy()
    a[300:420, 420:580] = a[60:180, 60:220]   # نسخ منطقة ولصقها في مكان آخر
    p4 = os.path.join(OUT, "copy_move_forgery.jpg")
    Image.fromarray(a).save(p4, "JPEG", quality=95)
    made.append(p4)

    # 5) ضغط مزدوج (حُفظت بجودة منخفضة ثم أُعيد حفظها بعالية)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=55)
    buf.seek(0)
    p5 = os.path.join(OUT, "double_compressed.jpg")
    Image.open(buf).save(p5, "JPEG", quality=95)
    made.append(p5)

    # 6) ملف مدمج (ZIP مخبأ بعد نهاية JPEG) — إخفاء كلاسيكي
    import zipfile
    zbuf = io.BytesIO()
    with zipfile.ZipFile(zbuf, "w") as z:
        z.writestr("secret.txt", "رسالة سرية داخل الصورة: الموعد 22:00 — mirsad@example.com")
    p6 = os.path.join(OUT, "appended_zip.jpg")
    with open(p6, "wb") as f:
        f.write(open(p, "rb").read() + zbuf.getvalue())
    made.append(p6)

    # 7) إخفاء LSB حقيقي في PNG
    arr = np.asarray(base_image(320, 240, seed=3)).copy()
    msg = ("SECRET:اجتماع الساعة 9 في الموقع 30.0392,31.2336 — جهة الاتصال +201234567890 ")*30
    bits = np.unpackbits(np.frombuffer(msg.encode("utf-8"), dtype=np.uint8))
    flat = arr.reshape(-1)
    n = min(bits.size, flat.size)
    flat[:n] = (flat[:n] & 0xFE) | bits[:n]
    p7 = os.path.join(OUT, "lsb_stego.png")
    Image.fromarray(flat.reshape(arr.shape)).save(p7)
    made.append(p7)

    # 8) PNG بوسوم نصية وtIME
    from PIL import PngImagePlugin
    meta = PngImagePlugin.PngInfo()
    meta.add_text("Author", "محقق مِرصاد")
    meta.add_text("Software", "Adobe Photoshop 25.0")
    meta.add_text("Comment", "GPS: 30.0444,31.2357 | device: iPhone 15 Pro")
    meta.add_itxt("XML:com.adobe.xmp",
                  '<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
                  '<rdf:Description xmlns:xmp="http://ns.adobe.com/xap/1.0/" xmlns:tiff="http://ns.adobe.com/tiff/1.0/" '
                  'xmp:CreatorTool="Adobe Photoshop 25.0" xmp:CreateDate="2024-01-02T10:11:12" '
                  'tiff:Make="Apple" tiff:Model="iPhone 15 Pro"/></rdf:RDF></x:xmpmeta>')
    p8 = os.path.join(OUT, "png_with_metadata.png")
    base_image(400, 300, seed=11).save(p8, pnginfo=meta)
    made.append(p8)

    # 9) ملف متنكر: PNG بامتداد .txt
    p9 = os.path.join(OUT, "disguised_file.txt")
    with open(p9, "wb") as f:
        f.write(open(p8, "rb").read())
    made.append(p9)

    # 10) PDF بسيط مع ميتاداتا وتحديث تزايدي
    pdf = (b"%PDF-1.7\n"
           b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
           b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
           b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\n"
           b"4 0 obj<</Title(\xd8\xaa\xd9\x82\xd8\xb1\xd9\x8a\xd8\xb1 \xd8\xb3\xd8\xb1\xd9\x8a)"
           b"/Author(Investigator A)/Creator(Microsoft Word)/Producer(Mirsad Test)"
           b"/CreationDate(D:20240115093000+02'00')/ModDate(D:20240320170000+02'00')>>endobj\n"
           b"trailer<</Root 1 0 R/Info 4 0 R/ID[<AABB> <CCDD>]>>\n%%EOF\n"
           b"5 0 obj<</Type/Action/S/JavaScript/JS(app.alert\\(1\\))>>endobj\n"
           b"trailer<</Root 1 0 R/Info 4 0 R/OpenAction 5 0 R>>\n%%EOF\n")
    p10 = os.path.join(OUT, "document_with_js.pdf")
    open(p10, "wb").write(pdf)
    made.append(p10)

    # 11) صور بأربع بنى MakerNote حقيقية (كانون · نيكون · آبل · سوني)
    for vendor in ("canon", "nikon", "apple", "sony"):
        px = base_image(640, 480, seed=hash(vendor) % 1000)
        pv = os.path.join(OUT, f"makernote_{vendor}.jpg")
        px.save(pv, "JPEG", quality=94, exif=build_exif_with_makernote(vendor))
        made.append(pv)

    return made


if __name__ == "__main__":
    for f in main():
        print("[+]", f, os.path.getsize(f), "بايت")
