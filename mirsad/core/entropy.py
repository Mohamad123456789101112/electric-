"""
تحليل العشوائية (إنتروبيا شانون) + اختبارات إحصائية حقيقية لكشف التشفير/الضغط/الإخفاء.
"""
from __future__ import annotations

import math
from collections import Counter


def shannon(data: bytes) -> float:
    """H = -Σ p·log2(p)  بوحدة بت/بايت (0 = منتظم تمامًا، 8 = عشوائي تمامًا)."""
    if not data:
        return 0.0
    counts = Counter(data)
    n = len(data)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def chi_square_uniform(data: bytes) -> dict:
    """اختبار كاي-تربيع مقابل التوزيع المنتظم: البيانات المشفّرة تقترب من 255 درجة حرية."""
    if not data:
        return {"chi2": 0.0, "dof": 255, "interpretation": "لا توجد بيانات"}
    n = len(data)
    expected = n / 256.0
    counts = Counter(data)
    chi2 = sum((counts.get(b, 0) - expected) ** 2 / expected for b in range(256))
    # القيمة الحرجة عند 0.05 لـ 255 درجة حرية ≈ 293.25
    if chi2 < 293.25:
        interp = "التوزيع منتظم إحصائيًا — متوافق مع بيانات مشفّرة أو مضغوطة عالية الجودة."
    elif chi2 < 1000:
        interp = "انحراف بسيط عن الانتظام — بيانات مضغوطة أو مختلطة."
    else:
        interp = "انحراف كبير عن الانتظام — بيانات ذات بنية (نص/كود/صورة غير مضغوطة)."
    return {"chi2": round(chi2, 2), "dof": 255, "critical_0.05": 293.25, "interpretation": interp}


def monte_carlo_pi(data: bytes) -> dict:
    """تقدير π بطريقة مونت كارلو من البايتات — انحراف صغير = عشوائية عالية (معيار ent)."""
    if len(data) < 6:
        return {}
    inside = total = 0
    for i in range(0, len(data) - 5, 6):
        x = int.from_bytes(data[i:i + 3], "big") / 16777215.0
        y = int.from_bytes(data[i + 3:i + 6], "big") / 16777215.0
        total += 1
        if x * x + y * y <= 1.0:
            inside += 1
    if not total:
        return {}
    pi = 4.0 * inside / total
    err = abs(pi - math.pi) / math.pi * 100
    return {"pi_estimate": round(pi, 6), "error_percent": round(err, 4),
            "interpretation": "عشوائية عالية جدًا" if err < 1 else
                              ("عشوائية متوسطة" if err < 5 else "بيانات غير عشوائية / ذات بنية")}


def serial_correlation(data: bytes) -> float:
    """معامل الارتباط التسلسلي: يقترب من الصفر في البيانات العشوائية."""
    n = len(data)
    if n < 2:
        return 0.0
    t1 = t2 = t3 = 0.0
    prev = data[0]
    for i in range(1, n):
        cur = data[i]
        t1 += prev * cur
        t2 += prev
        t3 += prev * prev
        prev = cur
    t1 += data[-1] * data[0]
    t2 += data[-1]
    t3 += data[-1] * data[-1]
    num = n * t1 - t2 * t2
    den = n * t3 - t2 * t2
    return round(num / den, 6) if den else 0.0


def entropy_map(data: bytes, blocks: int = 256) -> list[dict]:
    """خريطة إنتروبيا على طول الملف — القفزات تكشف مناطق مضمّنة/مشفّرة/مخفية."""
    if not data:
        return []
    size = max(256, math.ceil(len(data) / blocks))
    out = []
    for i in range(0, len(data), size):
        chunk = data[i:i + size]
        out.append({"offset": i, "size": len(chunk), "entropy": round(shannon(chunk), 4)})
        if len(out) >= blocks * 2:
            break
    return out


def anomalies(emap: list[dict], global_h: float) -> list[dict]:
    """كشف المناطق الشاذة: كتل عشوائية داخل ملف منخفض العشوائية (دليل تشفير/حمولة مخفية)."""
    out = []
    for b in emap:
        if b["entropy"] >= 7.5 and global_h < 7.0 and b["size"] >= 1024:
            out.append({"offset": b["offset"], "size": b["size"], "entropy": b["entropy"],
                        "note": "كتلة شبه عشوائية تمامًا داخل ملف منخفض العشوائية — "
                                "مؤشر على بيانات مشفّرة أو مضغوطة مضمّنة."})
        if b["entropy"] <= 0.5 and b["size"] >= 4096:
            out.append({"offset": b["offset"], "size": b["size"], "entropy": b["entropy"],
                        "note": "كتلة شبه ثابتة (حشو/مساحة مُصفّرة) — قد تكون slack space أو مسحًا جزئيًا."})
    return out[:50]


def analyze(data: bytes) -> dict:
    h = shannon(data)
    emap = entropy_map(data)
    verdict = ("مشفّر/مضغوط بقوة" if h > 7.9 else
               "مضغوط" if h > 7.2 else
               "ذو بنية (وسائط/كود)" if h > 5.0 else
               "نص أو بيانات منتظمة")
    return {
        "shannon_bits_per_byte": round(h, 4),
        "normalized": round(h / 8.0, 4),
        "verdict": verdict,
        "chi_square": chi_square_uniform(data[:1_000_000]),
        "monte_carlo": monte_carlo_pi(data[:600_000]),
        "serial_correlation": serial_correlation(data[:1_000_000]),
        "map": emap,
        "anomalies": anomalies(emap, h),
    }
