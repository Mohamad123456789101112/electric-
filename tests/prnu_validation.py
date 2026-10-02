"""
تحقق علمي من محرك PRNU على مرجعية معلومة مسبقًا (ground truth).

لا تتوفر في بيئة التطوير صور ملتقطة بكاميرات حقيقية، فنبني مرجعية بالنموذج
الفيزيائي المعتمد في الأدبيات نفسها (Lukáš–Fridrich–Goljan 2006، المعادلة 1):

        I = I⁰ + I⁰·K + Θ

حيث K نمط PRNU الضربي الفريد للمستشعر، وΘ مجموع الضجيج العشوائي (طلقي + قراءة).
النمط K يُولَّد عشوائيًا **مرة واحدة لكل «مستشعر»** ويبقى ثابتًا في كل صوره —
وهذا بالضبط سلوك المستشعر الحقيقي. ثم تُضغط الصور JPEG كما تخرج من الكاميرا.

ما نقيسه: هل يستعيد المحرك النمط ويميّز المستشعر الصحيح عن مستشعر آخر؟
القرار يُتخذ بإحصائية PCE بعتباتها المنشورة.

التشغيل:  .venv/bin/python tests/prnu_validation.py
"""
from __future__ import annotations

import io
import os
import sys
import time

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mirsad.core import prnu  # noqa: E402

SIZE = 512
N_FLATS = 16


def smooth_scene(rng, h, w, kind="flat"):
    """مشهد واقعي: تدرّج ناعم + نسيج منخفض التردد (تمويه بمتوسط متحرك)."""
    if kind == "flat":
        base = np.full((h, w), 180.0)
        g = np.linspace(-12, 12, w)[None, :] + np.linspace(-8, 8, h)[:, None]
        tex = rng.normal(0, 6, (h, w))
    else:
        base = np.full((h, w), 128.0)
        g = 40 * np.sin(np.linspace(0, 6, w))[None, :] + 30 * np.cos(np.linspace(0, 4, h))[:, None]
        tex = rng.normal(0, 25, (h, w))
    for _ in range(3):                      # تمويه بسيط ليصبح النسيج منخفض التردد
        tex = (np.roll(tex, 1, 0) + np.roll(tex, -1, 0)
               + np.roll(tex, 1, 1) + np.roll(tex, -1, 1) + tex) / 5.0
    return np.clip(base + g + tex, 0, 255)


def capture(scene, K, rng, read_noise=1.2, quality=95):
    """محاكاة التقاط فيزيائي: تطبيق PRNU الضربي + ضجيج + ضغط JPEG حقيقي."""
    I = scene * (1.0 + K) + rng.normal(0, read_noise, scene.shape)
    I = np.clip(I, 0, 255).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(np.dstack([I, I, I])).save(buf, "JPEG", quality=quality)
    return buf.getvalue()


