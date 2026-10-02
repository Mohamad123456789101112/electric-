"""
بصمة ضجيج المستشعر PRNU — ربط صورة بكاميرا فيزيائية بعينها.

لماذا هذه الوحدة هي الأقوى قضائيًا في المنظومة كلها؟
لأن كل المحللات الأخرى (EXIF، MakerNote، جداول التكميم) تفحص **ما كتبه البرنامج**،
وهو قابل للتزوير بالكامل. أما PRNU فيفحص **عيبًا فيزيائيًا في السيليكون نفسه**:
اختلافات مجهرية في حساسية كل بكسل ناتجة عن تفاوت سماكة الطبقة أثناء التصنيع.
هذا النمط:
  • فريد لكل مستشعر (حتى بين وحدتين من نفس الطراز ونفس خط الإنتاج)،
  • ثابت طوال عمر المستشعر،
  • ومطبوع ضربيًا في كل صورة يلتقطها،
  • ولا يُزال بالضغط JPEG العادي ولا بتغيير الحجم المعتدل.

المرجع العلمي المنفَّذ هنا حرفيًا:
  [1] J. Lukáš, J. Fridrich, M. Goljan, "Digital Camera Identification from
      Sensor Pattern Noise", IEEE TIFS 1(2), 2006.
  [2] M. Chen, J. Fridrich, M. Goljan, J. Lukáš, "Determining Image Origin and
      Integrity Using Sensor Noise", IEEE TIFS 3(1), 2008  — مقدّر الأرجحية
      العظمى للبصمة K = Σ(W·I)/Σ(I²).
  [3] M. Goljan, J. Fridrich, T. Filler, "Large Scale Test of Sensor Fingerprint
      Camera Identification", SPIE 2009 — إحصائية PCE وعتباتها.
  [4] M. K. Mihçak et al., "Low-complexity image denoising based on statistical
      modeling of wavelet coefficients", IEEE SPL 1999 — مُزيل الضجيج المويجي.

لا توجد أي قيمة مُقدّرة أو مُحاكاة في هذه الوحدة: كل رقم مقيس من بكسلات الصورة.
المرشّحات المويجية تُحسب عدديًا من شرط دوبيشي (تحليل طيفي للعامل نصف النطاقي)
ولا تُنسخ من جدول محفوظ — ويمكن التحقق منها بالاختبارات المرفقة.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import os
import time

import numpy as np

# ===================================================================
#   1) مرشّحات دوبيشي محسوبة عدديًا (لا جداول محفوظة)
# ===================================================================


def daubechies(n_vanishing: int = 8) -> tuple[np.ndarray, np.ndarray]:
    """
    حساب مرشّح دوبيشي ذي n عزوم متلاشية (طوله 2n) بالتحليل الطيفي.

    الطريقة القياسية (Strang & Nguyen):
      P(y) = Σ_{k=0}^{n-1} C(n-1+k, k) · y^k   مع   y = (2 - z - z⁻¹)/4
    نحوّلها لكثير حدود في z، نأخذ جذوره داخل دائرة الوحدة (الطور الأدنى)،
    ونضربها في (1+z)^n ثم نُعاير المجموع إلى √2.

    النتيجة تحقق شروط التعامد تمامًا، وهذا مُختبَر عدديًا في tests.
    """
    n = int(n_vanishing)
    if n < 1:
        raise ValueError("عدد العزوم المتلاشية يجب أن يكون ≥ 1")
    if n == 1:                                   # هار
        h = np.array([1.0, 1.0]) / math.sqrt(2.0)
        return h, _qmf(h)

    # معاملات P(y)
    p = np.array([math.comb(n - 1 + k, k) for k in range(n)], dtype=float)

    # y = (2 - z - z⁻¹)/4  ⇒  نبني كثير الحدود في z بضرب متتالٍ
    # نمثّل كثيرات الحدود بمعاملات np.poly1d في z (درجات موجبة بعد الضرب في z^k)
    poly = np.zeros(1)
    poly[0] = 0.0
    acc = np.zeros(2 * (n - 1) + 1)
    base = np.array([-0.25, 0.5, -0.25])          # يمثّل (2 - z - z⁻¹)/4 مضروبًا في z
    term = np.array([1.0])                        # (…)^0
    for k in range(n):
        padded = np.zeros_like(acc)
        start = (len(acc) - len(term)) // 2
        padded[start:start + len(term)] = term * p[k]
        acc += padded
        term = np.convolve(term, base)

    roots = np.roots(acc)
    inside = roots[np.abs(roots) < 1.0]
    if len(inside) != n - 1:                      # احتياط عددي: اختر الأصغر مقدارًا
        inside = roots[np.argsort(np.abs(roots))][:n - 1]

    h = np.poly(inside).real                      # Π (z - r_i)
    for _ in range(n):                            # × (1+z)^n
        h = np.convolve(h, [1.0, 1.0])
    h = h / h.sum() * math.sqrt(2.0)              # شرط Σh = √2
    h = h / np.linalg.norm(h) * 1.0               # شرط ‖h‖ = 1 (تطبيع نهائي)
    h = h / h.sum() * math.sqrt(2.0)
    return h, _qmf(h)


def _qmf(h: np.ndarray) -> np.ndarray:
    """مرشّح التفاصيل المرافق: g[k] = (-1)^k · h[L-1-k]."""
    g = h[::-1].copy()
    g[1::2] *= -1
    return g


# ===================================================================
#   2) تحويل المويجات المتقطع ثنائي الأبعاد (وضع periodization)
# ===================================================================

def _dwt1(x: np.ndarray, h: np.ndarray, g: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    خطوة تحليل أحادية على المحور الأخير بالتفاف دائري وتخفيض بمعامل 2:

        ca[i] = Σ_k h[k]·x[(2i+k) mod n]
        cd[i] = Σ_k g[k]·x[(2i+k) mod n]

    مصفوفة التحليل المقابلة متعامدة تمامًا (صفوفها إزاحات زوجية لمرشّح معياري)،
    ولذلك تكون إعادة البناء تامة رياضيًا — وهذا مُختبَر عدديًا.
    """
    n = x.shape[-1]
    if n % 2:
        raise ValueError("طول المحور يجب أن يكون زوجيًا في كل مستوى")
    half = n // 2
    base = 2 * np.arange(half)
    ca = np.zeros(x.shape[:-1] + (half,), dtype=float)
    cd = np.zeros_like(ca)
    for k in range(len(h)):
        col = x[..., (base + k) % n]
        ca += h[k] * col
        cd += g[k] * col
    return ca, cd


