"""
اختبارات تحقق لمحركات مِرصاد — تقيس الكشف الصحيح وغياب الإنذارات الكاذبة
على عيّنات مُولّدة بخصائص معروفة مسبقًا (ground truth).

التشغيل:  .venv/bin/python tests/test_engines.py
"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mirsad.core import (analyzer, carver, entropy, exif as exif_mod, hashing,  # noqa: E402
                         imaging, jpeg as jpeg_mod, jpegdct, recovery, signatures)
import make_fixtures  # noqa: E402

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
TMP = tempfile.mkdtemp(prefix="mirsad_test_")
PASS, FAIL = [], []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(("  ✅ " if cond else "  ❌ ") + name + (f"  [{detail}]" if detail else ""))


def read(n: str) -> bytes:
    return open(os.path.join(FIX, n), "rb").read()


def main() -> int:
    if not os.path.exists(os.path.join(FIX, "original_with_exif.jpg")):
        make_fixtures.main()

    print("\n=== 1. البصمات والتجزئة السياقية ===")
    a = b"MIRSAD forensic evidence sample " * 200
    b = a[:3000] + b"X" + a[3001:]
    fa, fb = hashing.full_fingerprint(a), hashing.full_fingerprint(b)
    check("SHA-256 يطابق المرجع", fa["sha256"] == __import__("hashlib").sha256(a).hexdigest())
    check("الملفان المختلفان ببايت واحد لهما بصمتان مختلفتان", fa["sha256"] != fb["sha256"])
    sim = hashing.fuzzy_compare(fa["ctph_fuzzy"], fb["ctph_fuzzy"])
    check("التجزئة السياقية ترصد تشابهًا عاليًا رغم الاختلاف", sim >= 80, f"sim={sim}")
    check("تشابه بيانات غير مترابطة منخفض",
          hashing.fuzzy_compare(hashing.fuzzy_hash(a), hashing.fuzzy_hash(os.urandom(6000))) < 40)

    print("\n=== 2. تعريف النوع وكشف التمويه ===")
    t = signatures.identify(read("png_with_metadata.png"), "png_with_metadata.png")
    check("تعريف PNG صحيح", t.ext == "png" and not t.extension_mismatch)
    t2 = signatures.identify(read("disguised_file.txt"), "disguised_file.txt")
    check("كشف ملف PNG متنكر بامتداد .txt", t2.ext == "png" and t2.extension_mismatch)
    check("تعريف PDF", signatures.identify(read("document_with_js.pdf"), "x.pdf").ext == "pdf")

    print("\n=== 3. محلّل EXIF ===")
    jp = jpeg_mod.parse(read("original_with_exif.jpg"))
    ex = jp["app_payloads"]["Exif"]
    flat = exif_mod.flatten(ex)
    check("قراءة الصانع", flat.get("IFD0:Make") == "ARENA-CAM", str(flat.get("IFD0:Make")))
    check("قراءة الطراز", flat.get("IFD0:Model") == "MIRSAD-X1 Pro")
    check("قراءة الرقم التسلسلي للجسم", flat.get("ExifIFD:BodySerialNumber") == "SN-FORENSIC-00912")
    g = ex.get("GPS_decoded") or {}
    check("فك إحداثيات GPS بدقة", abs(g.get("latitude", 0) - 30.041253) < 1e-4
          and abs(g.get("longitude", 0) - 31.237733) < 1e-4, f"{g.get('latitude')},{g.get('longitude')}")
    check("ارتفاع GPS", abs((g.get("altitude_m") or 0) - 23) < 0.01)
    dts = exif_mod.exif_datetimes(ex)
    check("استخراج تواريخ EXIF", any(d["iso"].startswith("2024-03-15") for d in dts))

    print("\n=== 4. استرجاع الميتاداتا الممسوحة ===")
    stripped = read("stripped_metadata.jpg")
    jps = jpeg_mod.parse(stripped)
    check("الصورة الممسوحة بلا EXIF في موضعه", "Exif" not in jps["app_payloads"])
    wiped = read("wiped_but_recoverable.jpg")
    rec = recovery.analyze(wiped, "", jpeg_mod.parse(wiped))
    frags = rec["exif_fragments"]
    check("استرجاع شظية EXIF من ملف ممسوح", len(frags) >= 1, f"{len(frags)} شظية")
    if frags:
        f0 = frags[0]
        check("الشظية تحتوي الطراز الأصلي",
              any("MIRSAD-X1" in str(v) for v in f0["fields"].values()))
        check("الشظية تحتوي الموقع الجغرافي الأصلي",
              f0.get("gps") and abs(f0["gps"]["latitude"] - 30.041253) < 1e-4)
    check("استخراج صور مدمجة من الملف الأصلي",
          len(recovery.scan_embedded_jpegs(read("original_with_exif.jpg"))) >= 1)

    print("\n=== 5. كشف البيانات الملحقة والنحت ===")
    app = read("appended_zip.jpg")
    jpa = jpeg_mod.parse(app)
    check("رصد بيانات بعد نهاية JPEG", bool(jpa.get("trailing_data")))
    carved = carver.carve(app, TMP)
    check("نحت أرشيف ZIP المخبأ داخل الصورة",
          any(c["type"] == "zip" and c.get("extracted") for c in carved))
    zipf = [c for c in carved if c["type"] == "zip" and c.get("extracted")]
    if zipf:
        import zipfile
        z = zipfile.ZipFile(os.path.join(TMP, zipf[0]["file"]))
        check("الملف المنحوت أرشيف صالح يفتح ويحوي الرسالة",
              "secret.txt" in z.namelist() and "سرية" in z.read("secret.txt").decode("utf-8"))
    check("عدم وجود بيانات ملحقة في الملف النظيف",
          not jpeg_mod.parse(read("original_with_exif.jpg")).get("trailing_data"))

    print("\n=== 6. فكّ معاملات JPEG الحقيقية ===")
    dec = jpegdct.decode_coefficients(read("original_with_exif.jpg"))
    check("فكّ ترميز هوفمان ناجح", dec.get("ok"))
    check("تغطية كاملة للكتل", dec.get("coverage", 0) > 0.99, str(dec.get("coverage")))
    if dec.get("ok"):
        w = dec["frame"]["width"]
        check("أبعاد الإطار صحيحة", w == 640, str(w))

    print("\n=== 7. كشف الضغط المزدوج (أرضية الإنذار الكاذب) ===")
    img = make_fixtures.base_image(512, 384, seed=21)
    one = io.BytesIO(); img.save(one, "JPEG", quality=92)
    r1 = jpegdct.double_compression(one.getvalue())
    check("لا إنذار كاذب على صورة مضغوطة مرة واحدة", r1["flag_ratio"] < 0.15, str(r1["flag_ratio"]))
    tmp = io.BytesIO(); img.save(tmp, "JPEG", quality=60); tmp.seek(0)
    two = io.BytesIO(); Image.open(tmp).save(two, "JPEG", quality=92)
    r2 = jpegdct.double_compression(two.getvalue())
    check("كشف الضغط المزدوج (60 ← 92)", r2["flag_ratio"] >= 0.15, str(r2["flag_ratio"]))
    b1 = jpegdct.coefficient_stats(one.getvalue())["generalized_benford_fit"]["total_variation"]
    b2 = jpegdct.coefficient_stats(two.getvalue())["generalized_benford_fit"]["total_variation"]
    check("بنفورد يفرّق بين ضغط واحد ومزدوج", b2 > b1 * 2, f"{b1} ← {b2}")

    print("\n=== 8. كشف النسخ واللصق ===")
    clean = make_fixtures.base_image(512, 384, seed=5)
    cm_clean = imaging.copy_move(clean, TMP)
    check("لا إنذار كاذب على صورة سليمة", not cm_clean.get("detected"))
    arr = np.asarray(clean).copy()
    arr[240:340, 300:440] = arr[40:140, 40:180]
    cm_f = imaging.copy_move(Image.fromarray(arr), TMP)
    check("كشف منطقة منسوخة ملصوقة", cm_f.get("detected"),
          str(cm_f.get("top_shift_vectors", [])[:1]))

    print("\n=== 9. كشف الإخفاء LSB ===")
    base = np.asarray(make_fixtures.base_image(400, 300, seed=9))
    st_clean = imaging.lsb_analysis(Image.fromarray(base), TMP)
    check("لا إنذار كاذب للإخفاء على صورة سليمة",
          st_clean["chi_square"]["suspicious_fraction"] < 0.05,
          str(st_clean["chi_square"]["suspicious_fraction"]))
    flat_a = base.copy().reshape(-1)
    bits = np.random.default_rng(3).integers(0, 2, flat_a.size // 2).astype(np.uint8)
    flat_a[:bits.size] = (flat_a[:bits.size] & 0xFE) | bits
    st = imaging.lsb_analysis(Image.fromarray(flat_a.reshape(base.shape)), TMP)
    # في الصور ذات المدرّج الناعم يعجز اختبار كاي-تربيع بطبيعته، فيتكفّل تحليل RS بالكشف
    check("كشف إخفاء LSB بنسبة 50% (كاي-تربيع أو RS)",
          st["chi_square"]["suspicious_fraction"] > 0.1
          or st["rs_analysis"]["estimated_payload_ratio"] > 0.25,
          f"chi={st['chi_square']['suspicious_fraction']} rs={st['rs_analysis']['estimated_payload_ratio']}")
    check("تحليل RS يقدّر حمولة أعلى من أرضية الضجيج",
          st["rs_analysis"]["estimated_payload_ratio"] >
          st_clean["rs_analysis"]["estimated_payload_ratio"] + 0.1,
          f"{st_clean['rs_analysis']['estimated_payload_ratio']} ← {st['rs_analysis']['estimated_payload_ratio']}")

    print("\n=== 10. الإنتروبيا ===")
    check("إنتروبيا بيانات عشوائية ≈ 8", entropy.shannon(os.urandom(100000)) > 7.95)
    check("إنتروبيا نص منخفضة", entropy.shannon(b"A" * 10000) < 0.1)
    rnd = entropy.chi_square_uniform(os.urandom(200000))
    check("كاي-تربيع يصنّف العشوائي كمنتظم", rnd["chi2"] < 400, str(rnd["chi2"]))

    print("\n=== 11. المستندات ===")
    from mirsad.core import documents
    pdf = documents.parse_pdf(read("document_with_js.pdf"))
    check("قراءة ميتاداتا PDF", pdf["info"].get("Author") == "Investigator A", str(pdf["info"]))
    check("كشف التحديث التزايدي", pdf["incremental_updates"] >= 1)
    check("كشف جافاسكربت داخل PDF",
          any(r["marker"] == "/JavaScript" for r in pdf["risk_indicators"]))

    print("\n=== 12. التحليل الكامل من البداية للنهاية ===")
    rep = analyzer.analyze(read("original_with_exif.jpg"), "original_with_exif.jpg", TMP)
    check("التقرير بلا أخطاء وحدات", not rep["errors"], str(rep["errors"])[:200])
    check("مؤشر الشبهة منخفض للملف السليم", rep["assessment"]["suspicion_score"] <= 20,
          str(rep["assessment"]["suspicion_score"]))
    check("الميتاداتا مستخرجة", len(rep["metadata"]) > 20)
    check("الخط الزمني مبني", len(rep["timeline"]["events"]) >= 3)

    rep2 = analyzer.analyze(read("appended_zip.jpg"), "appended_zip.jpg", TMP)
    check("مؤشر الشبهة مرتفع للملف المخبأ فيه أرشيف",
          rep2["assessment"]["suspicion_score"] >= 30, str(rep2["assessment"]["suspicion_score"]))
    rep3 = analyzer.analyze(read("wiped_but_recoverable.jpg"), "wiped_but_recoverable.jpg", TMP)
    check("رصد آثار ميتاداتا ممسوحة في التقييم",
          any("ممسوحة" in f["title"] for f in rep3["assessment"]["findings"]))

    print("\n=== 13. فكّ MakerNote (بصمة الجهاز) ===")
    from mirsad.core import makernote as mn_mod

    can = mn_mod.analyze(read("makernote_canon.jpg"))
    can0 = can["makernotes"][0]
    check("كانون: التعرّف على المصنّع", can0["vendor"] == "Canon")
    check("كانون: الرقم التسلسلي للجسم",
          can0["identity"]["الرقم التسلسلي للكاميرا"]["value"] == "1230405678")
    check("كانون: الرقم التسلسلي الداخلي",
          can0["identity"]["الرقم التسلسلي الداخلي"]["value"] == "IS0123456789ABCD")
    cs = can0["interpreted"]["إعدادات الكاميرا لحظة الالتقاط"]
    check("كانون: فكّ مصفوفة CameraSettings (البؤرة)",
          cs["MinFocalLength_mm"] == 24.0 and cs["MaxFocalLength_mm"] == 70.0, str(cs)[:120])
    check("كانون: تحويل MaxAperture إلى f-stop", cs["MaxAperture_fstop"] == 2.8)

    nik = mn_mod.analyze(read("makernote_nikon.jpg"))["makernotes"][0]
    check("نيكون: ترويسة TIFF مستقلة (مرجع إزاحات داخلي)",
          nik["offset_base"].startswith("ترويسة TIFF مستقلة"))
    check("نيكون: عدّاد الغالق",
          nik["identity"]["عدّاد الغالق (عدد الصور طوال عمر الجسم)"]["value"] == 48213)
    check("نيكون: الرقم التسلسلي", nik["identity"]["الرقم التسلسلي للكاميرا"]["value"] == "6001234")
    check("نيكون: قراءة بيانات العدسة من RATIONAL",
          nik["identity"]["العدسة"]["value"].startswith("24-70mm"))

    app = mn_mod.analyze(read("makernote_apple.jpg"))["makernotes"][0]
    check("آبل: ترتيب بايتات Big Endian داخل كتلة Little Endian",
          app["byte_order"] == "Big Endian")
    rt = app["identity"]["زمن تشغيل الجهاز لحظة الالتقاط"]
    check("آبل: فكّ bplist داخل وسم RunTime",
          abs(rt["device_uptime_seconds"] - 123456.789) < 0.01, str(rt)[:120])
    check("آبل: معرّف المحتوى (Live Photo)",
          app["identity"]["معرّف المحتوى (يربط الصورة بفيديو Live Photo)"]["value"].startswith("9A8B"))
    av = app["identity"]["اتجاه الجهاز لحظة الالتقاط (متجه التسارع)"]["value"]
    check("آبل: متجه التسارع موقَّع (SRATIONAL)", av[1] < 0 and abs(av[1] + 0.9512) < 1e-6, str(av))

    son = mn_mod.analyze(read("makernote_sony.jpg"))["makernotes"][0]
    check("سوني: قراءة الوسوم بعد ترويسة SONY DSC", son["vendor"] == "Sony" and son["tag_count"] == 8)
    check("سوني: الإقرار بالكتل المُعمّاة بدل تخمينها",
          "_encrypted_note" in son["identity"])

    check("لا MakerNote في صورة ممسوحة",
          mn_mod.analyze(read("stripped_metadata.jpg"))["present"] is False)
    check("MakerNote يمر عبر JSON بلا أخطاء",
          isinstance(json.dumps(analyzer.jsonable(can), ensure_ascii=False), str))

    repm = analyzer.analyze(read("makernote_nikon.jpg"), "makernote_nikon.jpg", TMP)
    check("ربط MakerNote بالتقرير بلا أخطاء وحدات", not repm["errors"], str(repm["errors"])[:200])
    check("حقول الجهاز تظهر في جدول الميتاداتا الموحّد",
          any(k.startswith("🔧") for k in repm["metadata"]))
    check("فكّ MakerNote لا يرفع مؤشر الشبهة لصورة سليمة",
          repm["assessment"]["suspicion_score"] <= 20,
          str(repm["assessment"]["suspicion_score"]))

    print("\n=== 14. بصمة ضجيج المستشعر PRNU ===")
    import math as _math
    import tempfile as _tf
    from mirsad.core import prnu as prnu_mod
    from prnu_validation import capture as _capture, smooth_scene as _scene

    # (أ) صحة مرشّحات دوبيشي المحسوبة عدديًا
    for nvm in (2, 4, 8):
        hh, gg = prnu_mod.daubechies(nvm)
        check(f"db{nvm}: مجموع المرشّح = √2",
              abs(hh.sum() - _math.sqrt(2)) < 1e-10)
        check(f"db{nvm}: طاقة المرشّح = 1", abs(np.linalg.norm(hh) - 1) < 1e-10)
        orth = max(abs(float(np.dot(hh[2 * k:], hh[:len(hh) - 2 * k])))
                   for k in range(1, len(hh) // 2))
        check(f"db{nvm}: تعامد الإزاحات الزوجية", orth < 1e-9, f"{orth:.2e}")
        mom = max(abs(sum(gg[k] * (k ** mm) for k in range(len(gg))))
                  for mm in range(nvm))
        check(f"db{nvm}: تلاشي أول {nvm} عزوم", mom < 1e-6, f"{mom:.2e}")

    rngp = np.random.default_rng(7)
    xx = rngp.random((64, 96)) * 255
    hh, gg = prnu_mod.daubechies(8)
    err = float(np.abs(xx - prnu_mod.waverec2(prnu_mod.wavedec2(xx, 4, hh, gg), hh, gg)).max())
    check("تحويل المويجات: إعادة بناء تامة (4 مستويات)", err < 1e-6, f"{err:.2e}")

    # (ب) تجربة مرجعية كاملة بنموذج المستشعر الفيزيائي I = I⁰(1+K) + Θ
    S = 256
    rngp = np.random.default_rng(2024)
    K_A = rngp.normal(0, 0.02, (S, S))
    K_B = rngp.normal(0, 0.02, (S, S))
    flats = [_capture(_scene(rngp, S, S, "flat"), K_A, rngp) for _ in range(10)]
    fpr = prnu_mod.fingerprint_from_images(flats, crop=S)
    check("بناء بصمة الكاميرا من صور مرجعية", fpr["ok"] and fpr["n_images"] == 10)
    Kest = fpr["fingerprint"].astype(float)
    corr_true = float(np.corrcoef(Kest.ravel(), prnu_mod.zero_mean(K_A).ravel())[0, 1])
    corr_false = float(np.corrcoef(Kest.ravel(), prnu_mod.zero_mean(K_B).ravel())[0, 1])
    check("البصمة المستخرجة ترتبط بالنمط الحقيقي", corr_true > 0.3, f"{corr_true:.3f}")
    check("ولا ترتبط بنمط مستشعر آخر", abs(corr_false) < 0.05, f"{corr_false:.3f}")

    same = prnu_mod.match_image(Kest, _capture(_scene(rngp, S, S, "scene"), K_A, rngp))
    other = prnu_mod.match_image(Kest, _capture(_scene(rngp, S, S, "scene"), K_B, rngp))
    check("PCE يتجاوز عتبة التطابق القوي لنفس المستشعر",
          same["pce"] >= 60 and same["level"] == "strong", f"{same['pce']:.1f}")
    check("PCE تحت العتبة لمستشعر مختلف (لا إنذار كاذب)",
          other["pce"] < 25 and other["level"] in ("none", "weak"), f"{other['pce']:.1f}")
    check("الصورة من نفس المستشعر بعد ضغط JPEG 70 تظل مُطابَقة",
          prnu_mod.match_image(
              Kest, _capture(_scene(rngp, S, S, "scene"), K_A, rngp, quality=70))["pce"] >= 60)

    # (ج) كشف القصّ عبر موضع قمة الارتباط
    BIG = S + 80
    K_big = rngp.normal(0, 0.02, (BIG, BIG))
    o = (BIG - S) // 2
    K_big[o:o + S, o:o + S] = K_A
    bigb = _capture(_scene(rngp, BIG, BIG, "scene"), K_big, rngp)
    _im = Image.open(io.BytesIO(bigb)).crop((0, 0, S + 40, S + 40))
    _b = io.BytesIO(); _im.save(_b, "JPEG", quality=95)
    sh = prnu_mod.match_image(Kest, _b.getvalue())
    check("كشف القصّ: القمة تنزاح عن (0,0) مع بقاء التعرّف على الكاميرا",
          sh["level"] == "strong_shifted" and sh["detected_shift"] == [20, 20],
          f"{sh['level']} shift={sh.get('detected_shift')} pce={sh['pce_best_shift']:.0f}")

    # (د) سجل الكاميرات الدائم على القرص
    with _tf.TemporaryDirectory() as _d:
        reg = prnu_mod.CameraRegistry(_d)
        added = reg.add("cam_a", "كاميرا الاختبار A", flats, crop=S)
        check("تسجيل كاميرا وحفظ بصمتها", added["ok"] and len(reg.list()) == 1)
        ident = reg.identify(_capture(_scene(rngp, S, S, "scene"), K_A, rngp))
        check("السجل يتعرّف على الكاميرا بالاسم",
              ident.get("matched_camera") == "كاميرا الاختبار A", str(ident.get("verdict"))[:90])
        ident2 = reg.identify(_capture(_scene(rngp, S, S, "scene"), K_B, rngp))
        check("السجل لا ينسب صورة كاميرا أخرى خطأً",
              not ident2.get("matched_camera"), str(ident2.get("verdict"))[:90])
        rep_p = analyzer.analyze(_capture(_scene(rngp, S, S, "scene"), K_A, rngp),
                                 "prnu_case.jpg", TMP, prnu_registry=reg)
        check("ربط PRNU بالتقرير الكامل بلا أخطاء", not rep_p["errors"], str(rep_p["errors"])[:150])
        check("نتيجة التعرّف تظهر داخل التقرير",
              (rep_p["image_forensics"]["prnu"]["identification"].get("matched_camera")
               == "كاميرا الاختبار A"))
        check("التعرّف على الكاميرا لا يرفع مؤشر الشبهة",
              all(f["weight"] == 0 for f in rep_p["assessment"]["findings"]
                  if "PRNU" in f["title"]))
        check("حذف الكاميرا من السجل", reg.delete("cam_a") and reg.list() == [])

    print("\n=== 15. بصمة الضغط وجداول التكميم ===")
    import tempfile as _tf2
    from mirsad.core import qtables as QT
    from mirsad.core import jpeg as JP
    from mirsad.core.jpeg import STD_LUMA as _SL, STD_CHROMA as _SC

    def _enc(im, **kw):
        """ترميز إلى ملف مؤقّت (مسار الذاكرة في Pillow يفشل مع بعض التوليفات)."""
        pth = os.path.join(TMP, "enc_tmp.jpg")
        im.save(pth, "JPEG", **kw)
        with open(pth, "rb") as fh:
            return fh.read()

    _img = Image.fromarray(
        (np.random.default_rng(4).random((128, 128, 3)) * 180 + 40).astype("uint8"))

    # (أ) مطابقة معادلة IJG لمخرجات libjpeg الفعلية عند كل جودة
    mism = []
    for qq in range(1, 101):
        jpx = JP.parse(_enc(_img, quality=qq, subsampling=2))
        for t in jpx["quant_tables"]:
            e = QT.quality_of_table(t["values"], chroma=t["table_id"] != 0)
            if not e["exact_ijg_match"]:
                mism.append((qq, t["table_id"], e["max_deviation"]))
            elif e["quality"] != qq and not e.get("ambiguous"):
                mism.append((qq, t["table_id"], "quality=" + str(e["quality"])))
    check("معادلة تدرّج IJG تطابق libjpeg في كل الجودات 1..100 (جدولان)",
          not mism, str(mism[:5]))

    # (ب) فكّ ترتيب الزجزاج (أساس صحة كل ما سبق)
    zz = QT.from_zigzag(list(range(64)))
    check("فكّ ترتيب الزجزاج يعيد الموضع الصحيح",
          zz[0] == 0 and zz[1] == 1 and zz[8] == 2 and zz[16] == 3, str(zz[:9]))
    check("جدول Annex K المرجعي يطابق مخرجات libjpeg عند الجودة 50",
          QT.ijg_scale(_SL, 50) == _SL and QT.ijg_scale(_SC, 50) == _SC)

    # (ج) بصمات جداول هوفمان القياسية مُعاد توليدها لا محفوظة اعتباطًا
    jp_std = JP.parse(_enc(_img, quality=80, optimize=False))
    regen = {f"{h['class']}{h['table_id']}": h["sha1"] for h in jp_std["huffman_tables"]}
    check("بصمات هوفمان القياسية المخزَّنة = المُولَّدة من libjpeg الآن",
          regen == QT.STD_HUFFMAN_SHA1, str(regen))
    sig_std = QT.compression_signature(jp_std)
    check("رصد جداول هوفمان القياسية", sig_std["huffman_standard"])
    jp_opt = JP.parse(_enc(_img, quality=80, optimize=True))
    check("رصد جداول هوفمان المُحسَّنة",
          QT.compression_signature(jp_opt)["huffman_optimized"])

    # (د) البصمة خاصية للمُرمِّز لا للمحتوى
    img2 = Image.fromarray(
        (np.random.default_rng(55).random((96, 160, 3)) * 255).astype("uint8"))
    a = QT.compression_signature(JP.parse(_enc(_img, quality=77, subsampling=2)))
    b = QT.compression_signature(JP.parse(_enc(img2, quality=77, subsampling=2)))
    check("نفس الإعدادات + صورتان مختلفتان ⇒ نفس التوقيع الكامل",
          a["full_signature"] == b["full_signature"])
    c2 = QT.compression_signature(JP.parse(_enc(_img, quality=78, subsampling=2)))
    check("تغيير الجودة درجة واحدة ⇒ توقيع مختلف",
          a["full_signature"] != c2["full_signature"])
    d2 = QT.compression_signature(JP.parse(_enc(_img, quality=77, subsampling=0)))
    check("تغيير تخفيض اللون ⇒ توقيع مختلف مع بقاء جداول التكميم",
          d2["full_signature"] != a["full_signature"]
          and d2["qt_signature"] == a["qt_signature"])

    # (هـ) قاعدة البصمات المُرفقة والتعلّم
    db0 = QT.SignatureDB()
    check("قاعدة البصمات المُرفقة محمّلة", len(db0.entries) >= 50, str(len(db0.entries)))
    check("كل مُدخَل مُرفق موثّق المصدر (provenance)",
          all(e.get("provenance") for e in db0.entries))
    m_known = db0.match(JP.parse(_enc(img2, quality=85, subsampling=2, optimize=False)))
    check("التعرّف على مُرمِّز معروف من قاعدة البصمات",
          bool(m_known["exact_matches"]), str(m_known["confidence"]))

    with _tf2.TemporaryDirectory() as _d2:
        upath = os.path.join(_d2, "user.json")
        db = QT.SignatureDB(user_path=upath)
        ref = JP.parse(_enc(_img, quality=71, subsampling=2, optimize=True))
        got = db.learn(ref, "جهاز اختبار", "عيّنة مُولَّدة محليًا في الاختبار")
        check("تعلّم بصمة من عيّنة مرجعية", got["ok"])
        db2 = QT.SignatureDB(user_path=upath)
        unk = JP.parse(_enc(img2, quality=71, subsampling=2, optimize=True))
        mm = db2.match(unk)
        check("مطابقة صورة أخرى بنفس المُرمِّز عبر توقيع الملمح",
              mm["identified_source"] == "جهاز اختبار", str(mm["confidence"]))
        mm2 = db2.match(JP.parse(_enc(img2, quality=40, subsampling=0)))
        check("لا تُنسب صورة مُرمِّزها مختلف إلى الجهاز",
              mm2.get("identified_source") != "جهاز اختبار", str(mm2.get("identified_source")))
        check("حذف توقيع المحقق من القاعدة", db2.delete(got["full_signature"]))

    # (و) الاستدلال البنيوي والتكامل مع التقرير
    prog = QT.analyze(JP.parse(_enc(_img, quality=80, progressive=True)), None)
    check("رصد الترميز التقدمي كمؤشر إعادة ترميز",
          any("تقدمي" in f["fact"] for f in prog["structural_inference"]))
    rep_q = analyzer.analyze(_enc(_img, quality=77, subsampling=2), "q.jpg", TMP,
                             signature_db=db0)
    check("بصمة الضغط مدمجة في التقرير بلا أخطاء",
          rep_q["compression_signature"]["ok"] and not rep_q["errors"],
          str(rep_q["errors"])[:150])
    check("الجودة المقيسة في التقرير صحيحة",
          rep_q["compression_signature"]["quantization"]["quality_estimate"] == 77)
    check("تحديد المُرمِّز لا يرفع مؤشر الشبهة",
          all(f["weight"] == 0 for f in rep_q["assessment"]["findings"]
              if "بصمة الضغط" in f["title"]))

    print("\n=== 16. تحديد الموقع الجغرافي ===")
    from mirsad.core import geo as GEO

    # (أ) تحقق من الخوارزميات بأمثلة مرجعية منشورة عالميًا
    check("Geohash يطابق المثال المرجعي المنشور",
          GEO.geohash(57.64911, 10.40744, 11) == "u4pruydqqvj",
          GEO.geohash(57.64911, 10.40744, 11))
    check("Plus Code يطابق المثال المرجعي المنشور",
          GEO.plus_code(47.365590, 8.524997, 10) == "8FVC9G8F+6X",
          GEO.plus_code(47.365590, 8.524997, 10))
    for la, lo in ((30.0444, 31.2357), (-33.8688, 151.2093), (0.0, 0.0), (-89.9, 179.9)):
        code = GEO.plus_code(la, lo, 11)
        back = GEO.decode_plus_code(code)
        check(f"دورة ترميز/فكّ Plus Code عند ({la},{lo}) بخطأ < 5 م",
              back is not None and GEO.haversine_m((la, lo), back) < 5,
              f"{code} -> {back}")
    check("منطقة UTM للقاهرة = 36R", GEO.utm_zone(30.0444, 31.2357)["label"] == "36R")
    check("استثناء النرويج في شبكة UTM", GEO.utm_zone(60.0, 5.0)["zone"] == 32)
    check("مسافة القاهرة–الإسكندرية ≈ 180 كم",
          178 < GEO.haversine_m((30.0444, 31.2357), (31.2001, 29.9187)) / 1000 < 182)
    check("الاتجاه من القاهرة للإسكندرية شمال غربي",
          "شمال غرب" in GEO.compass_16(GEO.bearing_deg((30.0444, 31.2357), (31.2001, 29.9187))))
    check("تحويل DMS صحيح", GEO.to_dms(30.0444, True).startswith("30°02'"))
    check("ISO 6709 بالصيغة العشرية",
          abs(GEO.parse_iso6709("+30.0444+031.2357/")["latitude"] - 30.0444) < 1e-9)
    check("ISO 6709 بصيغة الدرجات والدقائق المضغوطة",
          abs(GEO.parse_iso6709("+3002.664+03114.142/")["latitude"] - 30.0444) < 1e-4)
    check("رفض الإحداثيات خارج النطاق", not GEO.valid_point(95.0, 10.0))

    # (ب) صورة بحقول GPS كاملة
    gf = analyzer.analyze(read("geo_gps_full.jpg"), "geo_gps_full.jpg", TMP)
    gg = gf["geolocation"]
    check("استخراج الموقع من EXIF GPS", gg["located"], str(gg.get("verdict"))[:80])
    gp = gg["primary"]
    check("دقة خط العرض المستخرج", abs(gp["latitude"] - 30.0412528) < 1e-6, str(gp["latitude"]))
    check("دقة خط الطول المستخرج", abs(gp["longitude"] - 31.2377333) < 1e-6, str(gp["longitude"]))
    check("قراءة الارتفاع", abs(gp["altitude_m"] - 23.4) < 0.01)
    check("قراءة عدد الأقمار و DOP", gp["satellites"] == "09" and gp["dop"] == 1.2)
    check("تحديد نوع التثبيت من GPSProcessingMethod",
          gp.get("fix_type") == "قمر صناعي مباشر", str(gp.get("fix_type")))
    check("قراءة السرعة لحظة الالتقاط", abs(gp["speed_kmh"] - 4.2) < 0.01)
    check("قراءة اتجاه عدسة الكاميرا",
          abs(gp["camera_direction_deg"] - 287.5) < 0.01 and "غرب" in gp["camera_direction_text"])
    check("ثقة عالية لتثبيت سليم", gp["confidence"]["score"] >= 80, str(gp["confidence"]))
    check("لا تناقضات في الصورة السليمة", not gg["consistency_checks"],
          str(gg["consistency_checks"])[:120])
    check("الموقع لا يرفع مؤشر الشبهة بذاته",
          all(f["weight"] == 0 for f in gf["assessment"]["findings"] if "موقع جغرافي" in f["title"]))

    # (ج) موقع مزوَّر: ثلاثة تناقضات مستقلة
    gt = analyzer.analyze(read("geo_gps_tampered.jpg"), "geo_gps_tampered.jpg", TMP)["geolocation"]
    notes = " | ".join(x["note"] for x in gt["consistency_checks"])
    check("كشف الإحداثيات المُقرّبة يدويًا", "مُقرّبة" in notes, notes[:100])
    check("كشف تضارب تاريخ GPS مع تاريخ الالتقاط", "تاريخ GPS" in notes)
    check("كشف تناقض فرق التوقيت مع خط الطول", "فرق التوقيت" in notes)
    check("خفض الثقة للتثبيت اليدوي عديم الإشارة",
          gt["primary"]["confidence"]["score"] <= 20, str(gt["primary"]["confidence"]["score"]))
    check("تمييز الإدخال اليدوي", gt["primary"].get("fix_type") == "أُدخل يدويًا")

    # (د) فيديو MP4 بصندوق موقع ISO 6709
    gv = analyzer.analyze(read("geo_video.mp4"), "geo_video.mp4", TMP)["geolocation"]
    check("استخراج الموقع من صندوق ©xyz في MP4",
          gv["located"] and abs(gv["primary"]["latitude"] - 31.2001) < 1e-3,
          str(gv.get("verdict"))[:90])

    # (هـ) نصوص وروابط
    gh = analyzer.analyze(read("geo_report.html"), "geo_report.html", TMP)["geolocation"]
    srcs = " | ".join(p["source"] for p in gh["points"])
    check("استخراج إحداثيات من رابط خرائط جوجل", "جوجل" in srcs, srcs[:120])
    check("استخراج إحداثيات من رابط geo:", "geo:" in srcs)
    check("استخراج إحداثيات بصيغة درجات/دقائق/ثوانٍ من النص", "درجات" in srcs)
    check("فكّ Plus Code مكتوب داخل النص", "Plus Code" in srcs)
    inds = {i["type"]: i for i in gh["indirect_indicators"]}
    check("رصد مفتاح الهاتف الدولي المصري",
          inds.get("مفتاح هاتف دولي", {}).get("country") == "مصر")
    check("رصد نطاق إنترنت مصري",
          inds.get("نطاق إنترنت لدولة", {}).get("country") == "مصر")
    check("رصد معرّفات شبكة (MAC) كمؤشر موقع خارجي",
          "عناوين MAC / معرّفات نقاط واي-فاي" in inds)
    check("رصد تباعد النقاط داخل الملف الواحد",
          any("متباعد" in x["note"] for x in gh["consistency_checks"]))

    # (و) أهم حالة: موقع من ميتاداتا ممسوحة
    gw = analyzer.analyze(read("wiped_but_recoverable.jpg"), "wiped.jpg", TMP)["geolocation"]
    check("استخراج الموقع من شظية EXIF مُستعادة بعد المسح",
          gw["located"] and "مُستعادة" in (gw["primary"].get("kind") or ""),
          str(gw.get("verdict"))[:110])

    # (ز) ملف بلا أي موقع
    gn = analyzer.analyze(read("stripped_metadata.jpg"), "stripped.jpg", TMP)["geolocation"]
    check("لا إنذار كاذب لملف بلا موقع",
          not gn["located"] and not gn["indirect_indicators"], str(gn.get("verdict"))[:80])

    # (ح) تجميع مواقع أدلة القضية
    cl = GEO.cluster([
        {"latitude": 30.0444, "longitude": 31.2357, "label": "أ"},
        {"latitude": 30.0445, "longitude": 31.2358, "label": "ب"},
        {"latitude": 31.2001, "longitude": 29.9187, "label": "ج"},
    ])
    check("تجميع الأدلة المتجاورة في تجمّع واحد وفصل البعيدة",
          cl["count"] == 2 and max(c["size"] for c in cl["clusters"]) == 2, str(cl["count"]))
    check("قياس أقصى تباعد بين أدلة القضية",
          178000 < cl["max_separation_m"] < 182000, str(cl["max_separation_m"]))

    print("\n" + "=" * 60)
    print(f"النتيجة: {len(PASS)} ناجح / {len(FAIL)} فاشل")
    if FAIL:
        print("الاختبارات الفاشلة:")
        for f in FAIL:
            print("  -", f)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
