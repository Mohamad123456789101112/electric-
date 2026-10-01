"""
فاكّ ترميز JPEG على مستوى المعاملات (Baseline sequential DCT).

لماذا؟ لأن أقوى أدلة تزوير الصور تُقرأ من **معاملات DCT المُكمَّمة نفسها** كما خزّنها
المُرمِّز، لا من البكسلات بعد فك الضغط. هذا المحلّل يفك ترميز هوفمان ويستخرج
المعاملات الحقيقية (قبل الضرب في جدول التكميم)، فتصبح اختبارات الضغط المزدوج
وبصمة المُرمِّز قائمة على بيانات أصلية لا على تقدير.

المرجع: ITU-T T.81 (ISO/IEC 10918-1) — الأقسام F.2 (فك الترميز المتتابع).
"""
from __future__ import annotations

import struct

import numpy as np

ZIGZAG = [
    0, 1, 8, 16, 9, 2, 3, 10, 17, 24, 32, 25, 18, 11, 4, 5,
    12, 19, 26, 33, 40, 48, 41, 34, 27, 20, 13, 6, 7, 14, 21, 28,
    35, 42, 49, 56, 57, 50, 43, 36, 29, 22, 15, 23, 30, 37, 44, 51,
    58, 59, 52, 45, 38, 31, 39, 46, 53, 60, 61, 54, 47, 55, 62, 63]


class _BitReader:
    __slots__ = ("data", "pos", "bits", "nbits", "eof", "markers")

    def __init__(self, data: bytes, pos: int):
        self.data = data
        self.pos = pos
        self.bits = 0
        self.nbits = 0
        self.eof = False
        self.markers: list[int] = []

    def _fill(self) -> None:
        d = self.data
        while self.nbits <= 24:
            if self.pos >= len(d):
                self.eof = True
                self.bits = (self.bits << 8) & 0xFFFFFFFFFF
                self.nbits += 8
                continue
            b = d[self.pos]
            self.pos += 1
            if b == 0xFF:
                nxt = d[self.pos] if self.pos < len(d) else 0xD9
                if nxt == 0x00:
                    self.pos += 1
                elif 0xD0 <= nxt <= 0xD7:
                    self.pos += 1
                    self.markers.append(nxt)
                    continue
                else:
                    self.eof = True
                    self.pos -= 1
                    b = 0
            self.bits = ((self.bits << 8) | b) & 0xFFFFFFFFFF
            self.nbits += 8

    def bit(self) -> int:
        if self.nbits == 0:
            self._fill()
        self.nbits -= 1
        return (self.bits >> self.nbits) & 1

    def receive(self, n: int) -> int:
        v = 0
        for _ in range(n):
            v = (v << 1) | self.bit()
        return v

    def reset(self) -> None:
        self.bits = 0
        self.nbits = 0
        # محاذاة على حدود البايت وتخطي علامة RST إن وُجدت
        d = self.data
        while self.pos + 1 < len(d):
            if d[self.pos] == 0xFF and 0xD0 <= d[self.pos + 1] <= 0xD7:
                self.pos += 2
                return
            self.pos += 1


def _extend(v: int, t: int) -> int:
    return v - (1 << t) + 1 if t and v < (1 << (t - 1)) else v


def _build_huff(counts: list[int], symbols: list[int]) -> dict:
    table: dict[tuple[int, int], int] = {}
    code = 0
    k = 0
    for ln in range(1, 17):
        for _ in range(counts[ln - 1]):
            if k < len(symbols):
                table[(ln, code)] = symbols[k]
            k += 1
            code += 1
        code <<= 1
    return table


def _decode_huff(br: _BitReader, table: dict) -> int:
    code = 0
    for ln in range(1, 17):
        code = (code << 1) | br.bit()
        s = table.get((ln, code))
        if s is not None:
            return s
    return 0


