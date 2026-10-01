"""
تحليل الصور جنائيًا (Image Forensics) — خوارزميات منشورة ومنفّذة فعليًا بـ NumPy:

  • ELA  — Error Level Analysis (Krawetz 2007): إعادة الحفظ بجودة معلومة وقياس فرق الخطأ.
  • JPEG Ghosts (Farid 2009): البحث عن مناطق ذات تاريخ ضغط مختلف عن بقية الصورة.
  • Double-JPEG detection: تحليل مدرج معاملات DCT والبحث عن دورية (أثر الضغط المزدوج).
  • Noise / PRNU residual: فصل ضجيج المستشعر وكشف المناطق ذات الضجيج الشاذ (لصق).
  • Copy-Move (Fridrich 2003): مطابقة كتل 16×16 عبر DCT منخفض التردد + تصويت متجه الإزاحة.
  • LSB steganalysis: خريطة البت الأدنى + اختبار كاي-تربيع (Westfeld & Pfitzmann 1999)
    + تحليل RS (Fridrich 2001) لتقدير نسبة الحمولة المخفية.
  • تحليل المدرج التكراري والقصّ (clipping) وتكرار قيم البكسل (أثر معالجة/تعديل تباين).
"""
from __future__ import annotations

import io
import math
import os

import numpy as np
from PIL import Image, ImageChops, ImageFilter

Image.MAX_IMAGE_PIXELS = 300_000_000


def load(data: bytes) -> Image.Image | None:
    try:
        im = Image.open(io.BytesIO(data))
        im.load()
        return im
    except Exception:
        return None


def _save(im: Image.Image, outdir: str, name: str) -> str:
    os.makedirs(outdir, exist_ok=True)
    p = os.path.join(outdir, name)
    im.save(p)
    return name


def _norm_to_img(arr: np.ndarray, cmap: bool = False) -> Image.Image:
    a = arr.astype(np.float64)
    lo, hi = float(np.nanmin(a)), float(np.nanmax(a))
    if hi - lo < 1e-9:
        a = np.zeros_like(a)
    else:
        a = (a - lo) / (hi - lo)
    v = (a * 255).astype(np.uint8)
    if not cmap:
        return Image.fromarray(v, "L")
    # خريطة حرارية (أزرق→أحمر) لإبراز الشذوذ
    r = np.clip(1.5 - np.abs(4 * (a - 0.75)), 0, 1)
    g = np.clip(1.5 - np.abs(4 * (a - 0.5)), 0, 1)
    b = np.clip(1.5 - np.abs(4 * (a - 0.25)), 0, 1)
    rgb = (np.dstack([r, g, b]) * 255).astype(np.uint8)
    return Image.fromarray(rgb, "RGB")


# ------------------------------------------------------------------------ ELA

def ela(im: Image.Image, outdir: str, quality: int = 90, scale_cap: int = 2000) -> dict:
    rgb = im.convert("RGB")
    if max(rgb.size) > scale_cap:
        rgb = rgb.copy()
        rgb.thumbnail((scale_cap, scale_cap), Image.LANCZOS)
    buf = io.BytesIO()
    rgb.save(buf, "JPEG", quality=quality)
    buf.seek(0)
    resaved = Image.open(buf)
    diff = ImageChops.difference(rgb, resaved)
    arr = np.asarray(diff).astype(np.float32)
    mag = arr.max(axis=2)
    mx = float(mag.max()) or 1.0
    boost = np.clip(mag * (255.0 / mx), 0, 255).astype(np.uint8)
    img = Image.fromarray(np.dstack([boost] * 3), "RGB")
    fn = _save(img, outdir, f"ela_q{quality}.png")

    # إحصاء مناطق الشذوذ: كتل 32×32 بمتوسط خطأ أعلى بكثير من الوسيط العام
    bs = 32
    h, w = mag.shape
    bh, bw = h // bs, w // bs
    regions = []
    if bh and bw:
        blocks = mag[:bh * bs, :bw * bs].reshape(bh, bs, bw, bs).mean(axis=(1, 3))
        med = float(np.median(blocks))
        mad = float(np.median(np.abs(blocks - med))) or 1e-6
        z = (blocks - med) / (1.4826 * mad)
        ys, xs = np.where(z > 6)
        order = np.argsort(-z[ys, xs])[:40]
        for k in order:
            y, x = int(ys[k]), int(xs[k])
            regions.append({"x": x * bs, "y": y * bs, "w": bs, "h": bs,
                            "z_score": round(float(z[y, x]), 2)})
    return {
        "image": fn, "quality_used": quality,
        "mean_error": round(float(mag.mean()), 3),
        "max_error": round(mx, 2),
        "suspect_regions": regions,
        "interpretation": (
            "مناطق ذات مستوى خطأ أعلى بشكل حاد من محيطها قد تدل على لصق/تعديل محلي، "
            "لكن الحواف والنصوص والمناطق عالية التباين تعطي خطأً مرتفعًا طبيعيًا. "
            "تُقرأ ELA دائمًا مع بقية الأدلة ولا تُعتمد وحدها (معيار مقبول قضائيًا: التأييد المتبادل)."
        ),
        "regions_found": len(regions),
    }