def _idwt1(ca: np.ndarray, cd: np.ndarray, h: np.ndarray, g: np.ndarray) -> np.ndarray:
    """
    خطوة التركيب المرافقة (منقول مصفوفة التحليل):

        x[m] = Σ_i ca[i]·h[(m−2i) mod n] + Σ_i cd[i]·g[(m−2i) mod n]
    """
    half = ca.shape[-1]
    n = half * 2
    ua = np.zeros(ca.shape[:-1] + (n,), dtype=float)
    ud = np.zeros_like(ua)
    ua[..., ::2] = ca
    ud[..., ::2] = cd
    out = np.zeros_like(ua)
    for k in range(len(h)):
        out += h[k] * np.roll(ua, k, axis=-1) + g[k] * np.roll(ud, k, axis=-1)
    return out


def wavedec2(img: np.ndarray, levels: int, h: np.ndarray, g: np.ndarray) -> list:
    """تحليل مويجي ثنائي الأبعاد: يُعيد [cA_L, (cH,cV,cD)_L, …, (cH,cV,cD)_1]."""
    coeffs = []
    a = img
    for _ in range(levels):
        # صفوف ثم أعمدة
        la, ld = _dwt1(a, h, g)
        laa, lad = _dwt1(la.T, h, g)
        lda, ldd = _dwt1(ld.T, h, g)
        a = laa.T
        coeffs.append((lda.T, lad.T, ldd.T))       # (cH الأفقية, cV الرأسية, cD القطرية)
    coeffs.append(a)
    coeffs.reverse()
    return coeffs


def waverec2(coeffs: list, h: np.ndarray, g: np.ndarray) -> np.ndarray:
    a = coeffs[0]
    for (ch, cv, cd) in coeffs[1:]:
        la = _idwt1(np.ascontiguousarray(a.T), np.ascontiguousarray(cv.T), h, g).T
        ld = _idwt1(np.ascontiguousarray(ch.T), np.ascontiguousarray(cd.T), h, g).T
        a = _idwt1(la, ld, h, g)
    return a