def decode_coefficients(data: bytes, max_mcus: int = 60000) -> dict:
    """يرجع المعاملات المُكمَّمة الحقيقية لكل مكوّن في صورة JPEG أساسية."""
    out: dict = {"ok": False, "reason": ""}
    if data[:2] != b"\xFF\xD8":
        out["reason"] = "ليس ملف JPEG"
        return out
    qt: dict[int, list[int]] = {}
    hdc: dict[int, dict] = {}
    hac: dict[int, dict] = {}
    frame = None
    restart_interval = 0
    i = 2
    n = len(data)
    while i < n - 1:
        if data[i] != 0xFF:
            i += 1
            continue
        m = data[i + 1]
        if m in (0xD8, 0x01) or 0xD0 <= m <= 0xD7:
            i += 2
            continue
        if m == 0xD9:
            break
        if i + 4 > n:
            break
        ln = struct.unpack_from(">H", data, i + 2)[0]
        seg = data[i + 4:i + 2 + ln]
        if m == 0xDB:
            p = 0
            while p < len(seg):
                pq, tq = seg[p] >> 4, seg[p] & 15
                p += 1
                if pq == 0:
                    qt[tq] = list(seg[p:p + 64]); p += 64
                else:
                    qt[tq] = list(struct.unpack_from(">64H", seg, p)); p += 128
        elif m == 0xC4:
            p = 0
            while p + 17 <= len(seg):
                tc, th = seg[p] >> 4, seg[p] & 15
                counts = list(seg[p + 1:p + 17])
                total = sum(counts)
                syms = list(seg[p + 17:p + 17 + total])
                tbl = _build_huff(counts, syms)
                (hac if tc else hdc)[th] = tbl
                p += 17 + total
        elif m == 0xDD and len(seg) >= 2:
            restart_interval = struct.unpack_from(">H", seg, 0)[0]
        elif m in (0xC0, 0xC1):
            prec = seg[0]
            h, w = struct.unpack_from(">HH", seg, 1)
            nc = seg[5]
            comps = []
            for c in range(nc):
                cid, hv, tq = seg[6 + c * 3], seg[7 + c * 3], seg[8 + c * 3]
                comps.append({"id": cid, "h": hv >> 4, "v": hv & 15, "tq": tq})
            frame = {"width": w, "height": h, "precision": prec, "components": comps}
        elif m == 0xC2:
            out["reason"] = "JPEG تقدمي (Progressive) — فكّ المعاملات هنا يدعم الوضع الأساسي فقط."
            return out
        elif m in (0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            out["reason"] = f"وضع JPEG غير مدعوم للفك (علامة 0x{m:02X})"
            return out
        elif m == 0xDA:
            ns = seg[0]
            scomp = []
            for c in range(ns):
                cs, td_ta = seg[1 + c * 2], seg[2 + c * 2]
                scomp.append({"id": cs, "dc": td_ta >> 4, "ac": td_ta & 15})
            if frame is None:
                out["reason"] = "لم يُعثر على ترويسة إطار قبل المسح"
                return out
            return _decode_scan(data, i + 2 + ln, frame, scomp, hdc, hac, qt,
                                restart_interval, max_mcus)
        i += 2 + ln
    out["reason"] = out["reason"] or "لم يُعثر على مقطع المسح (SOS)"
    return out


def _decode_scan(data: bytes, pos: int, frame: dict, scomp: list[dict],
                 hdc: dict, hac: dict, qt: dict, ri: int, max_mcus: int) -> dict:
    comps = frame["components"]
    hmax = max(c["h"] for c in comps)
    vmax = max(c["v"] for c in comps)
    mcux = (frame["width"] + 8 * hmax - 1) // (8 * hmax)
    mcuy = (frame["height"] + 8 * vmax - 1) // (8 * vmax)
    total_mcus = mcux * mcuy
    limit = min(total_mcus, max_mcus)

    sel = {s["id"]: s for s in scomp}
    store: dict[int, list] = {c["id"]: [] for c in comps if c["id"] in sel}
    pred: dict[int, int] = {c["id"]: 0 for c in comps}
    br = _BitReader(data, pos)
    decoded = 0
    try:
        for mcu in range(limit):
            if ri and mcu and mcu % ri == 0:
                br.reset()
                for k in pred:
                    pred[k] = 0
            for c in comps:
                if c["id"] not in sel:
                    continue
                dct = hdc.get(sel[c["id"]]["dc"], {})
                act = hac.get(sel[c["id"]]["ac"], {})
                for _ in range(c["h"] * c["v"]):
                    blk = [0] * 64
                    t = _decode_huff(br, dct)
                    diff = _extend(br.receive(t), t) if t else 0
                    pred[c["id"]] += diff
                    blk[0] = pred[c["id"]]
                    k = 1
                    while k < 64:
                        rs = _decode_huff(br, act)
                        r, s = rs >> 4, rs & 15
                        if s == 0:
                            if r == 15:
                                k += 16
                                continue
                            break
                        k += r
                        if k > 63:
                            break
                        blk[ZIGZAG[k]] = _extend(br.receive(s), s)
                        k += 1
                    store[c["id"]].append(blk)
            decoded += 1
            if br.eof:
                break
    except Exception:
        pass

    arrays = {}
    for cid, blocks in store.items():
        if blocks:
            arrays[cid] = np.asarray(blocks, dtype=np.int32)
    return {
        "ok": bool(arrays),
        "frame": {k: v for k, v in frame.items() if k != "components"},
        "components": [{"id": c["id"], "sampling": f"{c['h']}x{c['v']}",
                        "quant_table_id": c["tq"],
                        "blocks_decoded": int(arrays[c["id"]].shape[0]) if c["id"] in arrays else 0}
                       for c in comps],
        "mcus_total": total_mcus, "mcus_decoded": decoded,
        "coverage": round(decoded / total_mcus, 4) if total_mcus else 0,
        "quant_tables": qt,
        "_coeffs": arrays,
        "restart_interval": ri,
    }


# ----------------------------------------------- تحليلات مبنية على المعاملات

def double_compression(data: bytes) -> dict:
    """كشف الضغط المزدوج من مدرّجات المعاملات المُكمَّمة الحقيقية.

    الأساس العلمي: عند إعادة ضغط صورة JPEG بجدول تكميم مختلف، تنشأ في مدرّج كل
    معامل قممٌ وفجوات دورية (Double Quantization artifact) — Popescu & Farid 2004,
    Lin et al. 2009. نقيس شدة الدورية عبر الارتباط الذاتي لبقايا المدرّج بعد إزالة الاتجاه العام.
    """
    dec = decode_coefficients(data)
    if not dec.get("ok"):
        return {"applicable": False, "reason": dec.get("reason", "تعذّر فك المعاملات")}
    y = dec["_coeffs"].get(min(dec["_coeffs"].keys()))
    if y is None or y.shape[0] < 400:
        return {"applicable": False, "reason": "عدد الكتل غير كافٍ للتحليل الإحصائي."}
    results = []
    flags = 0
    for idx, (u, v) in enumerate(((0, 1), (1, 0), (1, 1), (0, 2), (2, 0), (2, 1), (1, 2), (2, 2))):
        pos = u * 8 + v
        vals = y[:, pos]
        vals = vals[np.abs(vals) <= 40]
        if vals.size < 400:
            continue
        n_samples = int(vals.size)
        hist = np.bincount(vals + 40, minlength=81).astype(float)
        nz = hist > 0
        if nz.sum() < 10:
            continue
        # إزالة الاتجاه العام (المدرّج الطبيعي سلس وأحادي القمة) ثم قياس الدورية
        # عبر الارتباط الذاتي: التكميم المزدوج يُنتج قممًا على مسافات منتظمة
        # (وتوافقياتها)، بينما ضجيج المدرّج الطبيعي لا يُنتج ارتباطًا دوريًا.
        kernel = np.ones(5) / 5.0
        smooth = np.convolve(hist, kernel, mode="same")
        resid = hist - smooth
        resid = resid - resid.mean()
        denom = float((resid * resid).sum()) + 1e-9
        ac = [float((resid[:len(resid) - L] * resid[L:]).sum()) / denom for L in range(0, 21)]
        best_score, best_lag = 0.0, 0
        for L in range(2, 9):
            harmonics = [ac[L]] + ([ac[2 * L]] if 2 * L <= 20 else [])
            sc = float(np.mean(harmonics))
            if sc > best_score:
                best_score, best_lag = sc, L
        lo, hi = int(np.argmax(nz)), int(len(hist) - np.argmax(nz[::-1]))
        span = hist[lo:hi]
        gap_ratio = float((span == 0).sum() / max(1, span.size))
        periodic = bool(best_score > 0.45)
        if periodic:
            flags += 1
        results.append({"coefficient": f"({u},{v})", "samples": n_samples,
                        "period_bins": best_lag,
                        "periodicity_score": round(best_score, 3),
                        "gap_ratio": round(gap_ratio, 3), "periodic": periodic})
    tested = len(results)
    ratio = flags / tested if tested else 0
    verdict = ("مؤشرات قوية على ضغط JPEG مزدوج — الصورة فُتحت وأُعيد حفظها بعد الضغط الأول"
               if ratio >= 0.35 else
               "مؤشرات محتملة على ضغط مزدوج — تحتاج تأييدًا بأدلة أخرى" if ratio >= 0.2 else
               "لا دورية دالة في مدرّجات المعاملات — متوافق مع ضغط واحد")
    return {"applicable": True, "coefficients": results, "periodic_flags": flags,
            "tested": tested, "flag_ratio": round(ratio, 3), "verdict": verdict,
            "blocks_analyzed": int(y.shape[0]), "coverage": dec["coverage"],
            "method": "تحليل مدرّج معاملات DCT المُكمَّمة المستخرجة فعليًا من تيار JPEG "
                      "(Popescu & Farid 2004)",
            "limitation": "غياب الدورية لا ينفي إعادة الحفظ: إذا كان التكميم الثاني أخشن من الأول "
                          "(حفظ بجودة أقل) فإن آثار التكميم المزدوج تُمحى فيزيائيًا ولا يمكن رصدها "
                          "بهذه الطريقة — وهذا حدّ معروف للمنهج وليس خطأً في القياس."}


def coefficient_stats(data: bytes) -> dict:
    """إحصاءات المعاملات: قانون بنفورد على الرقم الأول (كشف إعادة الضغط/التوليد الصناعي)."""
    dec = decode_coefficients(data)
    if not dec.get("ok"):
        return {"applicable": False, "reason": dec.get("reason", "")}
    y = dec["_coeffs"].get(min(dec["_coeffs"].keys()))
    if y is None:
        return {"applicable": False, "reason": "لا توجد معاملات"}
    ac = np.abs(y[:, 1:]).flatten()
    ac = ac[ac > 0]
    if ac.size < 1000:
        return {"applicable": False, "reason": "معاملات غير كافية"}
    first = (ac // (10 ** (np.floor(np.log10(ac))))).astype(int)
    obs = np.bincount(first, minlength=10)[1:10].astype(float)
    obs /= obs.sum()
    benford = np.array([np.log10(1 + 1 / d) for d in range(1, 10)])
    chi2 = float((((obs - benford) ** 2) / benford).sum() * ac.size)
    diverg = float(np.abs(obs - benford).sum())
    # ملاءمة قانون بنفورد المعمّم  p(d)=N·log10(1+1/(s+d^q))  (Fu, Shi & Su 2007)
    d_ = np.arange(1, 10, dtype=float)
    best = (1e9, None)
    for q in np.arange(0.5, 2.51, 0.05):
        for sshift in np.arange(-0.6, 1.61, 0.05):
            denom = sshift + d_ ** q
            if np.any(denom <= 0):
                continue
            model = np.log10(1 + 1 / denom)
            model = model / model.sum()
            sse = float(((obs - model) ** 2).sum())
            if sse < best[0]:
                best = (sse, (float(q), float(sshift), model))
    fit_sse, fit = best
    fit_tv = float(np.abs(obs - fit[2]).sum() / 2) if fit else None
    return {"applicable": True,
            "observed_first_digit": [round(x, 4) for x in obs],
            "benford_expected": [round(x, 4) for x in benford],
            "total_variation_distance": round(diverg / 2, 4),
            "chi_square": round(chi2, 2),
            "nonzero_ac_coefficients": int(ac.size),
            "generalized_benford_fit": {"q": fit[0] if fit else None, "s": fit[1] if fit else None,
                                        "sse": round(fit_sse, 6),
                                        "total_variation": round(fit_tv, 4) if fit_tv is not None else None},
            "interpretation": ("توزيع الرقم الأول يلائم قانون بنفورد المعمّم بدقة — سلوك طبيعي "
                               "لصورة مضغوطة مرة واحدة."
                               if (fit_tv is not None and fit_tv < 0.05) else
                               "انحراف عن قانون بنفورد المعمّم — شائع في الصور المُعاد ضغطها أو المعالَجة."),
            "method": "Generalized Benford's Law على معاملات DCT (Fu, Shi & Su, 2007)"}