def jpeg_ghosts(im: Image.Image, outdir: str, qualities=(55, 65, 75, 85, 95)) -> dict:
    """بحث عن «أشباح JPEG»: مناطق أصلها ضُغط بجودة مختلفة."""
    rgb = im.convert("RGB")
    if max(rgb.size) > 1200:
        rgb = rgb.copy()
        rgb.thumbnail((1200, 1200), Image.LANCZOS)
    base = np.asarray(rgb).astype(np.float32)
    out = []
    files = []
    for q in qualities:
        buf = io.BytesIO()
        rgb.save(buf, "JPEG", quality=q)
        buf.seek(0)
        a = np.asarray(Image.open(buf).convert("RGB")).astype(np.float32)
        d = ((base - a) ** 2).mean(axis=2)
        # تنعيم للحصول على خريطة مناطقية
        k = 16
        h, w = d.shape
        hh, ww = h // k, w // k
        if not hh or not ww:
            continue
        m = d[:hh * k, :ww * k].reshape(hh, k, ww, k).mean(axis=(1, 3))
        files.append(_save(_norm_to_img(-m, cmap=True).resize(rgb.size, Image.NEAREST),
                           outdir, f"ghost_q{q}.png"))
        out.append({"quality": q, "mean_sq_error": round(float(m.mean()), 4),
                    "min_region_error": round(float(m.min()), 4),
                    "spatial_variation": round(float(m.std()), 4)})
    best = min(out, key=lambda x: x["mean_sq_error"]) if out else None
    return {"per_quality": out, "images": files,
            "estimated_last_save_quality": best["quality"] if best else None,
            "interpretation": "أقل خطأ عند جودة ما ⇒ غالبًا هي جودة آخر حفظ. "
                              "وجود منطقة محدودة يقل خطؤها عند جودة مختلفة عن بقية الصورة = مؤشر تركيب."}


