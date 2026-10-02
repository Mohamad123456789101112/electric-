"""
بناء الخط الزمني الجنائي ومطابقة الطوابع الزمنية (Timestamp correlation).
تضارب الطوابع من أقوى أدلة التلاعب في التحقيق الرقمي.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

_ISO = "%Y-%m-%dT%H:%M:%S"


def _parse(s) -> datetime | None:
    if not s or not isinstance(s, str):
        return None
    s = s.strip().replace("Z", "")
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S.%f", "%Y:%m:%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:len(datetime.now().strftime(fmt)) + 6][:26].split("+")[0].strip(), fmt)
        except ValueError:
            continue
    m = re.match(r"(\d{4})[:\-](\d{2})[:\-](\d{2})[ T](\d{2}):(\d{2}):(\d{2})", s)
    if m:
        try:
            return datetime(*[int(x) for x in m.groups()])
        except ValueError:
            return None
    return None


def build(events: list[dict]) -> dict:
    """events: [{label, source, value}]"""
    parsed = []
    for e in events:
        dt = _parse(e.get("value") or e.get("iso"))
        parsed.append({**e, "parsed": dt.strftime(_ISO) if dt else None,
                       "epoch": int(dt.replace(tzinfo=timezone.utc).timestamp()) if dt else None})
    valid = [p for p in parsed if p["epoch"]]
    valid.sort(key=lambda p: p["epoch"])
    conflicts = []
    if valid:
        first, last = valid[0], valid[-1]
        span = last["epoch"] - first["epoch"]
        now = int(datetime.now(timezone.utc).timestamp())
        for p in valid:
            if p["epoch"] > now + 86400:
                conflicts.append({"severity": "عالية", "event": p["label"],
                                  "issue": f"طابع زمني في المستقبل ({p['parsed']}) — ساعة مضبوطة خطأً أو تلاعب متعمّد."})
            if p["epoch"] < 946684800:  # قبل 2000
                conflicts.append({"severity": "متوسطة", "event": p["label"],
                                  "issue": f"طابع زمني قديم جدًا ({p['parsed']}) — ساعة جهاز غير مضبوطة أو تزوير."})
        # تاريخ التعديل أقدم من الإنشاء
        by_label = {p["label"]: p for p in valid}
        orig = next((p for p in valid if "الالتقاط" in p["label"] or "Original" in p["source"]), None)
        mod = next((p for p in valid if "تعديل" in p["label"] or "Modify" in p["source"]), None)
        if orig and mod and mod["epoch"] < orig["epoch"] - 60:
            conflicts.append({"severity": "عالية", "event": "تسلسل زمني مقلوب",
                              "issue": f"تاريخ التعديل ({mod['parsed']}) أقدم من تاريخ الالتقاط ({orig['parsed']}) — "
                                       "تضارب منطقي يدل على تعديل الطوابع."})
        if orig and mod and mod["epoch"] - orig["epoch"] > 60:
            conflicts.append({"severity": "معلوماتية", "event": "فجوة بين الالتقاط والتعديل",
                              "issue": f"الملف عُدّل بعد الالتقاط بـ {_human(mod['epoch'] - orig['epoch'])}."})
        return {"events": valid, "unparsed": [p for p in parsed if not p["epoch"]],
                "span_seconds": span, "span_human": _human(span),
                "earliest": first, "latest": last, "conflicts": conflicts}
    return {"events": [], "unparsed": parsed, "conflicts": [],
            "note": "لم يُعثر على أي طابع زمني قابل للتحليل داخل الملف."}


def _human(sec: int) -> str:
    if sec < 60:
        return f"{sec} ثانية"
    if sec < 3600:
        return f"{sec // 60} دقيقة"
    if sec < 86400:
        return f"{sec // 3600} ساعة و{(sec % 3600) // 60} دقيقة"
    d = sec // 86400
    if d < 365:
        return f"{d} يوم"
    return f"{d // 365} سنة و{(d % 365)} يوم"
