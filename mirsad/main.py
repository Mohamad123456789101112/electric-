"""
مِرصاد — منظومة التحقيق الجنائي الرقمي
واجهة الويب + واجهة برمجية REST (FastAPI).
"""
from __future__ import annotations

import io
import json
import os
import zipfile
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

from .core import (analyzer, geo as geo_mod, hashing, prnu as prnu_mod,
                   qtables as qtables_mod, report as report_mod)
from .core.case import CaseStore

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_ROOT = os.environ.get("MIRSAD_DATA", os.path.join(os.path.dirname(ROOT), "data"))
MAX_UPLOAD = int(os.environ.get("MIRSAD_MAX_UPLOAD_MB", "512")) * 1024 * 1024

store = CaseStore(DATA_ROOT)
cameras = prnu_mod.CameraRegistry(os.path.join(DATA_ROOT, "prnu_cameras"))
SIGDB_USER = os.path.join(DATA_ROOT, "jpeg_signatures_user.json")


def sigdb() -> qtables_mod.SignatureDB:
    """تُقرأ القاعدة في كل طلب حتى تظهر الإضافات الجديدة فورًا."""
    return qtables_mod.SignatureDB(user_path=SIGDB_USER)
app = FastAPI(title="مِرصاد — منظومة التحقيق الجنائي الرقمي", version="1.0.0",
              description="تحليل جنائي رقمي حقيقي للملفات: بصمات، ميتاداتا، استرجاع، تزوير، إخفاء.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

WEB = os.path.join(ROOT, "web")
app.mount("/static", StaticFiles(directory=os.path.join(WEB, "static")), name="static")


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    with open(os.path.join(WEB, "index.html"), encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "name": "mirsad", "version": app.version,
            "data_root": DATA_ROOT, "max_upload_bytes": MAX_UPLOAD}


# ------------------------------------------------------------------- القضايا

@app.get("/api/cases")
def list_cases() -> list:
    return store.list_cases()


@app.post("/api/cases")
def create_case(number: str = Form(...), title: str = Form(""), investigator: str = Form(""),
                authority: str = Form(""), notes: str = Form("")) -> dict:
    return store.create_case(number, title, investigator, authority, notes)


@app.get("/api/cases/{cid}")
def get_case(cid: str) -> dict:
    c = store.get_case(cid)
    if not c:
        raise HTTPException(404, "القضية غير موجودة")
    c["evidence"] = store.list_evidence(cid)
    c["custody"] = store.custody_log(cid)
    c["chain"] = store.verify_chain(cid)
    return c


@app.delete("/api/cases/{cid}")
def delete_case(cid: str) -> dict:
    store.delete_case(cid)
    return {"deleted": cid}


@app.get("/api/cases/{cid}/chain")
def chain(cid: str) -> dict:
    return store.verify_chain(cid)


# -------------------------------------------------------------------- التحليل

@app.post("/api/analyze")
async def analyze_upload(file: UploadFile = File(...),
                         case_id: Optional[str] = Form(None),
                         actor: str = Form("محقق"),
                         source_note: str = Form(""),
                         deep: bool = Form(True)) -> JSONResponse:
    data = await file.read()
    if not data:
        raise HTTPException(400, "الملف فارغ")
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, f"حجم الملف يتجاوز الحد ({MAX_UPLOAD // (1024*1024)} م.بايت)")
    fp = hashing.full_fingerprint(data)
    cid = case_id or None
    if cid and not store.get_case(cid):
        cid = None
    eid = store.add_evidence(cid, file.filename or "evidence.bin", data, fp,
                             file.content_type or "", actor, source_note)
    artifacts = store.artifacts_dir(eid)
    rep = analyzer.analyze(data, file.filename or "evidence.bin", artifacts, deep=deep,
                           prnu_registry=cameras, signature_db=sigdb())
    rep["evidence"]["evidence_id"] = eid
    rep["evidence"]["case_id"] = cid
    store.save_report(eid, rep)
    store.log(cid, eid, actor, "تحليل آلي كامل",
              f"مؤشر الشبهة: {(rep.get('assessment') or {}).get('suspicion_score')} | "
              f"عدد المؤشرات: {(rep.get('assessment') or {}).get('findings_count')}")
    return JSONResponse(rep)