def dct_double_compression(data: bytes, quant_table: list[int] | None = None) -> dict:
    """كشف الضغط المزدوج عبر تحليل مدرج معاملات DCT للقناة الضوئية.
    الأثر العلمي: الضغط المزدوج يُحدث قمماً/فجوات دورية في مدرج المعاملات."""
    try:
        import PIL.Image as PImage
        im = PImage.open(io.BytesIO(data))
        if im.format != "JPEG":
            return {"applicable": False, "reason": "التحليل ينطبق على JPEG فقط."}
        y = np.asarray(im.convert("L")).astype(np.float32) - 128.0
    except Exception as e:
        return {"applicable": False, "reason": str(e)}
    h, w = y.shape
    h8, w8 = h // 8, w // 8
    if h8 < 4 or w8 < 4:
        return {"applicable": False, "reason": "الصورة صغيرة جدًا."}
    blocks = y[:h8 * 8, :w8 * 8].reshape(h8, 8, w8, 8).transpose(0, 2, 1, 3).reshape(-1, 8, 8)
    if blocks.shape[0] > 20000:
        idx = np.linspace(0, blocks.shape[0] - 1, 20000).astype(int)
        blocks = blocks[idx]
    # DCT-II ثنائي الأبعاد عبر مصفوفة الأساس
    n = 8
    c = np.array([[math.sqrt(1 / n) if u == 0 else math.sqrt(2 / n) for _ in range(n)]
                  for u in range(n)])
    k = np.array([[math.cos((2 * x + 1) * u * math.pi / (2 * n)) for x in range(n)]
                  for u in range(n)])
    basis = c * k
    coef = np.einsum("ux,bxy,vy->buv", basis, blocks, basis)
    q = np.asarray(quant_table, dtype=np.float64).reshape(8, 8) if quant_table and len(quant_table) == 64 \
        else np.ones((8, 8))
    results = []
    flags = 0
    for (u, v) in ((0, 1), (1, 0), (1, 1), (0, 2), (2, 0), (1, 2), (2, 1)):
        vals = np.round(coef[:, u, v] / q[u, v]).astype(int)   # معاملات مُكمَّمة تقريبًا
        vals = vals[np.abs(vals) <= 50]
        if vals.size < 300:
            continue
        hist = np.bincount(vals + 50, minlength=101).astype(float)
        if hist.sum() < 300:
            continue
        spec = np.abs(np.fft.rfft(hist - hist.mean()))
        if spec.size < 8:
            continue
        dc = spec[2:]                     # تجاهل المركّبة شبه الثابتة
        if dc.size == 0:
            continue
        pi = int(np.argmax(dc))
        strength = float(dc[pi] / (dc.mean() + 1e-9))
        periodic = bool(strength > 5.0)
        if periodic:
            flags += 1
        results.append({"coefficient": f"({u},{v})", "peak_bin": pi + 2,
                        "periodicity_strength": round(strength, 2), "periodic": periodic})
    verdict = ("مؤشرات قوية على ضغط مزدوج (الصورة حُفظت كـ JPEG أكثر من مرة — أي عُولجت بعد الالتقاط)"
               if flags >= 4 else
               "مؤشرات محتملة على ضغط مزدوج — تحتاج تأييدًا" if flags >= 2 else
               "لا توجد دورية واضحة — متوافق مع ضغط واحد")
    return {"applicable": True, "coefficients": results, "periodic_flags": flags,
            "verdict": verdict,
            "method": "تحليل فورييه لمدرج معاملات DCT (Popescu & Farid, 2004)"}


def noise_analysis(im: Image.Image, outdir: str) -> dict:
    rgb = im.convert("RGB")
    if max(rgb.size) > 1600:
        rgb = rgb.copy()
        rgb.thumbnail((1600, 1600), Image.LANCZOS)
    g = np.asarray(rgb.convert("L")).astype(np.float32)
    med = np.asarray(rgb.convert("L").filter(ImageFilter.MedianFilter(3))).astype(np.float32)
    resid = g - med
    fn = _save(_norm_to_img(np.abs(resid)), outdir, "noise_residual.png")
    k = 32
    h, w = resid.shape
    hh, ww = h // k, w // k
    regions = []
    uniformity = None
    if hh and ww:
        local = resid[:hh * k, :ww * k].reshape(hh, k, ww, k).std(axis=(1, 3))
        med_l = float(np.median(local))
        mad = float(np.median(np.abs(local - med_l))) or 1e-6
        z = (local - med_l) / (1.4826 * mad)
        uniformity = round(float(local.std() / (local.mean() + 1e-9)), 4)
        ys, xs = np.where(np.abs(z) > 6)
        for i in np.argsort(-np.abs(z[ys, xs]))[:40]:
            y, x = int(ys[i]), int(xs[i])
            regions.append({"x": x * k, "y": y * k, "w": k, "h": k,
                            "z_score": round(float(z[y, x]), 2),
                            "type": "ضجيج أعلى من المحيط" if z[y, x] > 0 else "ضجيج أقل (تنعيم/لصق)"})
        fn2 = _save(_norm_to_img(local, cmap=True).resize(rgb.size, Image.NEAREST),
                    outdir, "noise_map.png")
    else:
        fn2 = None
    return {"residual_image": fn, "noise_map": fn2,
            "global_noise_sigma": round(float(resid.std()), 4),
            "noise_uniformity_index": uniformity,
            "anomalous_regions": regions,
            "interpretation": "المستشعر الواحد يُنتج ضجيجًا متجانسًا إحصائيًا. مناطق ذات ضجيج "
                              "مختلف جوهريًا عن محيطها تُرجّح إدراج محتوى من مصدر آخر أو تنعيمًا موضعيًا."}