# ===================================================================
#   3) مُزيل الضجيج المويجي (Mihçak) واستخراج البقايا
# ===================================================================

def _box_mean(x2: np.ndarray, w: int) -> np.ndarray:
    """متوسط منزلق على نافذة w×w باستخدام مجموع تراكمي (O(N))."""
    pad = w // 2
    p = np.pad(x2, pad, mode="symmetric")
    cs = p.cumsum(axis=0).cumsum(axis=1)
    cs = np.pad(cs, ((1, 0), (1, 0)))
    h, wd = x2.shape
    s = (cs[w:w + h, w:w + wd] - cs[0:h, w:w + wd]
         - cs[w:w + h, 0:wd] + cs[0:h, 0:wd])
    return s / (w * w)


def _wiener_subband(c: np.ndarray, sigma0_sq: float,
                    windows=(3, 5, 7, 9)) -> np.ndarray:
    """
    تقدير محلي للتباين بأربع نوافذ وأخذ الحد الأدنى (Mihçak)،
    ثم ترشيح واينر لاستخلاص **مكوّن الضجيج** لا الصورة النظيفة.
    """
    c2 = c * c
    var_est = None
    for w in windows:
        v = np.maximum(0.0, _box_mean(c2, w) - sigma0_sq)
        var_est = v if var_est is None else np.minimum(var_est, v)
    return c * (sigma0_sq / (var_est + sigma0_sq))


def noise_residual(gray: np.ndarray, sigma: float = 3.0, levels: int = 4,
                   wavelet_n: int = 8) -> np.ndarray:
    """
    استخراج بقايا الضجيج W = I − F(I) حيث F مُزيل الضجيج المويجي.

    gray: مصفوفة float بقيم 0..255. تُبطَّن أبعادها لمضاعف 2^levels ثم تُقصّ.
    """
    h, g = daubechies(wavelet_n)
    H, W = gray.shape
    m = 1 << levels
    ph, pw = (-H) % m, (-W) % m
    if ph or pw:
        gray = np.pad(gray, ((0, ph), (0, pw)), mode="symmetric")
    coeffs = wavedec2(gray, levels, h, g)
    s2 = float(sigma) ** 2
    out = [np.zeros_like(coeffs[0])]               # إسقاط نطاق التقريب: الضجيج فقط
    for (ch, cv, cd) in coeffs[1:]:
        out.append((_wiener_subband(ch, s2), _wiener_subband(cv, s2),
                    _wiener_subband(cd, s2)))
    res = waverec2(out, h, g)
    return res[:H, :W]


# ===================================================================
#   4) تنقية البصمة من المصنوعات غير الفريدة (NUA)
# ===================================================================

def zero_mean(x: np.ndarray) -> np.ndarray:
    """
    إزالة متوسط كل صف وكل عمود (Zero-Mean) — تحذف مصنوعات CFA وقراءة الصفوف
    المشتركة بين كل كاميرات نفس الطراز، والتي تُنتج تطابقات كاذبة.
    """
    x = x - x.mean(axis=0, keepdims=True)
    x = x - x.mean(axis=1, keepdims=True)
    return x


def wiener_dft(x: np.ndarray, sigma: float | None = None) -> np.ndarray:
    """
    ترشيح واينر في مجال فورييه (Goljan 2009): يقمع القمم الدورية الناتجة عن
    ضغط JPEG الكتلي وعن التداخل، ويُبقي المكوّن العشوائي الفريد للمستشعر.
    """
    F = np.fft.fft2(x)
    mag = np.abs(F)
    if sigma is None:
        sigma = float(np.sqrt(np.mean(mag ** 2)))
    s2 = sigma ** 2
    mag2 = mag ** 2
    # تقدير محلي لطيف القدرة بنافذة 3×3 ثم واينر على المقدار
    local = _box_mean(mag2, 3)
    att = np.maximum(0.0, local - s2) / (local + 1e-12)
    F2 = F * att
    out = np.real(np.fft.ifft2(F2))
    return out


def to_gray(rgb: np.ndarray) -> np.ndarray:
    """تحويل إلى الإضاءة بأوزان ITU-R BT.601 (كما في مرجع Fridrich)."""
    if rgb.ndim == 2:
        return rgb.astype(np.float64)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    return 0.299 * r + 0.587 * g + 0.114 * b


