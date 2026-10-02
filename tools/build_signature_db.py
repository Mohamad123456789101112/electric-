"""
توليد قاعدة بصمات الضغط المُرفقة مع المنظومة — **بلا أي قيمة محفوظة يدويًا**.

كل مُدخَل في القاعدة يُنتَج هنا بترميز صورة فعليًا بمكتبة libjpeg المتاحة في
البيئة ثم قراءة بنية الملف الناتج. أي شخص يستطيع إعادة تشغيل هذا السكربت
والحصول على نفس البصمات بالبايت — وهذا شرط قابلية التدقيق.

لا يُضاف هنا أي توقيع منسوب إلى جهة لا نملك عيّنة منها (واتساب، آيفون،
فوتوشوب…)؛ تلك تُضاف من واجهة «تعلّم بصمة» بعد رفع عيّنة مرجعية موثّقة.

التشغيل:  .venv/bin/python tools/build_signature_db.py
"""
from __future__ import annotations

import io
import json
import os
import sys
import time

import numpy as np
from PIL import Image, features

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mirsad.core import jpeg as jpeg_mod            # noqa: E402
from mirsad.core import qtables                     # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "mirsad", "data", "jpeg_signatures.json")

SUBS = {0: "4:4:4", 1: "4:2:2", 2: "4:2:0"}


def sample_image(w=256, h=256):
    """صورة اختبار ثابتة البذرة: تدرّج + نسيج، تُعطي نفس النتيجة عند كل تشغيل."""
    rng = np.random.default_rng(12345)
    y, x = np.mgrid[0:h, 0:w]
    base = (x * 0.6 + y * 0.3) % 256
    tex = rng.normal(0, 18, (h, w))
    arr = np.clip(base + tex, 0, 255).astype(np.uint8)
    rgb = np.dstack([arr, np.roll(arr, 7, axis=1), np.roll(arr, 13, axis=0)])
    return Image.fromarray(rgb)


def encode(im, **kw) -> bytes:
    """
    ترميز إلى ملف مؤقّت لا إلى الذاكرة: مسار BytesIO في Pillow يفشل أحيانًا مع
    خيار optimize بسبب حجم المخزن المؤقت الداخلي، ومسار الملف لا يعاني ذلك.
    """
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        path = f.name
    try:
        im.save(path, "JPEG", **kw)
        with open(path, "rb") as f:
            return f.read()
    finally:
        os.unlink(path)


def main():
    im = sample_image()
    sigs = []
    lib = features.version("jpg") or "غير معروف"
    skipped = []
    for quality in (50, 60, 70, 75, 80, 85, 90, 92, 95, 98):
        for sub, sub_name in SUBS.items():
            for optimize in (False, True):
                try:
                    raw = encode(im, quality=quality, subsampling=sub,
                                 optimize=optimize)
                except OSError as ex:      # قيد في مخزن Pillow المؤقت لبعض التوليفات
                    skipped.append(f"q{quality}/{sub_name}/opt={optimize}: {ex}")
                    continue
                jp = jpeg_mod.parse(raw)
                sig = qtables.compression_signature(jp)
                ana = qtables.analyze_tables(jp)
                name = (f"مُرمِّز libjpeg/IJG — جودة {quality}، تخفيض لون {sub_name}، "
                        f"هوفمان {'مُحسَّن' if optimize else 'قياسي'}")
                sigs.append({
                    "source": name,
                    "family": "libjpeg / IJG",
                    "provenance": (f"مُولَّد محليًا بـPillow فوق libjpeg {lib} "
                                   "عبر tools/build_signature_db.py — قابل لإعادة التوليد"),
                    "notes": ("هذه العائلة يستخدمها عدد كبير من الكاميرات والبرامج، "
                              "فالتطابق معها يحدّد **المُرمِّز وإعداداته** لا الجهاز بعينه."),
                    "qt_signature": sig["qt_signature"],
                    "full_signature": sig["full_signature"],
                    "huffman_signature": sig["huffman_signature"],
                    "structure_signature": sig["structure_signature"],
                    "subsampling": sig["subsampling"],
                    "progressive": sig["progressive"],
                    "huffman_optimized": sig["huffman_optimized"],
                    "app_marker_order": sig["app_marker_order"],
                    "quality": ana["quality_estimate"],
                    "standard_ijg": ana["all_tables_standard_ijg"],
                    "tables": [t.get("values") for t in jp.get("quant_tables", [])],
                    "added_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "origin": "مُرفق مع المنظومة (مُولَّد محليًا)",
                })

    # نسخة تقدمية (لإثبات أن الترميز التقدمي يُنتج توقيعًا بنيويًا مختلفًا)
    for quality in (75, 85):
        jp = jpeg_mod.parse(encode(im, quality=quality, progressive=True,
                                   subsampling=2))
        sig = qtables.compression_signature(jp)
        ana = qtables.analyze_tables(jp)
        sigs.append({
            "source": f"مُرمِّز libjpeg/IJG — تقدمي، جودة {quality}، 4:2:0",
            "family": "libjpeg / IJG (progressive)",
            "provenance": f"مُولَّد محليًا بـPillow فوق libjpeg {lib}",
            "notes": "الترميز التقدمي لا تنتجه الكاميرات عمليًا — مؤشر إعادة ترميز.",
            "qt_signature": sig["qt_signature"],
            "full_signature": sig["full_signature"],
            "huffman_signature": sig["huffman_signature"],
            "structure_signature": sig["structure_signature"],
            "subsampling": sig["subsampling"], "progressive": sig["progressive"],
            "huffman_optimized": sig["huffman_optimized"],
            "app_marker_order": sig["app_marker_order"],
            "quality": ana["quality_estimate"],
            "standard_ijg": ana["all_tables_standard_ijg"],
            "tables": [t.get("values") for t in jp.get("quant_tables", [])],
            "added_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "origin": "مُرفق مع المنظومة (مُولَّد محليًا)",
        })

    db = {
        "schema": 1,
        "description": ("قاعدة بصمات ضغط JPEG. كل مُدخَل مُولَّد بترميز فعلي أو "
                        "مأخوذ من عيّنة مرجعية وثّقها المحقق. لا تُضاف هنا نسبة "
                        "إلى جهة بلا عيّنة."),
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "libjpeg_version": lib,
        "signatures": sigs,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=1)
    print(f"[+] {OUT}: {len(sigs)} توقيعًا (libjpeg {lib})")
    uniq = len({s["full_signature"] for s in sigs})
    print(f"    توقيعات فريدة: {uniq}/{len(sigs)}")
    for sk in skipped:
        print(f"    [-] تُخطّيت توليفة (قيد في المُرمِّز المحلي): {sk}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