# ------------------------------------------- قواعد SQLite (رسائل/سجلات محذوفة)

@app.post("/api/sqlite/analyze")
async def sqlite_analyze(file: UploadFile = File(...),
                         wal: Optional[UploadFile] = File(None),
                         journal: Optional[UploadFile] = File(None),
                         recover: bool = Form(True)) -> JSONResponse:
    """
    تحليل قاعدة SQLite مع ملفّيها المصاحبين.

    ارفع الثلاثة معًا متى توفّرت: ملف `-wal` يحمل نسخًا أحدث أو أقدم من
    الصفحات، وملف `-journal` يحمل صور الصفحات **قبل** التعديل. تجاهلهما
    يعني فقدان جزء من الأدلة.
    """
    from .core import sqlitef as sq
    data = await file.read()
    if not data:
        raise HTTPException(400, "الملف فارغ")
    if data[:16] != b"SQLite format 3\x00":
        raise HTTPException(400, "الملف ليس قاعدة SQLite")
    wal_b = await wal.read() if wal is not None else None
    jrn_b = await journal.read() if journal is not None else None
    out = sq.analyze(data, wal=wal_b or None, journal=jrn_b or None,
                     recover=bool(recover))
    store.log(None, None, "محقق", "تحليل قاعدة SQLite",
              f"{file.filename} | محذوفة: {out.get('deleted_count')}")
    return JSONResponse(analyzer.jsonable(out))


# ----------------------------------------------------- تحديد الموقع الجغرافي

@app.post("/api/geo/locate")
async def geo_locate(file: UploadFile = File(...)) -> JSONResponse:
    """
    تحديد موقع ملف واحد بسرعة (بلا تحليل جنائي كامل).

    يمسح: GPS في EXIF، صناديق الموقع في الفيديو، XMP/IPTC، النصوص والروابط،
    وكذلك شظايا الميتاداتا الممسوحة التي يستعيدها محرّك الاسترجاع.
    """
    data = await file.read()
    if not data:
        raise HTTPException(400, "الملف فارغ")
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "حجم الملف يتجاوز الحد")
    from .core import containers as cont_mod, jpeg as jpeg_mod, recovery as rec_mod
    c: dict = {}
    if data[:2] == b"\xFF\xD8":
        c["jpeg"] = jpeg_mod.parse(data)
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        c["png"] = cont_mod.parse_png(data)
    if data[:4] == b"RIFF":
        c["riff"] = cont_mod.parse_riff(data)
    if len(data) > 12 and data[4:8] in (b"ftyp", b"moov", b"mdat", b"styp", b"free"):
        c["iso_bmff"] = cont_mod.parse_bmff(data)
    if data[:4] in (b"II*\x00", b"MM\x00*"):
        from .core import exif as exif_mod
        c["tiff"] = exif_mod.parse_tiff(data, 0)
    try:
        txt = data[:4_000_000].decode("utf-8", "ignore")
    except Exception:
        txt = ""
    rec = rec_mod.analyze(data, txt, c.get("jpeg"))
    rec.pop("_embedded_image_bytes", None)
    out = geo_mod.analyze(c, None, rec, txt)
    out["file"] = {"name": file.filename, "size": len(data),
                   "sha256": hashing.crypto_hashes(data)["sha256"]}
    return JSONResponse(analyzer.jsonable(out))


