"""
بصمة الضغط JPEG: تحديد مصدر الصورة من جداول التكميم وحدها (على نمط JPEGsnoop).

الفكرة: ملف JPEG لا يحمل فقط بكسلات، بل يحمل **توقيع المُرمِّز** الذي أنتجه:
جداول التكميم، جداول هوفمان، نسبة تخفيض اللون، ترتيب المقاطع، ووجود مقاطع
APP بعينها. هذه البصمة تبقى كاملة **حتى لو مُسحت كل الميتاداتا**، لأنها جزء
من بنية الضغط نفسها لا من الوسوم.

منهجية صارمة مُلتزَم بها هنا:
  • كل ما يُنسب إلى جهة مُسمّاة يأتي من **عيّنة مرجعية مُتحقَّق منها** (إما
    مُولَّدة محليًا ومُثبتة بالاختبار، أو يضيفها المحقق بنفسه من جهاز بحوزته).
  • لا تُختلق جداول منسوبة لواتساب أو آيفون أو فوتوشوب من الذاكرة. إن لم يوجد
    تطابق مرجعي، تُعرض **الخصائص البنيوية المقيسة** وتُصنّف العائلة التقنية
    (IJG قياسي / جدول مخصّص / مُحسَّن)، ويُقال صراحةً إن المصدر غير محدَّد.
  • قاعدة البصمات **قابلة للتوسعة**: يرفع المحقق صورة مرجعية من جهاز معروف
    فتُستخرج بصمتها وتُسجَّل باسمه مع تاريخ ومصدر العيّنة (provenance).

الأساس العلمي المُتحقَّق منه محليًا:
  - جداول Annex K الأساسية تُطابق مخرجات libjpeg عند الجودة 50 (مُختبَر).
  - معادلة التدرّج في libjpeg:  q(i) = clamp((base(i)·S + 50)/100, 1, 255)
    حيث S = 5000/Q للجودة <50 و S = 200−2Q للجودة ≥50 (مُختبَر لكل جودة 1..100).
"""
from __future__ import annotations

import hashlib
import json
import os
import time

from .jpeg import STD_CHROMA, STD_LUMA

# ترتيب زجزاج القياسي (JPEG Annex A) — لازم لتحويل الجدول إلى شبكة 8×8
ZIGZAG = [
    0, 1, 8, 16, 9, 2, 3, 10, 17, 24, 32, 25, 18, 11, 4, 5,
    12, 19, 26, 33, 40, 48, 41, 34, 27, 20, 13, 6, 7, 14, 21, 28,
    35, 42, 49, 56, 57, 50, 43, 36, 29, 22, 15, 23, 30, 37, 44, 51,
    58, 59, 52, 45, 38, 31, 39, 46, 53, 60, 61, 54, 47, 55, 62, 63]

# بصمات جداول هوفمان القياسية (Annex K) — مستخرجة معمليًا من libjpeg
# ومُعاد توليدها والتحقق منها في tests/test_engines.py (لا قيم محفوظة بلا سند).
STD_HUFFMAN_SHA1 = {
    "DC0": "4097f3098faf5020", "AC0": "9d3fb1cb18c2b7a8",
    "DC1": "87a1c59c45e75e99", "AC1": "4c6d66658d1f0d71",
}


# ===================================================================
#   1) معادلة تدرّج IJG وتقدير الجودة بدقة
# ===================================================================