def main():
    rng = np.random.default_rng(20240719)
    # مستشعران مختلفان: نمطان مستقلان إحصائيًا بنفس القوة (σ = 2%)
    K_A = rng.normal(0, 0.02, (SIZE, SIZE))
    K_B = rng.normal(0, 0.02, (SIZE, SIZE))
    print(f"ارتباط النمطين المرجعيين (يجب أن يكون ≈ 0): "
          f"{np.corrcoef(K_A.ravel(), K_B.ravel())[0, 1]:+.5f}")

    t0 = time.time()
    flats_A = [capture(smooth_scene(rng, SIZE, SIZE, "flat"), K_A, rng)
               for _ in range(N_FLATS)]
    fp = prnu.fingerprint_from_images(flats_A, crop=SIZE)
    K_est = fp["fingerprint"].astype(np.float64)
    print(f"بناء البصمة من {fp['n_images']} صورة في {time.time() - t0:.1f}s")

    # دقة الاستعادة: ارتباط البصمة المقدَّرة بالنمط الحقيقي
    Kz = prnu.zero_mean(K_A)
    c = np.corrcoef(K_est.ravel(), Kz.ravel())[0, 1]
    print(f"ارتباط البصمة المستخرجة بالنمط الحقيقي للمستشعر A: {c:+.4f}")
    c_wrong = np.corrcoef(K_est.ravel(), prnu.zero_mean(K_B).ravel())[0, 1]
    print(f"ارتباطها بنمط المستشعر B (يجب ≈ 0): {c_wrong:+.4f}")

    tests = [
        ("صورة طبيعية من المستشعر A (نفس الكاميرا)",
         capture(smooth_scene(rng, SIZE, SIZE, "scene"), K_A, rng), "تطابق"),
        ("صورة طبيعية من المستشعر B (كاميرا أخرى)",
         capture(smooth_scene(rng, SIZE, SIZE, "scene"), K_B, rng), "لا تطابق"),
        ("صورة من A بضغط عالٍ (JPEG 70)",
         capture(smooth_scene(rng, SIZE, SIZE, "scene"), K_A, rng, quality=70), "تطابق"),
        ("صورة من A مع ضجيج قراءة مضاعف",
         capture(smooth_scene(rng, SIZE, SIZE, "scene"), K_A, rng, read_noise=4.0), "تطابق"),
        ("صورة بلا مستشعر (نمط صفري)",
         capture(smooth_scene(rng, SIZE, SIZE, "scene"), np.zeros((SIZE, SIZE)), rng),
         "لا تطابق"),
    ]
    print("\n" + "-" * 78)
    print(f"{'الحالة':48} {'PCE':>10} {'NCC':>9}  الحكم")
    print("-" * 78)
    rows = []
    for label, data, expect in tests:
        r = prnu.match_image(K_est, data)
        rows.append((label, expect, r))
        print(f"{label:48} {r['pce']:10.1f} {r['ncc_at_zero_shift']:+9.4f}  {r['level']}")

    # كشف القصّ: نلتقط صورة أكبر بنفس المستشعر ثم نقصّ نافذة بعيدة عن المركز،
    # فتزيح بصمة المستشعر داخل الإطار ويجب أن تظهر القمة خارج (0,0).
    BIG = SIZE + 160
    K_big = rng.normal(0, 0.02, (BIG, BIG))
    K_big[(BIG - SIZE) // 2:(BIG - SIZE) // 2 + SIZE,
          (BIG - SIZE) // 2:(BIG - SIZE) // 2 + SIZE] = K_A
    big_bytes = capture(smooth_scene(rng, BIG, BIG, "scene"), K_big, rng)
    im = Image.open(io.BytesIO(big_bytes)).crop((0, 0, SIZE + 60, SIZE + 60))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=95)
    rs = prnu.match_image(K_est, buf.getvalue())
    print(f"\nصورة مقصوصة من A (نافذة خارج المركز): PCE(0,0)={rs['pce']:.1f} | "
          f"أفضل إزاحة {rs['best_shift_location']} بقيمة {rs['pce_best_shift']:.1f}")

    # معدّل الإنذار الكاذب: 10 مستشعرات مختلفة تمامًا
    far = []
    for _ in range(10):
        Kx = rng.normal(0, 0.02, (SIZE, SIZE))
        far.append(prnu.match_image(
            K_est, capture(smooth_scene(rng, SIZE, SIZE, "scene"), Kx, rng))["pce"])
    print(f"PCE لعشرة مستشعرات غريبة: أقصى قيمة {max(far):.2f} | "
          f"المتوسط {sum(far) / len(far):.2f}  (العتبة 60)")

    print("-" * 78)
    ok = True
    for label, expect, r in rows:
        hit = r["level"] in ("strong", "probable")
        good = hit if expect == "تطابق" else (not hit)
        ok &= good
        print(("✅" if good else "❌") + f" {label} — المتوقع: {expect}")
    print("\nعتبات القرار:", prnu.PCE_THRESHOLDS)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
