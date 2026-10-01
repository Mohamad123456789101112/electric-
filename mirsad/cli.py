"""
واجهة سطر الأوامر لمِرصاد:
    python -m mirsad.cli <ملف> [--json out.json] [--html out.html] [--artifacts dir] [--quick]
    python -m mirsad.cli --compare a.jpg b.jpg
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from .core import analyzer, hashing, report as report_mod


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="مِرصاد — التحقيق الجنائي الرقمي")
    ap.add_argument("file", nargs="?", help="مسار الدليل")
    ap.add_argument("--json", help="حفظ التقرير JSON")
    ap.add_argument("--html", help="حفظ تقرير HTML")
    ap.add_argument("--artifacts", default="mirsad_artifacts", help="مجلد المخرجات البصرية")
    ap.add_argument("--quick", action="store_true", help="تحليل سريع بدون معالجة الصور الثقيلة")
    ap.add_argument("--compare", nargs=2, metavar=("A", "B"), help="مقارنة ملفين")
    a = ap.parse_args(argv)

    if a.compare:
        da = open(a.compare[0], "rb").read()
        db = open(a.compare[1], "rb").read()
        fa, fb = hashing.full_fingerprint(da), hashing.full_fingerprint(db)
        sim = hashing.fuzzy_compare(fa["ctph_fuzzy"], fb["ctph_fuzzy"])
        print(json.dumps({"a": fa, "b": fb, "identical": fa["sha256"] == fb["sha256"],
                          "similarity_percent": sim}, ensure_ascii=False, indent=1))
        return 0

    if not a.file:
        ap.print_help()
        return 2
    data = open(a.file, "rb").read()
    rep = analyzer.analyze(data, os.path.basename(a.file), a.artifacts, deep=not a.quick)
    print(report_mod.text_summary(rep))
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(rep, f, ensure_ascii=False, indent=1)
        print(f"\n[+] التقرير JSON: {a.json}")
    if a.html:
        with open(a.html, "w", encoding="utf-8") as f:
            f.write(report_mod.html_report(rep, artifacts_base=a.artifacts.rstrip("/") + "/"))
        print(f"[+] التقرير HTML: {a.html}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