@app.get("/api/cases/{cid}/map")
def case_map(cid: str) -> dict:
    """كل مواقع أدلة القضية مجمّعة مكانيًا على خريطة واحدة."""
    case = store.get_case(cid)
    if not case:
        raise HTTPException(404, "القضية غير موجودة")
    pts = []
    for ev in store.list_evidence(cid):
        rep = store.load_report(ev["id"])
        if not rep:
            continue
        g = (rep.get("geolocation") or {})
        for p in g.get("points", []):
            pts.append({"latitude": p["latitude"], "longitude": p["longitude"],
                        "label": ev.get("filename"), "evidence_id": ev["id"],
                        "source": p.get("source"), "kind": p.get("kind"),
                        "confidence": (p.get("confidence") or {}).get("score"),
                        "formats": p.get("formats")})
    cl = geo_mod.cluster(pts)
    return {"case": case.get("number"), "points": pts, "points_count": len(pts),
            **cl,
            "verdict": (f"أدلة القضية تحمل {len(pts)} موقعًا في "
                        f"{cl['count']} تجمّعًا مكانيًا"
                        + (f"، وأقصى تباعد بينها {cl['max_separation_m'] / 1000:.2f} كم."
                           if cl.get("max_separation_m") else ".")
                        ) if pts else "لا توجد مواقع في أدلة هذه القضية."}


# ------------------------------------------- قاعدة بصمات الضغط (جداول التكميم)

@app.get("/api/signatures")
def sig_list() -> dict:
    db = sigdb()
    return {"count": len(db.entries), "signatures": db.list()}


@app.post("/api/signatures/learn")
async def sig_learn(source: str = Form(...),
                    provenance: str = Form(...),
                    notes: str = Form(""),
                    file: UploadFile = File(...)) -> JSONResponse:
    """
    تعلّم بصمة ضغط من عيّنة مرجعية موثّقة.

    `provenance` إلزامي: من أين أتت العيّنة بالضبط (جهاز بحوزة المحقق، تطبيق
    بإصدار معيّن…). بلا توثيق المصدر لا قيمة قضائية للنسبة.
    """
    data = await file.read()
    if not data:
        raise HTTPException(400, "الملف فارغ")
    from .core import jpeg as jpeg_mod
    jp = jpeg_mod.parse(data)
    if not jp.get("is_jpeg"):
        raise HTTPException(400, "العيّنة ليست ملف JPEG")
    res = sigdb().learn(jp, source, provenance, notes)
    if not res.get("ok"):
        raise HTTPException(400, res.get("reason", "تعذّر التسجيل"))
    store.log(None, None, "محقق", "تسجيل بصمة ضغط مرجعية",
              f"{source} ← {provenance}")
    return JSONResponse(res)


@app.delete("/api/signatures/{full_signature}")
def sig_delete(full_signature: str) -> dict:
    return {"deleted": sigdb().delete(full_signature)}


@app.post("/api/signatures/identify")
async def sig_identify(file: UploadFile = File(...)) -> JSONResponse:
    data = await file.read()
    from .core import jpeg as jpeg_mod
    jp = jpeg_mod.parse(data)
    if not jp.get("is_jpeg"):
        raise HTTPException(400, "ليس ملف JPEG")
    return JSONResponse(analyzer.jsonable(qtables_mod.analyze(jp, sigdb())))


# ----------------------------------------------- سجل بصمات الكاميرات (PRNU)

@app.get("/api/prnu/cameras")
def prnu_list() -> list:
    """كل الكاميرات المسجّلة ببصماتها وبيانات بنائها."""
    return cameras.list()


@app.post("/api/prnu/cameras")
async def prnu_add(name: str = Form(...),
                   camera_id: Optional[str] = Form(None),
                   notes: str = Form(""),
                   crop: int = Form(1024),
                   files: list[UploadFile] = File(...)) -> JSONResponse:
    """
    تسجيل كاميرا جديدة ببناء بصمة PRNU من صورها المرجعية.

    يُفضَّل علميًا 20–50 صورة **مسطّحة ساطعة** (سماء/حائط أبيض) بنفس الدقة
    وبأقل ضغط ممكن. الصور لا تُحفظ؛ تُحفظ البصمة المستخرجة فقط.
    """
    blobs, names = [], []
    for f in files:
        b = await f.read()
        if not b:
            continue
        if len(b) > MAX_UPLOAD:
            raise HTTPException(413, f"الملف {f.filename} يتجاوز الحد المسموح")
        blobs.append(b)
        names.append(f.filename or "image")
    if len(blobs) < 2:
        raise HTTPException(400, "يلزم رفع صورتين على الأقل من نفس الكاميرا "
                                 "(والموصى به 20 صورة مسطّحة).")
    cid = camera_id or hashing.crypto_hashes(name.encode("utf-8"))["sha256"][:12]
    res = cameras.add(cid, name, blobs, names=names, crop=int(crop), notes=notes)
    if not res.get("ok"):
        raise HTTPException(400, res.get("reason", "تعذّر بناء البصمة"))
    store.log(None, None, "محقق", "تسجيل بصمة كاميرا PRNU",
              f"{name} ({cid}) من {res['n_images']} صورة")
    return JSONResponse(res)