def copy_move(im: Image.Image, outdir: str, block: int = 16, max_dim: int = 900) -> dict:
    """كشف النسخ-واللصق داخل الصورة نفسها (Fridrich et al., 2003)."""
    g = im.convert("L")
    scale = 1.0
    if max(g.size) > max_dim:
        scale = max_dim / max(g.size)
        g = g.resize((max(8, int(g.width * scale)), max(8, int(g.height * scale))), Image.LANCZOS)
    a = np.asarray(g).astype(np.float32)
    h, w = a.shape
    if h < block * 2 or w < block * 2:
        return {"applicable": False, "reason": "الصورة صغيرة جدًا للتحليل."}
    step = 2
    n = 8
    c = np.array([[math.sqrt(1 / n) if u == 0 else math.sqrt(2 / n) for _ in range(n)] for u in range(n)])
    kk = np.array([[math.cos((2 * x + 1) * u * math.pi / (2 * n)) for x in range(n)] for u in range(n)])
    basis = c * kk
    feats = []
    coords = []
    skipped_flat = 0
    for y in range(0, h - block + 1, step):
        for x in range(0, w - block + 1, step):
            b = a[y:y + block, x:x + block]
            if b.std() < 10.0:          # تجاهل الكتل المسطّحة (سماء/خلفية) لمنع الإنذارات الكاذبة
                skipped_flat += 1
                continue
            small = b.reshape(8, 2, 8, 2).mean(axis=(1, 3))
            d = basis @ (small - 128.0) @ basis.T
            feats.append(np.round(d[:4, :4].flatten() / 16.0))
            coords.append((x, y))
    if len(feats) < 40:
        return {"applicable": False, "reason": "لا توجد كتل كافية ذات تباين للتحليل.",
                "flat_blocks_skipped": skipped_flat}
    F = np.asarray(feats)
    C = np.asarray(coords)
    order = np.lexsort(tuple(F[:, i] for i in range(F.shape[1] - 1, -1, -1)))
    Fs, Cs = F[order], C[order]
    shifts: dict[tuple[int, int], int] = {}
    pairs: dict[tuple[int, int], list] = {}
    for i in range(len(Fs) - 1):
        for j in (i + 1, i + 2, i + 3):
            if j >= len(Fs):
                break
            if not np.array_equal(Fs[i], Fs[j]):
                continue
            dx, dy = int(Cs[j][0] - Cs[i][0]), int(Cs[j][1] - Cs[i][1])
            if abs(dx) + abs(dy) < block:
                continue
            # تحقق فعلي من تطابق البكسلات (منع المطابقات العرضية)
            b1 = a[int(Cs[i][1]):int(Cs[i][1]) + block, int(Cs[i][0]):int(Cs[i][0]) + block]
            b2 = a[int(Cs[j][1]):int(Cs[j][1]) + block, int(Cs[j][0]):int(Cs[j][0]) + block]
            if np.abs(b1 - b2).mean() > 6.0:
                continue
            key = (dx, dy) if (dy, dx) > (0, 0) else (-dx, -dy)
            shifts[key] = shifts.get(key, 0) + 1
            pairs.setdefault(key, []).append((int(Cs[i][0]), int(Cs[i][1]), int(Cs[j][0]), int(Cs[j][1])))
    if not shifts:
        return {"applicable": True, "detected": False, "matched_regions": [],
                "interpretation": "لم تُرصد كتل متطابقة بإزاحة ثابتة — لا دليل على نسخ ولصق داخلي."}
    top = sorted(shifts.items(), key=lambda kv: -kv[1])[:5]
    thresh = max(20, int(0.004 * len(feats)))

    def _density(key) -> float:
        """تركيز التطابقات مكانيًا: التزوير يُنتج منطقة مُدمجة، بينما النسيج المتكرر يُنتج تشتتًا."""
        pts = pairs[key]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        bw = (max(xs) - min(xs)) // step + 1
        bh_ = (max(ys) - min(ys)) // step + 1
        return len(pts) / max(1, bw * bh_)

    stats = []
    for k, cnt in top:
        stats.append({"shift": list(k), "matching_blocks": cnt,
                      "spatial_density": round(_density(k), 4)})
    best = max(stats, key=lambda s: (s["matching_blocks"] >= thresh, s["spatial_density"]))
    detected = best["matching_blocks"] >= thresh and best["spatial_density"] >= 0.10
    regions = []
    if detected:
        key = tuple(best["shift"])
        for (x1, y1, x2, y2) in pairs[key][:150]:
            regions.append({"x1": int(x1 / scale), "y1": int(y1 / scale),
                            "x2": int(x2 / scale), "y2": int(y2 / scale),
                            "size": int(block / scale), "shift": best["shift"]})
    return {"applicable": True, "detected": detected,
            "top_shift_vectors": stats,
            "threshold": thresh, "density_threshold": 0.10,
            "flat_blocks_skipped": skipped_flat,
            "matched_regions": regions[:200],
            "analysis_scale": round(scale, 3),
            "interpretation": ("⚠️ وُجد عدد كبير من الكتل المتطابقة بإزاحة ثابتة — "
                               "مؤشر قوي على نسخ منطقة ولصقها داخل نفس الصورة (استنساخ/إخفاء كائن)."
                               if detected else
                               "التطابقات المرصودة قليلة ومبعثرة — ضمن الضجيج الطبيعي (مناطق متجانسة كالسماء)."),
            "method": "مطابقة كتل مرتبة معجميًا على معاملات DCT منخفضة التردد + تصويت متجه الإزاحة"}


