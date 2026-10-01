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


ASCII, SHORT, LONG, RATIONAL, BYTE = 2, 3, 4, 5, 1
TYPE_SIZE = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8}


def _enc(typ, val) -> tuple[int, bytes]:
    """ترميز قيمة وسم TIFF (Little Endian) وإرجاع (العدد، البايتات)."""
    if typ == ASCII:
        b = val.encode("utf-8") + b"\x00"
        return len(b), b
    if typ == BYTE:
        return len(val), bytes(val)
    if typ == SHORT:
        v = val if isinstance(val, (list, tuple)) else [val]
        return len(v), b"".join(struct.pack("<H", x) for x in v)
    if typ == LONG:
        v = val if isinstance(val, (list, tuple)) else [val]
        return len(v), b"".join(struct.pack("<I", x) for x in v)
    if typ == RATIONAL:
        v = val if isinstance(val[0], (list, tuple)) else [val]
        return len(v), b"".join(struct.pack("<II", n, d) for n, d in v)
    raise ValueError(typ)


def _ifd(entries: list[tuple[int, int, object]], base: int, next_ifd: int = 0,
         pointer_fixups: dict | None = None) -> bytes:
    """بناء IFD كامل عند الإزاحة base داخل بنية TIFF."""
    entries = sorted(entries, key=lambda e: e[0])
    n = len(entries)
    body_off = base + 2 + n * 12 + 4
    out = struct.pack("<H", n)
    tail = b""
    for tag, typ, val in entries:
        cnt, raw = _enc(typ, val)
        size = len(raw)
        if size <= 4:
            field = raw + b"\x00" * (4 - size)
        else:
            field = struct.pack("<I", body_off + len(tail))
            tail += raw + (b"\x00" if len(raw) % 2 else b"")
        out += struct.pack("<HHI", tag, typ, cnt) + field
    out += struct.pack("<I", next_ifd)
    return out + tail


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

    return made


if __name__ == "__main__":
    for f in main():
        print("[+]", f, os.path.getsize(f), "بايت")