def ijg_scale(base: list[int], quality: int, max_val: int = 255) -> list[int]:
    """توليد جدول التكميم كما يفعل libjpeg تمامًا عند جودة معيّنة."""
    q = max(1, min(100, int(quality)))
    # القسمة في libjpeg صحيحة (عددية) لا كسرية — فرق جوهري عند الجودات < 50
    s = 5000 // q if q < 50 else 200 - 2 * q
    return [max(1, min(max_val, (b * s + 50) // 100)) for b in base]


def quality_of_table(table: list[int], chroma: bool = False) -> dict:
    """
    تحديد جودة libjpeg من جدول التكميم بالمطابقة التامة لا بالمتوسط.

    نجرّب كل الجودات 1..100 ونقارن الجدول قيمةً بقيمة:
      • تطابق تام ⇒ الجودة مؤكدة وجدول قياسي.
      • لا تطابق ⇒ نُرجع أقرب جودة مع أقصى انحراف، ونصنّف الجدول «غير قياسي».
    """
    base = STD_CHROMA if chroma else STD_LUMA
    if len(table) < 64:
        return {"ok": False, "reason": "جدول ناقص (أقل من 64 قيمة)"}
    t = from_zigzag(list(table[:64]))
    best = None
    exact_qs = []
    for q in range(1, 101):
        gen = ijg_scale(base, q)
        dev = max(abs(a - b) for a, b in zip(t, gen))
        l1 = sum(abs(a - b) for a, b in zip(t, gen))
        if l1 == 0:
            exact_qs.append(q)
        if best is None or (l1, dev) < (best["l1"], best["max_dev"]):
            best = {"quality": q, "l1": l1, "max_dev": dev}
    exact = best["l1"] == 0
    out = {"ok": True, "quality": best["quality"], "exact_ijg_match": exact,
           "max_deviation": best["max_dev"], "l1_distance": best["l1"],
           "table_class": "لون (Chroma)" if chroma else "إضاءة (Luma)"}
    if len(exact_qs) > 1:
        # عند الجودات المنخفضة جدًا يتشبّع الجدول عند 255 فتتطابق عدة جودات
        out["quality_candidates"] = exact_qs
        out["ambiguous"] = True
        out["quality"] = exact_qs[-1]
    if exact:
        out["note"] = (f"جدول قياسي مطابق تمامًا لمقياس IJG عند الجودة "
                       f"{best['quality']} — أي أن المُرمِّز من عائلة libjpeg/IJG "
                       "(تشمل أغلب الكاميرات وبرامج التحرير الشائعة).")
    else:
        out["note"] = (f"⚠️ جدول **غير قياسي**: أقرب جودة IJG هي {best['quality']} "
                       f"لكن بانحراف أقصاه {best['max_dev']}. المُرمِّز يستخدم جدولًا "
                       "مخصّصًا — سمة مميِّزة لتطبيقات/أجهزة بعينها وتصلح للمطابقة.")
    return out


def from_zigzag(table: list[int]) -> list[int]:
    """
    تحويل الجدول من ترتيب الزجزاج (كما يُخزَّن داخل مقطع DQT) إلى الترتيب
    الصفّي الطبيعي الذي كُتبت به جداول Annex K المرجعية.

    إغفال هذه الخطوة خطأ شائع يجعل تقدير الجودة مقاربًا بدل أن يكون تامًا.
    """
    out = [0] * 64
    for i, pos in enumerate(ZIGZAG[:min(64, len(table))]):
        out[pos] = table[i]
    return out


def table_grid(table: list[int]) -> list[list[int]]:
    """تحويل الجدول من ترتيب زجزاج إلى شبكة 8×8 كما يُعرض في JPEGsnoop."""
    grid = [[0] * 8 for _ in range(8)]
    for i, pos in enumerate(ZIGZAG[:min(64, len(table))]):
        grid[pos // 8][pos % 8] = table[i]
    return grid


def table_stats(table: list[int]) -> dict:
    t = from_zigzag(list(table[:64]))
    nz = [x for x in t if x > 0]
    return {
        "dc_step": t[0],
        "sum": sum(t),
        "mean": round(sum(t) / len(t), 2) if t else 0,
        "min": min(t) if t else 0,
        "max": max(t) if t else 0,
        "distinct_values": len(set(t)),
        "all_ones": all(x == 1 for x in t),
        "clipped_at_255": sum(1 for x in t if x >= 255),
        # المتوسطات محسوبة على الترتيب الصفّي: الربع العلوي الأيسر ترددات منخفضة
        "low_freq_mean": round(sum(t[r * 8 + c] for r in range(4) for c in range(4)) / 16, 2),
        "high_freq_mean": round(sum(t[r * 8 + c] for r in range(4, 8) for c in range(4, 8)) / 16, 2),
        "nonzero": len(nz),
    }


# ===================================================================
#   2) بصمة الضغط الكاملة (توقيع المُرمِّز)
# ===================================================================

def compression_signature(jp: dict) -> dict:
    """
    بناء توقيع المُرمِّز من البنية وحدها — بلا أي اعتماد على الميتاداتا.

    يتكوّن من: قيم جداول التكميم كاملة + معرّفاتها، نسبة تخفيض اللون، نوع
    الإطار (أساسي/تقدمي)، بصمات جداول هوفمان، وترتيب مقاطع APP كما ظهرت.
    """
    if not jp or not jp.get("is_jpeg"):
        return {"ok": False, "reason": "ليس ملف JPEG."}
    qts = jp.get("quant_tables") or []
    frame = jp.get("frame") or {}
    huff = jp.get("huffman_tables") or []

    qt_part = ";".join(
        f"{t.get('table_id')}:" + ",".join(str(v) for v in (t.get("values") or [])[:64])
        for t in qts)
    huff_part = ",".join(f"{h['class']}{h['table_id']}={h['sha1']}" for h in huff)
    markers = [s.get("marker") for s in jp.get("segments", [])]
    app_order = [m for m in markers if m and (m.startswith("APP") or m == "COM")]
    structure = "|".join([
        f"frame={'progressive' if frame.get('progressive') else 'baseline'}",
        f"sub={frame.get('subsampling')}",
        f"comps={frame.get('components')}",
        f"precision={frame.get('precision')}",
        f"apps={'>'.join(app_order)}",
        f"dqt={len(qts)}",
        f"dht={len(huff)}",
    ])
    full = qt_part + "||" + huff_part + "||" + structure
    # توقيع «الملمح»: جداول التكميم + البنية بلا بصمات هوفمان. ضروري لأن
    # المُرمِّزات التي تُحسّن جداول هوفمان تُنتج جداول مختلفة لكل صورة، فلا
    # يتكرر التوقيع الكامل أبدًا بينما يبقى الملمح ثابتًا لنفس الجهاز/الإعداد.
    profile = qt_part + "||" + structure
    std_huff = bool(huff) and all(
        h["sha1"] == STD_HUFFMAN_SHA1.get(f"{h['class']}{h['table_id']}")
        for h in huff)
    return {
        "ok": True,
        "qt_signature": hashlib.sha256(qt_part.encode()).hexdigest()[:32],
        "huffman_signature": hashlib.sha256(huff_part.encode()).hexdigest()[:32] if huff else None,
        "structure_signature": hashlib.sha256(structure.encode()).hexdigest()[:32],
        "full_signature": hashlib.sha256(full.encode()).hexdigest(),
        "profile_signature": hashlib.sha256(profile.encode()).hexdigest()[:32],
        "quant_table_count": len(qts),
        "subsampling": frame.get("subsampling"),
        "progressive": bool(frame.get("progressive")),
        "app_marker_order": app_order,
        "huffman_standard": std_huff,
        "huffman_optimized": bool(huff) and not std_huff,
        "structure_text": structure,
    }


def analyze_tables(jp: dict) -> dict:
    """تحليل علمي لكل جداول التكميم في الملف مع تقدير الجودة والتصنيف."""
    qts = jp.get("quant_tables") or []
    out = {"tables": [], "count": len(qts)}
    exact_all = bool(qts)
    qualities = []
    for t in qts:
        chroma = t.get("table_id", 0) != 0
        vals = t.get("values") or []
        q = quality_of_table(vals, chroma=chroma)
        st = table_stats(vals)
        exact_all &= bool(q.get("exact_ijg_match"))
        if q.get("ok"):
            qualities.append(q["quality"])
        out["tables"].append({
            "table_id": t.get("table_id"), "precision_bits": t.get("precision_bits"),
            "role": "إضاءة (Y)" if not chroma else "لون (Cb/Cr)",
            "quality": q.get("quality"), "exact_ijg_match": q.get("exact_ijg_match"),
            "max_deviation": q.get("max_deviation"), "note": q.get("note"),
            "stats": st, "grid_8x8": table_grid(vals), "values": vals,
        })
    out["all_tables_standard_ijg"] = exact_all
    out["quality_estimate"] = max(qualities) if qualities else None
    out["qualities"] = qualities
    if not qts:
        out["verdict"] = "لا توجد جداول تكميم (ليس JPEG أو الملف مبتور)."
    elif exact_all:
        out["verdict"] = (f"جداول قياسية من عائلة libjpeg/IJG عند الجودة "
                          f"{out['quality_estimate']} — هذه العائلة يستخدمها عدد كبير "
                          "من الكاميرات والبرامج، فلا تكفي وحدها لتسمية جهة بعينها.")
    else:
        out["verdict"] = ("⚠️ الملف يحوي جدول تكميم **مخصّصًا** لا يطابق مقياس IJG — "
                          "هذه أقوى حالة للمطابقة: الجدول المخصّص يكاد يكون حصريًا "
                          "لمُرمِّز/جهاز بعينه.")
    return out


# ===================================================================
#   3) قاعدة البصمات القابلة للتوسعة
# ===================================================================

DEFAULT_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "data", "jpeg_signatures.json")


class SignatureDB:
    """
    قاعدة توقيعات المُرمِّزات. ملفان:
      • الملف المُرفق مع المشروع (توقيعات مُولَّدة ومُتحقَّق منها محليًا).
      • ملف المستخدم (توقيعات يتعلّمها المحقق من أجهزة بحوزته).
    """

    def __init__(self, builtin_path: str = DEFAULT_DB, user_path: str | None = None):
        self.builtin_path = builtin_path
        self.user_path = user_path
        self.entries: list[dict] = []
        self._load(builtin_path, "مُرفق مع المنظومة")
        if user_path:
            self._load(user_path, "أضافه المحقق")

    def _load(self, path: str, origin: str):
        if not path or not os.path.exists(path):
            return
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
        except Exception:
            return
        for e in d.get("signatures", []):
            e = dict(e)
            e.setdefault("origin", origin)
            e["_source_file"] = os.path.basename(path)
            self.entries.append(e)

    # ---------------------------------------------------------- التعلّم
    def learn(self, jp: dict, source_name: str, provenance: str,
              notes: str = "") -> dict:
        """تسجيل بصمة جديدة من عيّنة مرجعية يقدّمها المحقق."""
        sig = compression_signature(jp)
        if not sig.get("ok"):
            return {"ok": False, "reason": sig.get("reason")}
        ana = analyze_tables(jp)
        entry = {
            "source": source_name,
            "provenance": provenance,
            "notes": notes,
            "qt_signature": sig["qt_signature"],
            "full_signature": sig["full_signature"],
            "profile_signature": sig["profile_signature"],
            "huffman_signature": sig["huffman_signature"],
            "structure_signature": sig["structure_signature"],
            "subsampling": sig["subsampling"],
            "progressive": sig["progressive"],
            "huffman_optimized": sig["huffman_optimized"],
            "app_marker_order": sig["app_marker_order"],
            "quality": ana.get("quality_estimate"),
            "standard_ijg": ana.get("all_tables_standard_ijg"),
            "tables": [t.get("values") for t in (jp.get("quant_tables") or [])],
            "added_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "origin": "أضافه المحقق",
        }
        if not self.user_path:
            return {"ok": False, "reason": "لا يوجد مسار قاعدة بيانات للمستخدم."}
        db = {"signatures": []}
        if os.path.exists(self.user_path):
            try:
                with open(self.user_path, encoding="utf-8") as f:
                    db = json.load(f)
            except Exception:
                pass
        db.setdefault("signatures", [])
        db["signatures"] = [e for e in db["signatures"]
                            if e.get("full_signature") != entry["full_signature"]]
        db["signatures"].append(entry)
        os.makedirs(os.path.dirname(self.user_path), exist_ok=True)
        with open(self.user_path, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=1)
        self.entries.append(entry)
        return {"ok": True, **entry}

    def delete(self, full_signature: str) -> bool:
        if not self.user_path or not os.path.exists(self.user_path):
            return False
        with open(self.user_path, encoding="utf-8") as f:
            db = json.load(f)
        n = len(db.get("signatures", []))
        db["signatures"] = [e for e in db.get("signatures", [])
                            if e.get("full_signature") != full_signature]
        with open(self.user_path, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=1)
        self.entries = [e for e in self.entries
                        if e.get("full_signature") != full_signature]
        return len(db["signatures"]) < n

    def list(self) -> list[dict]:
        return [{k: v for k, v in e.items() if k != "tables"} for e in self.entries]

    # ---------------------------------------------------------- المطابقة
    def match(self, jp: dict) -> dict:
        sig = compression_signature(jp)
        if not sig.get("ok"):
            return {"ok": False, "reason": sig.get("reason")}
        exact, profile, qt_only, near = [], [], [], []
        mine = [t.get("values") or [] for t in (jp.get("quant_tables") or [])]
        for e in self.entries:
            if e.get("full_signature") == sig["full_signature"]:
                exact.append(e)
            elif (e.get("profile_signature")
                  and e["profile_signature"] == sig["profile_signature"]):
                profile.append(e)
            elif e.get("qt_signature") == sig["qt_signature"]:
                qt_only.append(e)
            else:
                d = _tables_distance(mine, e.get("tables") or [])
                if d is not None:
                    near.append((d, e))
        near.sort(key=lambda x: x[0])
        out = {"ok": True, "signature": sig,
               "exact_matches": [_strip(e) for e in exact],
               "profile_matches": [_strip(e) for e in profile],
               "quant_table_matches": [_strip(e) for e in qt_only],
               "nearest": [{"distance": d, **_strip(e)} for d, e in near[:3]],
               "database_size": len(self.entries)}
        if exact:
            names = sorted({e["source"] for e in exact})
            out["identified_source"] = names[0] if len(names) == 1 else names
            out["confidence"] = "تطابق تام للبصمة الكاملة"
            out["verdict"] = (f"🎯 بصمة الضغط تطابق تمامًا: «{'، '.join(names)}». "
                              "التطابق شمل جداول التكميم وهوفمان وترتيب المقاطع معًا.")
        elif profile:
            names = sorted({e["source"] for e in profile})
            out["identified_source"] = names[0] if len(names) == 1 else names
            out["confidence"] = "تطابق الملمح (جداول التكميم + البنية الكاملة)"
            out["verdict"] = (
                f"🎯 بصمة الضغط تطابق: «{'، '.join(names)}». التطابق شمل جداول "
                "التكميم وتخفيض اللون وترتيب المقاطع ونوع الإطار معًا؛ جداول هوفمان "
                "وحدها تختلف لأن هذا المُرمِّز يحسبها من محتوى كل صورة (optimize) — "
                "وهو سلوك متوقّع ولا ينفي التطابق.")
        elif qt_only:
            fams = sorted({e.get("family") or e["source"] for e in qt_only})
            quals = sorted({e.get("quality") for e in qt_only if e.get("quality")})
            out["identified_source"] = fams
            out["confidence"] = "تطابق جداول التكميم فقط (لا البنية الكاملة)"
            out["verdict"] = (
                f"🟠 جداول التكميم تطابق العائلة: «{'، '.join(fams)}»"
                + (f" عند الجودة {quals[0]}" if len(quals) == 1 else "")
                + f" — {len(qt_only)} مُدخَلًا مرجعيًا بنفس الجداول. لكن بقية البنية "
                  "(هوفمان/المقاطع/تخفيض اللون) تختلف، فالجداول وحدها تحدّد المُرمِّص "
                  "وإعداد الجودة لا الأداة بعينها.")
            out["verdict"] = out["verdict"].replace("المُرمِّص", "المُرمِّز")
        else:
            out["identified_source"] = None
            out["confidence"] = "لا يوجد تطابق مرجعي"
            out["verdict"] = ("لا توجد عيّنة مرجعية مطابقة في قاعدة البصمات. "
                              "يمكن للمحقق إضافة عيّنة من جهاز معروف ليصبح التعرّف "
                              "ممكنًا مستقبلًا.")
        return out


def _strip(e: dict) -> dict:
    return {k: v for k, v in e.items() if k not in ("tables",)}


def _tables_distance(a: list[list[int]], b: list[list[int]]) -> int | None:
    """مسافة L1 بين مجموعتي جداول تكميم (للمقارنة التقريبية)."""
    if not a or not b or len(a) != len(b):
        return None
    tot = 0
    for ta, tb in zip(a, b):
        if not ta or not tb or len(ta) < 64 or len(tb) < 64:
            return None
        tot += sum(abs(int(x) - int(y)) for x, y in zip(ta[:64], tb[:64]))
    return tot


# ===================================================================
#   4) استدلالات بنيوية حقيقية (ما يمكن قوله بلا قاعدة بصمات)
# ===================================================================

def structural_inference(jp: dict, sig: dict, ana: dict) -> list[dict]:
    """
    استنتاجات مبنية على خصائص مقيسة فعلًا، كل واحدة مع الدليل الذي أنتجها.
    لا تُسمّي جهة بعينها إلا إن كان المقطع نفسه يحمل اسمها (مثل APP14 Adobe).
    """
    facts: list[dict] = []
    apps = sig.get("app_marker_order") or []
    frame_prog = sig.get("progressive")

    if "APP14" in apps:
        facts.append({"fact": "المُرمِّز من أدوبي",
                      "detail": "وجود مقطع APP14 «Adobe» يكتبه مُرمِّز أدوبي حصريًا "
                                "(فوتوشوب/لايتروم/أدوات Adobe) ويحدّد تحويل الألوان.",
                      "evidence": "APP14"})
    if "APP12" in apps:
        facts.append({"fact": "نمط «حفظ للويب» (Ducky)",
                      "detail": "مقطع APP12 «Ducky» يكتبه فوتوشوب في مسار "
                                "Save for Web ويحمل إعداد الجودة.",
                      "evidence": "APP12"})
    if "APP2" in apps:
        facts.append({"fact": "مقطع APP2 موجود",
                      "detail": "يُستخدم لملف ألوان ICC أو لبنية MPF متعددة الصور "
                                "(شائعة في الهواتف وكاميرات التصوير المتتابع).",
                      "evidence": "APP2"})
    if apps and apps[0] == "APP0" and "APP1" not in apps:
        facts.append({"fact": "JFIF بلا EXIF",
                      "detail": "الملف يبدأ بـAPP0/JFIF ولا يحوي APP1/EXIF إطلاقًا — "
                                "نمط مميّز لإعادة الترميز ببرنامج أو خدمة تُسقط "
                                "الميتاداتا (تطبيقات المراسلة، محسّنات الويب).",
                      "evidence": ">".join(apps)})
    if not apps:
        facts.append({"fact": "بلا أي مقاطع APP",
                      "detail": "ملف خامّ تمامًا بلا JFIF ولا EXIF — إما مكتوب "
                                "بمكتبة ترميز مباشرة أو مُنظَّف بالكامل.",
                      "evidence": "لا توجد مقاطع APP"})
    if sig.get("huffman_optimized"):
        facts.append({"fact": "جداول هوفمان مُحسَّنة (غير قياسية)",
                      "detail": "المُرمِّز حسب جداول هوفمان من إحصاء الصورة نفسها "
                                "(optimize). الكاميرات غالبًا تستخدم الجداول "
                                "القياسية لسرعتها، بينما يفعل ذلك ضاغطو الويب "
                                "وبرامج التحرير لتقليل الحجم.",
                      "evidence": "بصمات DHT تخالف جداول Annex K"})
    elif sig.get("huffman_standard"):
        facts.append({"fact": "جداول هوفمان قياسية (Annex K)",
                      "detail": "نمط شائع في مُرمِّزات الأجهزة والكاميرات.",
                      "evidence": "بصمات DHT تطابق Annex K"})
    if frame_prog:
        facts.append({"fact": "ترميز تقدمي (Progressive)",
                      "detail": "الكاميرات لا تنتج JPEG تقدميًا عمليًا — هذا دليل "
                                "قوي على إعادة ترميز ببرنامج أو خدمة ويب.",
                      "evidence": "SOF2"})
    sub = sig.get("subsampling")
    if sub:
        facts.append({"fact": f"تخفيض اللون {sub}",
                      "detail": "نسبة تخفيض اللون من خصائص المُرمِّز وإعداداته "
                                "وتُضيّق دائرة المصادر المحتملة.",
                      "evidence": sub})
    if ana.get("all_tables_standard_ijg") is False:
        facts.append({"fact": "جدول تكميم مخصّص",
                      "detail": "لا يطابق أي جودة في مقياس IJG — مؤشر قوي على "
                                "مُرمِّز خاص بجهاز/تطبيق بعينه، وهو أفضل ما يُبنى "
                                "عليه التعرّف المرجعي.",
                      "evidence": f"أقصى انحراف عن أقرب جدول IJG: "
                                  f"{max((t.get('max_deviation') or 0) for t in ana.get('tables', [])) if ana.get('tables') else 0}"})
    return facts


def analyze(jp: dict, db: SignatureDB | None = None) -> dict:
    """نقطة الدخول: تحليل جداول التكميم + البصمة + المطابقة + الاستدلال البنيوي."""
    if not jp or not jp.get("is_jpeg"):
        return {"ok": False, "reason": "ليس ملف JPEG — لا توجد جداول تكميم."}
    sig = compression_signature(jp)
    ana = analyze_tables(jp)
    out = {"ok": True, "signature": sig, "quantization": ana,
           "structural_inference": structural_inference(jp, sig, ana)}
    if db is not None:
        m = db.match(jp)
        out["database_match"] = m
        out["verdict"] = m.get("verdict")
        out["identified_source"] = m.get("identified_source")
    else:
        out["verdict"] = ana.get("verdict")
    return out