# ===================================================================
#   5) بناء البصمة من عدة صور (مقدّر الأرجحية العظمى)
# ===================================================================

def _center_crop(a: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    H, W = a.shape[:2]
    th, tw = size
    y = max(0, (H - th) // 2)
    x = max(0, (W - tw) // 2)
    return a[y:y + th, x:x + tw]


def _load_pixels(data: bytes) -> np.ndarray | None:
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(data))
        im = im.convert("RGB")
        return np.asarray(im, dtype=np.float64)
    except Exception:
        return None


def fingerprint_from_images(images: list[bytes], crop: int = 1024,
                            sigma: float = 3.0, levels: int = 4,
                            names: list[str] | None = None) -> dict:
    """
    بناء بصمة الكاميرا K بمقدّر الأرجحية العظمى:

        K = Σ_i (W_i · I_i) / Σ_i (I_i²)

    حيث W_i بقايا الضجيج و I_i شدة البكسل. الأفضل علميًا أن تكون الصور
    **مشاهد مسطّحة ساطعة** (سماء/حائط) لأن الإشارة PRNU ضربية في الشدة.
    """
    num = None
    den = None
    used, skipped = [], []
    dims = None
    for i, raw in enumerate(images):
        name = (names[i] if names and i < len(names) else f"image_{i}")
        px = _load_pixels(raw)
        if px is None:
            skipped.append({"name": name, "reason": "تعذّر فك ترميز الصورة"})
            continue
        I = to_gray(px)
        if dims is None:
            th = min(crop, I.shape[0])
            tw = min(crop, I.shape[1])
            dims = (th, tw)
        if I.shape[0] < dims[0] or I.shape[1] < dims[1]:
            skipped.append({"name": name,
                            "reason": f"أبعاد أصغر من المقطع المرجعي {dims}"})
            continue
        I = _center_crop(I, dims)
        sat = float(np.mean(I >= 250.0))
        dark = float(np.mean(I <= 5.0))
        W = noise_residual(I, sigma=sigma, levels=levels)
        n = W * I
        d = I * I
        num = n if num is None else num + n
        den = d if den is None else den + d
        used.append({"name": name, "mean_intensity": round(float(I.mean()), 2),
                     "saturated_ratio": round(sat, 4),
                     "dark_ratio": round(dark, 4),
                     "sha256": hashlib.sha256(raw).hexdigest()})
    if num is None:
        return {"ok": False, "reason": "لم تُقبل أي صورة لبناء البصمة.",
                "skipped": skipped}
    K = num / (den + 1.0)
    K = zero_mean(K)
    K = wiener_dft(K)
    return {"ok": True, "fingerprint": K.astype(np.float32),
            "dims": [int(dims[0]), int(dims[1])],
            "images_used": used, "images_skipped": skipped,
            "n_images": len(used), "sigma": sigma, "levels": levels,
            "quality": _fingerprint_quality(K, len(used))}


def _fingerprint_quality(K: np.ndarray, n: int) -> dict:
    """تقدير جودة البصمة: قوتها وعدد الصور المساهمة وحدود الثقة."""
    energy = float(np.mean(K ** 2))
    note = []
    if n < 5:
        note.append("عدد الصور قليل (<5) — البصمة ضعيفة وقد تُنتج نتائج غير حاسمة؛ "
                    "المرجع العلمي يوصي بـ20–50 صورة مسطّحة.")
    elif n < 20:
        note.append("عدد الصور مقبول لكنه دون التوصية (20–50 صورة) — تُقرأ النتائج بحذر.")
    else:
        note.append("عدد الصور ضمن النطاق الموصى به علميًا.")
    return {"energy": energy, "n_images": n, "notes": note}


# ===================================================================
#   6) إحصائية الكشف: الارتباط المتقاطع المعياري وPCE
# ===================================================================

def crosscorr_all_shifts(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """
    الارتباط الدائري لكل الإزاحات عبر فورييه:
        C = IFFT( FFT(a) · conj(FFT(b)) )
    مع إزالة المتوسط من كلا المصفوفتين (لتصبح النتيجة تناسبية مع NCC).
    """
    a = a - a.mean()
    b = b - b.mean()
    return np.real(np.fft.ifft2(np.fft.fft2(a) * np.conj(np.fft.fft2(b))))


def pce(corr: np.ndarray, squaresize: int = 11,
        location: tuple[int, int] | None = None) -> dict:
    """
    Peak-to-Correlation-Energy (Goljan 2009):

        PCE = C(peak)² / ( (1/(N−|Ω|)) · Σ_{s∉Ω} C(s)² )

    حيث Ω جوار 11×11 حول القمة يُستبعد من حساب طاقة الخلفية.
    القيمة لا تعتمد على حجم الصورة، ولها عتبات معروفة تجريبيًا على ملايين الصور.
    """
    N = corr.size
    if location is None:
        idx = int(np.argmax(np.abs(corr)))
        py, px = np.unravel_index(idx, corr.shape)
    else:
        py, px = int(location[0]) % corr.shape[0], int(location[1]) % corr.shape[1]
    peak = float(corr[py, px])

    r = squaresize // 2
    mask = np.ones(corr.shape, dtype=bool)
    ys = [(py + dy) % corr.shape[0] for dy in range(-r, r + 1)]
    xs = [(px + dx) % corr.shape[1] for dx in range(-r, r + 1)]
    mask[np.ix_(ys, xs)] = False
    energy = float(np.sum(corr[mask] ** 2) / max(1, mask.sum()))
    val = (peak ** 2) / energy if energy > 0 else 0.0
    return {"pce": float(val), "signed_pce": float(math.copysign(val, peak)),
            "peak_value": peak, "peak_location": [int(py), int(px)],
            "peak_is_centered": bool(py == 0 and px == 0),
            "background_energy": energy, "samples": int(N)}


# عتبات مأخوذة من الاختبار واسع النطاق في المرجع [3] (مليون صورة، FAR محسوب)
PCE_THRESHOLDS = {
    "strong": 60.0,     # FAR ≈ 10⁻⁵ — تطابق قوي (القمة عند الإزاحة صفر)
    "probable": 25.0,   # ترجيح يحتاج أدلة مساندة
    "weak": 10.0,       # مؤشر ضعيف لا يصلح وحده
    # عند البحث عن القمة في كل الإزاحات (صورة مقصوصة) نأخذ أقصى قيمة من مئات
    # آلاف المواضع، فترتفع الإحصائية تحت فرض العدم ⇒ عتبة أعلى إلزاميًا.
    "shifted": 150.0,
}


def match_image(fp: np.ndarray, image_bytes: bytes, sigma: float = 3.0,
                levels: int = 4) -> dict:
    """
    مطابقة صورة مجهولة المصدر مع بصمة كاميرا مسجَّلة.

    الإحصائية المستخدمة هي ارتباط W (بقايا الصورة) مع I·K (البصمة مضروبة في
    شدة الصورة) — وهو الشكل الصحيح للنموذج الضربي، لا مجرد ارتباط W مع K.
    """
    px = _load_pixels(image_bytes)
    if px is None:
        return {"ok": False, "reason": "تعذّر فك ترميز الصورة."}
    I_full = to_gray(px)
    th, tw = fp.shape
    if I_full.shape[0] < th or I_full.shape[1] < tw:
        return {"ok": False,
                "reason": (f"أبعاد الصورة {I_full.shape} أصغر من مقطع البصمة "
                           f"{fp.shape} — لا تُقارن مصفوفتان بأحجام مختلفة لأن ذلك "
                           "يُنتج نتيجة بلا معنى.")}
    I = _center_crop(I_full, (th, tw))
    W = noise_residual(I, sigma=sigma, levels=levels)
    W = zero_mean(W)
    X = I * fp.astype(np.float64)
    X = zero_mean(X)
    corr = crosscorr_all_shifts(W, X)
    # الإحصائية الأساسية: القمة مثبّتة عند الإزاحة صفر (الصورة محاذية للبصمة).
    # هذا هو الاستخدام الصحيح لـPCE في تحديد الكاميرا؛ البحث عن القمة في كل
    # الإزاحات يُستخدم فقط لكشف القصّ/الإزاحة، ويضخّم الإحصائية تحت فرض العدم
    # لأنه يأخذ أقصى قيمة من ملايين المواضع.
    p = pce(corr, location=(0, 0))
    p_max = pce(corr)

    # الارتباط المعياري عند الإزاحة صفر (قيمة مألوفة للمقارنة البصرية)
    a = W - W.mean()
    b = X - X.mean()
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    ncc0 = float(np.sum(a * b) / denom) if denom > 0 else 0.0

    val = p["pce"]
    centered = bool(p_max["peak_location"] == [0, 0])
    if val >= PCE_THRESHOLDS["strong"]:
        verdict, level = ("🔴 تطابق قوي: الصورة ملتقطة بهذا المستشعر بعينه "
                          f"(PCE = {val:.1f} ≥ 60).", "strong")
    elif val >= PCE_THRESHOLDS["probable"]:
        verdict, level = (f"🟠 ترجيح تطابق (PCE = {val:.1f}) — يحتاج أدلة مساندة "
                          "أو عينة أكبر لبناء البصمة.", "probable")
    elif val >= PCE_THRESHOLDS["weak"]:
        verdict, level = (f"🟡 مؤشر ضعيف (PCE = {val:.1f}) لا يصلح للإثبات منفردًا.",
                          "weak")
    else:
        verdict, level = (f"🟢 لا تطابق (PCE = {val:.1f}) — لا دليل على أن هذه "
                          "الصورة من هذا المستشعر.", "none")
    if not centered and p_max["pce"] >= PCE_THRESHOLDS["shifted"]:
        loc = p_max["peak_location"]
        dy = loc[0] if loc[0] <= corr.shape[0] // 2 else loc[0] - corr.shape[0]
        dx = loc[1] if loc[1] <= corr.shape[1] // 2 else loc[1] - corr.shape[1]
        if level in ("none", "weak"):
            level = "strong_shifted"
            verdict = (f"🔴 تطابق قوي مع نفس المستشعر لكن بإزاحة مكانية "
                       f"(PCE = {p_max['pce']:.1f} عند الإزاحة {dy},{dx} بدل 0,0). "
                       "هذا يعني أن الصورة من هذه الكاميرا لكنها **مقصوصة أو مزاحة** "
                       "عن إطارها الأصلي — وهو بحد ذاته دليل تعديل.")
        else:
            verdict += (f" ⚠️ توجد أيضًا قمة عند الإزاحة ({dy},{dx}).")
        p_max["shift_dy_dx"] = [int(dy), int(dx)]
    return {"ok": True, "pce": val, "signed_pce": p["signed_pce"],
            "ncc_at_zero_shift": ncc0,
            "pce_best_shift": p_max["pce"],
            "best_shift_location": p_max["peak_location"],
            "detected_shift": p_max.get("shift_dy_dx"),
            "peak_is_centered": centered, "crop_used": [int(th), int(tw)],
            "image_dims": [int(I_full.shape[0]), int(I_full.shape[1])],
            "level": level, "verdict": verdict,
            "thresholds": PCE_THRESHOLDS,
            "method": ("ارتباط بقايا ضجيج الصورة W مع I·K عبر كل الإزاحات (FFT) "
                       "ثم حساب PCE بجوار مستبعد 11×11 — مرجع Goljan 2009.")}


# ===================================================================
#   7) سجل الكاميرات المسجّلة (ربط الصورة بكاميرا «بالاسم»)
# ===================================================================

class CameraRegistry:
    """سجل بصمات دائم على القرص: كل كاميرا باسمها وبصمتها وبيانات بنائها."""

    def __init__(self, root: str):
        self.root = root
        os.makedirs(root, exist_ok=True)

    def _path(self, cid: str) -> str:
        safe = "".join(c for c in cid if c.isalnum() or c in "-_")
        return os.path.join(self.root, f"{safe}.npz")

    def add(self, camera_id: str, name: str, images: list[bytes],
            names: list[str] | None = None, crop: int = 1024,
            notes: str = "") -> dict:
        fp = fingerprint_from_images(images, crop=crop, names=names)
        if not fp.get("ok"):
            return fp
        meta = {"camera_id": camera_id, "name": name, "notes": notes,
                "dims": fp["dims"], "n_images": fp["n_images"],
                "images_used": fp["images_used"],
                "images_skipped": fp["images_skipped"],
                "quality": fp["quality"], "sigma": fp["sigma"],
                "levels": fp["levels"],
                "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        K = fp["fingerprint"]
        meta["fingerprint_sha256"] = hashlib.sha256(K.tobytes()).hexdigest()
        np.savez_compressed(self._path(camera_id), fingerprint=K,
                            meta=json.dumps(meta, ensure_ascii=False))
        return {"ok": True, **meta}

    def get(self, camera_id: str):
        p = self._path(camera_id)
        if not os.path.exists(p):
            return None
        z = np.load(p, allow_pickle=False)
        return np.array(z["fingerprint"]), json.loads(str(z["meta"]))

    def list(self) -> list[dict]:
        out = []
        for f in sorted(os.listdir(self.root)):
            if not f.endswith(".npz"):
                continue
            try:
                z = np.load(os.path.join(self.root, f), allow_pickle=False)
                out.append(json.loads(str(z["meta"])))
            except Exception:
                continue
        return out

    def delete(self, camera_id: str) -> bool:
        p = self._path(camera_id)
        if os.path.exists(p):
            os.remove(p)
            return True
        return False

    def identify(self, image_bytes: bytes) -> dict:
        """مقارنة صورة مع كل الكاميرات المسجّلة وترتيبها حسب PCE."""
        results = []
        for meta in self.list():
            got = self.get(meta["camera_id"])
            if not got:
                continue
            K, m = got
            r = match_image(K, image_bytes)
            r["camera_id"] = m["camera_id"]
            r["camera_name"] = m.get("name")
            r["fingerprint_images"] = m.get("n_images")
            results.append(r)
        ok = [r for r in results if r.get("ok")]
        ok.sort(key=lambda r: r.get("pce", 0), reverse=True)
        best = ok[0] if ok else None
        out = {"cameras_compared": len(results), "results": results}
        if best and best["level"] in ("strong", "probable"):
            out["matched_camera"] = best["camera_name"]
            out["matched_camera_id"] = best["camera_id"]
            out["verdict"] = (f"{best['verdict']} الكاميرا: «{best['camera_name']}».")
        elif results:
            out["verdict"] = ("🟢 لم تتطابق الصورة مع أي كاميرا مسجّلة "
                              f"({len(results)} كاميرا) — أعلى PCE "
                              f"{(best or {}).get('pce', 0):.1f}.")
        else:
            out["verdict"] = ("لا توجد كاميرات مسجّلة بعد — سجّل كاميرا بعدة صور "
                              "مرجعية منها أولًا ليصبح الربط ممكنًا.")
        return out


# ===================================================================
#   8) تحليل صورة منفردة (بلا كاميرا مرجعية)
# ===================================================================

def analyze(data: bytes, registry: CameraRegistry | None = None,
            crop: int = 1024) -> dict:
    """
    ما يمكن قوله عن صورة واحدة بلا كاميرا مرجعية: نستخرج بقايا الضجيج ونقيس
    خصائصها. **لا يمكن تحديد الكاميرا من صورة واحدة بلا مرجع** — نقولها صراحة
    بدل إيهام المستخدم.
    """
    px = _load_pixels(data)
    if px is None:
        return {"ok": False, "reason": "ليست صورة قابلة للفك."}
    I_full = to_gray(px)
    th = min(crop, I_full.shape[0])
    tw = min(crop, I_full.shape[1])
    if th < 128 or tw < 128:
        return {"ok": False,
                "reason": "الصورة أصغر من 128×128 — إحصائية PRNU غير معتمدة لهذا الحجم."}
    I = _center_crop(I_full, (th, tw))
    W = noise_residual(I)
    Wz = zero_mean(W)
    sat = float(np.mean(I >= 250.0))
    dark = float(np.mean(I <= 5.0))
    out = {
        "ok": True,
        "crop_used": [int(th), int(tw)],
        "image_dims": [int(I_full.shape[0]), int(I_full.shape[1])],
        "residual_energy": float(np.mean(W ** 2)),
        "residual_std": float(np.std(W)),
        "residual_energy_after_zero_mean": float(np.mean(Wz ** 2)),
        "mean_intensity": float(I.mean()),
        "saturated_ratio": round(sat, 4),
        "dark_ratio": round(dark, 4),
        "usable_as_reference": bool(sat < 0.05 and dark < 0.2 and 60 < I.mean() < 230),
        "note": ("بقايا الضجيج مستخرجة فعليًا بمُزيل الضجيج المويجي. "
                 "تحديد الكاميرا يتطلب بصمة مرجعية مبنية من صور أخرى لنفس الجهاز."),
    }
    if registry is not None:
        out["identification"] = registry.identify(data)
    return out