@app.delete("/api/prnu/cameras/{cid}")
def prnu_delete(cid: str) -> dict:
    return {"deleted": cameras.delete(cid)}


@app.post("/api/prnu/identify")
async def prnu_identify(file: UploadFile = File(...)) -> JSONResponse:
    """مطابقة صورة مع كل الكاميرات المسجّلة وترتيب النتائج بإحصائية PCE."""
    data = await file.read()
    if not data:
        raise HTTPException(400, "الملف فارغ")
    return JSONResponse(analyzer.jsonable(cameras.identify(data)))


@app.get("/api/evidence")
def list_evidence(case_id: Optional[str] = None) -> list:
    return store.list_evidence(case_id)


@app.get("/api/evidence/{eid}")
def evidence_report(eid: str) -> dict:
    rep = store.load_report(eid)
    if not rep:
        raise HTTPException(404, "لا يوجد تقرير محفوظ لهذا الدليل")
    return rep


@app.get("/api/evidence/{eid}/verify")
def verify(eid: str) -> dict:
    return store.verify_integrity(eid)


@app.get("/api/evidence/{eid}/artifact/{name}")
def artifact(eid: str, name: str):
    safe = os.path.basename(name)
    p = os.path.join(store.artifacts_dir(eid), safe)
    if not os.path.exists(p):
        raise HTTPException(404, "الملف غير موجود")
    return FileResponse(p)


@app.get("/api/evidence/{eid}/original")
def original(eid: str):
    ev = store.get_evidence(eid)
    if not ev:
        raise HTTPException(404, "الدليل غير موجود")
    p = os.path.join(store.evidence_dir(eid), "original.bin")
    return FileResponse(p, filename=ev["filename"], media_type="application/octet-stream")


@app.get("/api/evidence/{eid}/hex")
def hexdump(eid: str, offset: int = 0, length: int = 1024) -> dict:
    p = os.path.join(store.evidence_dir(eid), "original.bin")
    if not os.path.exists(p):
        raise HTTPException(404, "الدليل غير موجود")
    size = os.path.getsize(p)
    length = max(16, min(length, 65536))
    offset = max(0, min(offset, max(0, size - 1)))
    with open(p, "rb") as f:
        f.seek(offset)
        chunk = f.read(length)
    lines = []
    for i in range(0, len(chunk), 16):
        row = chunk[i:i + 16]
        lines.append({
            "offset": offset + i,
            "hex": " ".join(f"{b:02x}" for b in row),
            "ascii": "".join(chr(b) if 32 <= b < 127 else "." for b in row),
        })
    return {"offset": offset, "length": len(chunk), "file_size": size, "lines": lines}


@app.get("/api/evidence/{eid}/strings")
def ev_strings(eid: str, kind: str = "ascii", limit: int = 500) -> dict:
    rep = store.load_report(eid)
    if not rep:
        raise HTTPException(404, "لا يوجد تقرير")
    s = (rep.get("strings") or {}).get("strings", {}).get(kind, [])
    return {"kind": kind, "count": len(s), "items": s[:limit]}