# ------------------------------------------------------------- Steganalysis

def lsb_analysis(im: Image.Image, outdir: str) -> dict:
    rgb = im.convert("RGB")
    a = np.asarray(rgb)
    planes = {}
    for ci, cname in enumerate(("R", "G", "B")):
        bit = (a[:, :, ci] & 1) * 255
        planes[cname] = _save(Image.fromarray(bit.astype(np.uint8), "L"), outdir, f"lsb_{cname}.png")
    # نسبة بتات 1 في LSB (يجب أن تقترب من 0.5 عشوائيًا؛ النص المخفي غير المشفّر ينحرف)
    ratios = {c: round(float(((a[:, :, i] & 1).mean())), 5) for i, c in enumerate("RGB")}
    chi = chi_square_lsb(a)
    # RS يُطبَّق على كل قناة لونية خامًا (التحويل لتدرج رمادي يُتلف البت الأدنى)
    per_channel = {c: rs_analysis(a[:, :, i]) for i, c in enumerate("RGB")}
    rs = max(per_channel.values(),
             key=lambda d: d.get("estimated_payload_ratio", 0) if d.get("applicable") else -1)
    rs = dict(rs)
    rs["per_channel_payload"] = {c: v.get("estimated_payload_ratio") for c, v in per_channel.items()}
    # إنتروبيا مستوى LSB
    lsb_bits = np.unpackbits((a & 1).astype(np.uint8).flatten()[:200000])
    ones = float(lsb_bits.mean()) if lsb_bits.size else 0.0
    verdict = []
    if chi["suspicious_fraction"] > 0.05:
        verdict.append(f"⚠️ اختبار كاي-تربيع يشير إلى احتمال إخفاء LSB في {chi['suspicious_fraction']*100:.1f}% "
                       "من الصورة (توزيع أزواج القيم شاذ).")
    if rs.get("estimated_payload_ratio", 0) > 0.15:
        verdict.append(f"⚠️ تحليل RS يقدّر حمولة مخفية ≈ {rs['estimated_payload_ratio']*100:.1f}% من سعة LSB "
                       "(أرضية الضجيج الطبيعية أقل من 10%).")
    if not verdict:
        verdict.append("لا توجد مؤشرات إحصائية دالة على إخفاء LSB.")
    return {"bit_plane_images": planes, "lsb_mean_per_channel": ratios,
            "chi_square": chi, "rs_analysis": rs, "verdict": verdict,
            "note": "اعرض مستويات البت: النصوص/الأشكال الظاهرة فيها دليل مباشر على إخفاء بيانات."}