@app.get("/api/evidence/{eid}/report.html", response_class=HTMLResponse)
def html_report(eid: str) -> HTMLResponse:
    rep = store.load_report(eid)
    if not rep:
        raise HTTPException(404, "لا يوجد تقرير")
    ev = store.get_evidence(eid)
    case = store.get_case(ev["case_id"]) if ev and ev["case_id"] else None
    custody = store.custody_log(evidence_id=eid)
    htmls = report_mod.html_report(rep, case, ev, custody,
                                   artifacts_base=f"/api/evidence/{eid}/artifact/")
    return HTMLResponse(htmls)


@app.get("/api/evidence/{eid}/report.txt", response_class=PlainTextResponse)
def txt_report(eid: str) -> PlainTextResponse:
    rep = store.load_report(eid)
    if not rep:
        raise HTTPException(404, "لا يوجد تقرير")
    return PlainTextResponse(report_mod.text_summary(rep))


@app.get("/api/evidence/{eid}/package")
def package(eid: str):
    """حزمة أدلة كاملة: التقرير + المخرجات + النسخة الأصلية + سلسلة الحيازة."""
    ev = store.get_evidence(eid)
    if not ev:
        raise HTTPException(404, "الدليل غير موجود")
    rep = store.load_report(eid) or {}
    custody = store.custody_log(evidence_id=eid)
    case = store.get_case(ev["case_id"]) if ev["case_id"] else None
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("report.json", json.dumps(rep, ensure_ascii=False, indent=1, default=str))
        z.writestr("report.html", report_mod.html_report(rep, case, ev, custody, "artifacts/"))
        z.writestr("summary.txt", report_mod.text_summary(rep))
        z.writestr("chain_of_custody.json", json.dumps(
            {"evidence": ev, "case": case, "custody": custody,
             "chain_verification": store.verify_chain(ev["case_id"])},
            ensure_ascii=False, indent=1, default=str))
        ad = store.artifacts_dir(eid)
        for n in sorted(os.listdir(ad)):
            z.write(os.path.join(ad, n), f"artifacts/{n}")
        op = os.path.join(store.evidence_dir(eid), "original.bin")
        if os.path.exists(op):
            z.write(op, f"original/{ev['filename']}")
    buf.seek(0)
    store.log(ev["case_id"], eid, "النظام", "تصدير حزمة أدلة", f"حجم الحزمة: {buf.getbuffer().nbytes} بايت")
    return Response(buf.read(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="mirsad_evidence_{eid}.zip"'})


@app.post("/api/compare")
async def compare(file_a: UploadFile = File(...), file_b: UploadFile = File(...)) -> dict:
    """مقارنة دليلين: تطابق تام + نسبة تشابه سياقية + أول موضع اختلاف."""
    a = await file_a.read()
    b = await file_b.read()
    fa, fb = hashing.full_fingerprint(a), hashing.full_fingerprint(b)
    sim = hashing.fuzzy_compare(fa["ctph_fuzzy"], fb["ctph_fuzzy"])
    first_diff = None
    for i in range(min(len(a), len(b))):
        if a[i] != b[i]:
            first_diff = i
            break
    if first_diff is None and len(a) != len(b):
        first_diff = min(len(a), len(b))
    ba = hashing.block_hashes(a)
    bb = hashing.block_hashes(b)
    changed = [x["offset"] for x, y in zip(ba, bb) if x["sha256"] != y["sha256"]][:200]
    return {
        "file_a": {"name": file_a.filename, **fa},
        "file_b": {"name": file_b.filename, **fb},
        "identical": fa["sha256"] == fb["sha256"],
        "similarity_percent": sim,
        "first_difference_offset": first_diff,
        "changed_blocks_4k": changed,
        "verdict": ("الملفان متطابقان تمامًا (نفس البصمة)" if fa["sha256"] == fb["sha256"] else
                    f"الملفان مختلفان — نسبة التشابه السياقي {sim}%"),
    }


@app.post("/api/custody")
def add_custody(case_id: str = Form(...), actor: str = Form(...), action: str = Form(...),
                details: str = Form(""), evidence_id: Optional[str] = Form(None)) -> dict:
    if not store.get_case(case_id):
        raise HTTPException(404, "القضية غير موجودة")
    return store.log(case_id, evidence_id, actor, action, details)