def chi_square_lsb(a: np.ndarray, blocks: int = 64) -> dict:
    """اختبار كاي-تربيع لأزواج القيم (2k, 2k+1) — Westfeld & Pfitzmann.

    للحد من الإنذارات الكاذبة في الصور الطبيعية الناعمة، يُقارَن تسوية الأزواج
    الزوجية (2k,2k+1) بتسوية الأزواج المُزاحة (2k+1,2k+2): الإخفاء في البت الأدنى
    يُسوّي الأولى فقط، بينما نعومة الصورة الطبيعية تُسوّي الاثنتين معًا.
    """
    g = a[:, :, 0].astype(np.int32).flatten() if a.ndim == 3 else a.flatten()
    n = g.size
    if n < 1024:
        return {"suspicious_fraction": 0.0, "blocks_tested": 0}
    seg = max(4096, n // blocks)
    susp = 0
    total = 0
    pvals = []
    ratios = []
    for s in range(0, n - seg + 1, seg):
        chunk = g[s:s + seg]
        hist = np.bincount(chunk, minlength=256).astype(float)

        def _chi(ev, od):
            exp = (ev + od) / 2.0
            m = exp > 4
            if m.sum() < 8:
                return None, 0
            return float((((ev[m] - exp[m]) ** 2) / exp[m]).sum()), int(m.sum() - 1)

        chi_pair, dof = _chi(hist[0:254:2], hist[1:255:2])
        chi_shift, _ = _chi(hist[1:255:2], hist[2:256:2])
        if chi_pair is None or chi_shift is None:
            continue
        p = _chi2_sf(chi_pair, dof)
        ratio = chi_shift / (chi_pair + 1e-9)
        pvals.append(round(p, 5))
        ratios.append(round(ratio, 3))
        total += 1
        # شبهة: الأزواج الزوجية مُسوّاة بوضوح أكثر من المُزاحة
        if p > 0.95 and ratio > 3.0:
            susp += 1
    return {"blocks_tested": total, "suspicious_blocks": susp,
            "suspicious_fraction": round(susp / total, 4) if total else 0.0,
            "p_values_sample": pvals[:40],
            "pair_vs_shift_ratio_sample": ratios[:40],
            "method": "Westfeld & Pfitzmann chi-square attack مع ضابط الأزواج المُزاحة"}


def _chi2_sf(x: float, k: int) -> float:
    """دالة البقاء لتوزيع كاي-تربيع (تكامل غاما غير الكامل المنظّم) — تنفيذ عددي."""
    if k <= 0:
        return 0.0
    if x <= 0:
        return 1.0
    a = k / 2.0
    xx = x / 2.0
    if xx < a + 1:
        # متسلسلة
        term = 1.0 / a
        total = term
        n = 1
        while n < 500:
            term *= xx / (a + n)
            total += term
            if term < total * 1e-12:
                break
            n += 1
        lng = math.lgamma(a)
        p = total * math.exp(-xx + a * math.log(xx) - lng)
        return max(0.0, min(1.0, 1.0 - p))
    # كسر مستمر (Lentz)
    tiny = 1e-300
    b = xx + 1 - a
    c = 1 / tiny
    d = 1 / b
    h = d
    for i in range(1, 500):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        d = 1 / d
        delta = d * c
        h *= delta
        if abs(delta - 1) < 1e-12:
            break
    q = math.exp(-xx + a * math.log(xx) - math.lgamma(a)) * h
    return max(0.0, min(1.0, q))


def rs_analysis(gray: np.ndarray) -> dict:
    """تحليل RS الكامل (Fridrich, Goljan & Du 2001) لتقدير نسبة حمولة LSB.

    يُقاس عدد المجموعات المنتظمة (R) والمفردة (S) تحت قناع الانعكاس M و-M،
    ثم يُكرَّر القياس على الصورة بعد عكس كل البتات الأدنى، وتُحلّ المعادلة
    التربيعية المعيارية لاستخراج نسبة البكسلات الحاملة للرسالة.
    """
    a = gray.astype(np.int32)
    h, w = a.shape
    if w < 4 or h < 1:
        return {"applicable": False, "reason": "أبعاد غير كافية"}
    g0 = a[:, :(w // 4) * 4].reshape(-1, 4)
    if g0.shape[0] < 100:
        return {"applicable": False, "reason": "عدد المجموعات غير كافٍ"}
    mask = np.array([1, 0, 0, 1])

    def disc(g):
        return np.abs(np.diff(g, axis=1)).sum(axis=1)

    def f1(x):
        return x ^ 1

    def fm1(x):
        return ((x + 1) ^ 1) - 1

    def rs(g, negative=False):
        fn = fm1 if negative else f1
        gg = g.copy()
        cols = np.where(mask == 1)[0]
        gg[:, cols] = fn(gg[:, cols])
        d0, d1 = disc(g), disc(gg)
        tot = g.shape[0]
        return float((d1 > d0).sum()) / tot, float((d1 < d0).sum()) / tot

    g1 = f1(g0)                      # الصورة بعد عكس كل البتات الأدنى (p = 1)
    Rm, Sm = rs(g0, False)
    Rmn, Smn = rs(g0, True)
    Rm1, Sm1 = rs(g1, False)
    Rmn1, Smn1 = rs(g1, True)

    d0, dn0 = Rm - Sm, Rmn - Smn
    d1, dn1 = Rm1 - Sm1, Rmn1 - Smn1
    A = 2 * (d1 + d0)
    B = dn0 - dn1 - d1 - 3 * d0
    C = d0 - dn0
    payload = None
    try:
        if abs(A) < 1e-12:
            x = -C / B if abs(B) > 1e-12 else None
        else:
            disc_ = B * B - 4 * A * C
            if disc_ < 0:
                x = -B / (2 * A)
            else:
                r1 = (-B + np.sqrt(disc_)) / (2 * A)
                r2 = (-B - np.sqrt(disc_)) / (2 * A)
                x = r1 if abs(r1) < abs(r2) else r2
        if x is not None and abs(x - 0.5) > 1e-9:
            payload = float(x / (x - 0.5))
    except Exception:
        payload = None
    if payload is None or not np.isfinite(payload):
        payload = 0.0
    payload = max(0.0, min(1.0, payload))
    return {"applicable": True,
            "R_m": round(Rm, 5), "S_m": round(Sm, 5),
            "R_-m": round(Rmn, 5), "S_-m": round(Smn, 5),
            "R_m_flipped": round(Rm1, 5), "S_m_flipped": round(Sm1, 5),
            "estimated_payload_ratio": round(payload, 4),
            "method": "RS steganalysis بالمعادلة التربيعية المعيارية (Fridrich et al., 2001)"}


def histogram_stats(im: Image.Image, outdir: str) -> dict:
    rgb = im.convert("RGB")
    a = np.asarray(rgb)
    out: dict = {"channels": {}}
    for i, c in enumerate("RGB"):
        ch = a[:, :, i].flatten()
        hist = np.bincount(ch, minlength=256)
        zeros = int((hist == 0).sum())
        out["channels"][c] = {
            "mean": round(float(ch.mean()), 3), "std": round(float(ch.std()), 3),
            "min": int(ch.min()), "max": int(ch.max()),
            "clipped_black_pct": round(float((ch == 0).mean() * 100), 3),
            "clipped_white_pct": round(float((ch == 255).mean() * 100), 3),
            "empty_bins": zeros,
            "histogram": hist.tolist(),
        }
    combs = sum(v["empty_bins"] for v in out["channels"].values()) / 3
    out["comb_artifact"] = {
        "avg_empty_bins": round(combs, 1),
        "note": ("⚠️ فجوات كثيرة في المدرج (نمط المشط) — أثر نموذجي لتعديل السطوع/التباين/المستويات "
                 "بعد الالتقاط." if combs > 40 else
                 "المدرج متصل دون فجوات غير طبيعية.")}
    gray = np.asarray(rgb.convert("L")).astype(np.float32)
    gx = np.diff(gray, axis=1)
    gy = np.diff(gray, axis=0)
    out["sharpness_laplacian_var"] = round(float(np.var(gx)) + float(np.var(gy)), 3)
    uniq = len(np.unique(np.asarray(rgb.convert("L"))))
    out["unique_gray_levels"] = uniq
    if uniq < 200:
        out["posterization_note"] = "عدد مستويات الرمادي منخفض — أثر إعادة معالجة/تقليل ألوان."
    return out


def thumbnail_compare(main: Image.Image, thumb_bytes: bytes, outdir: str) -> dict:
    """مقارنة الصورة الرئيسية بالمصغّرة المدمجة: التعارض = تعديل بعد الالتقاط."""
    try:
        th = Image.open(io.BytesIO(thumb_bytes)).convert("RGB")
    except Exception as e:
        return {"applicable": False, "reason": str(e)}
    fn = _save(th, outdir, "embedded_thumbnail.png")
    m = main.convert("RGB").resize(th.size, Image.LANCZOS)
    a = np.asarray(m).astype(np.float32)
    b = np.asarray(th).astype(np.float32)
    mse = float(((a - b) ** 2).mean())
    # ارتباط عام
    corr = float(np.corrcoef(a.flatten(), b.flatten())[0, 1]) if a.size == b.size else 0.0
    diff = _save(_norm_to_img(np.abs(a - b).mean(axis=2), cmap=True), outdir, "thumb_diff.png")
    aspect_main = main.width / main.height
    aspect_th = th.width / th.height
    verdict = []
    if corr < 0.9:
        verdict.append("⚠️ الصورة المصغّرة المدمجة تختلف جوهريًا عن الصورة الحالية — "
                       "دليل قوي على تعديل الصورة بعد التقاطها (المصغّرة لم تُحدَّث).")
    if abs(aspect_main - aspect_th) > 0.02:
        verdict.append("⚠️ نسبة أبعاد المصغّرة تخالف الصورة الحالية — مؤشر على قصّ (Crop).")
    if not verdict:
        verdict.append("المصغّرة متوافقة مع الصورة الحالية (لا تعارض).")
    return {"applicable": True, "thumbnail_image": fn, "diff_image": diff,
            "thumbnail_size": f"{th.width}x{th.height}", "mse": round(mse, 3),
            "correlation": round(corr, 5), "verdict": verdict}


def basic_info(im: Image.Image) -> dict:
    return {
        "format": im.format, "mode": im.mode, "width": im.width, "height": im.height,
        "megapixels": round(im.width * im.height / 1e6, 3),
        "aspect_ratio": round(im.width / im.height, 5) if im.height else None,
        "has_alpha": im.mode in ("RGBA", "LA") or "transparency" in im.info,
        "n_frames": getattr(im, "n_frames", 1),
        "is_animated": getattr(im, "is_animated", False),
        "icc_profile_present": bool(im.info.get("icc_profile")),
        "dpi": im.info.get("dpi"),
    }
