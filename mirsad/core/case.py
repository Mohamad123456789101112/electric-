"""
إدارة القضايا وسلسلة الحيازة (Chain of Custody).

سجل التدقيق مُسلسل تشفيريًا: كل قيد يحتوي hash القيد السابق، فأي تعديل لاحق على
السجل يكسر السلسلة ويُكتشف فورًا (نفس مبدأ دفاتر الأدلة المانعة للتلاعب).
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS cases (
    id TEXT PRIMARY KEY, number TEXT, title TEXT, investigator TEXT,
    authority TEXT, notes TEXT, created_utc TEXT
);
CREATE TABLE IF NOT EXISTS evidence (
    id TEXT PRIMARY KEY, case_id TEXT, filename TEXT, size INTEGER,
    sha256 TEXT, md5 TEXT, sha1 TEXT, fuzzy TEXT, mime TEXT,
    acquired_utc TEXT, source_note TEXT, report_path TEXT, suspicion_score INTEGER,
    FOREIGN KEY(case_id) REFERENCES cases(id)
);
CREATE TABLE IF NOT EXISTS custody (
    seq INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT, evidence_id TEXT,
    ts_utc TEXT, actor TEXT, action TEXT, details TEXT,
    prev_hash TEXT, entry_hash TEXT
);
CREATE INDEX IF NOT EXISTS idx_ev_case ON evidence(case_id);
CREATE INDEX IF NOT EXISTS idx_cu_case ON custody(case_id);
"""


class CaseStore:
    def __init__(self, root: str):
        self.root = root
        os.makedirs(root, exist_ok=True)
        self.db_path = os.path.join(root, "mirsad_cases.db")
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # ------------------------------------------------------------- utilities
    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def evidence_dir(self, evidence_id: str) -> str:
        p = os.path.join(self.root, "evidence", evidence_id)
        os.makedirs(p, exist_ok=True)
        return p

    def artifacts_dir(self, evidence_id: str) -> str:
        p = os.path.join(self.evidence_dir(evidence_id), "artifacts")
        os.makedirs(p, exist_ok=True)
        return p

    # ---------------------------------------------------------------- cases
    def create_case(self, number: str, title: str, investigator: str,
                    authority: str = "", notes: str = "") -> dict:
        cid = uuid.uuid4().hex[:16]
        self.conn.execute(
            "INSERT INTO cases VALUES (?,?,?,?,?,?,?)",
            (cid, number, title, investigator, authority, notes, self._now()))
        self.conn.commit()
        self.log(cid, None, investigator or "النظام", "فتح قضية",
                 f"رقم القضية: {number} — {title}")
        return self.get_case(cid)

    def get_case(self, cid: str) -> dict | None:
        r = self.conn.execute("SELECT * FROM cases WHERE id=?", (cid,)).fetchone()
        return dict(r) if r else None

    def list_cases(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT c.*, (SELECT COUNT(*) FROM evidence e WHERE e.case_id=c.id) AS evidence_count "
            "FROM cases c ORDER BY created_utc DESC").fetchall()
        return [dict(r) for r in rows]

    def delete_case(self, cid: str) -> None:
        self.conn.execute("DELETE FROM evidence WHERE case_id=?", (cid,))
        self.conn.execute("DELETE FROM cases WHERE id=?", (cid,))
        self.conn.commit()

    # -------------------------------------------------------------- evidence
    def add_evidence(self, case_id: str | None, filename: str, data: bytes,
                     fingerprints: dict, mime: str, actor: str = "النظام",
                     source_note: str = "") -> str:
        eid = uuid.uuid4().hex[:16]
        d = self.evidence_dir(eid)
        with open(os.path.join(d, "original.bin"), "wb") as f:
            f.write(data)
        self.conn.execute(
            "INSERT INTO evidence (id,case_id,filename,size,sha256,md5,sha1,fuzzy,mime,"
            "acquired_utc,source_note,report_path,suspicion_score) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (eid, case_id, filename, len(data), fingerprints.get("sha256"),
             fingerprints.get("md5"), fingerprints.get("sha1"), fingerprints.get("ctph_fuzzy"),
             mime, self._now(), source_note, None, None))
        self.conn.commit()
        self.log(case_id, eid, actor, "استلام دليل",
                 f"الملف: {filename} | الحجم: {len(data)} بايت | SHA-256: {fingerprints.get('sha256')}")
        return eid

    def save_report(self, evidence_id: str, report: dict) -> str:
        d = self.evidence_dir(evidence_id)
        p = os.path.join(d, "report.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
        score = (report.get("assessment") or {}).get("suspicion_score")
        self.conn.execute("UPDATE evidence SET report_path=?, suspicion_score=? WHERE id=?",
                          (p, score, evidence_id))
        self.conn.commit()
        return p

    def get_evidence(self, eid: str) -> dict | None:
        r = self.conn.execute("SELECT * FROM evidence WHERE id=?", (eid,)).fetchone()
        return dict(r) if r else None

    def list_evidence(self, case_id: str | None = None) -> list[dict]:
        if case_id:
            rows = self.conn.execute(
                "SELECT * FROM evidence WHERE case_id=? ORDER BY acquired_utc DESC", (case_id,)).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM evidence ORDER BY acquired_utc DESC LIMIT 500").fetchall()
        return [dict(r) for r in rows]

    def load_report(self, eid: str) -> dict | None:
        p = os.path.join(self.evidence_dir(eid), "report.json")
        if not os.path.exists(p):
            return None
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    def verify_integrity(self, eid: str) -> dict:
        """إعادة حساب بصمة الملف المخزّن ومطابقتها بما سُجّل وقت الاستلام."""
        ev = self.get_evidence(eid)
        if not ev:
            return {"ok": False, "error": "الدليل غير موجود"}
        p = os.path.join(self.evidence_dir(eid), "original.bin")
        if not os.path.exists(p):
            return {"ok": False, "error": "النسخة الأصلية مفقودة من المخزن"}
        h = hashlib.sha256()
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        now = h.hexdigest()
        ok = now == ev["sha256"]
        self.log(ev["case_id"], eid, "النظام", "تحقق من السلامة",
                 f"نتيجة المطابقة: {'مطابق' if ok else 'غير مطابق!'} | المحسوب: {now}")
        return {"ok": ok, "recorded_sha256": ev["sha256"], "computed_sha256": now,
                "verified_at": self._now()}

    # ---------------------------------------------------------- chain of custody
    def log(self, case_id: str | None, evidence_id: str | None, actor: str,
            action: str, details: str = "") -> dict:
        row = self.conn.execute(
            "SELECT entry_hash FROM custody WHERE case_id IS ? ORDER BY seq DESC LIMIT 1",
            (case_id,)).fetchone()
        prev = row["entry_hash"] if row else "0" * 64
        ts = self._now()
        payload = json.dumps({"case": case_id, "evidence": evidence_id, "ts": ts,
                              "actor": actor, "action": action, "details": details,
                              "prev": prev}, ensure_ascii=False, sort_keys=True)
        eh = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        self.conn.execute(
            "INSERT INTO custody (case_id,evidence_id,ts_utc,actor,action,details,prev_hash,entry_hash)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (case_id, evidence_id, ts, actor, action, details, prev, eh))
        self.conn.commit()
        return {"ts": ts, "entry_hash": eh, "prev_hash": prev}

    def custody_log(self, case_id: str | None = None, evidence_id: str | None = None) -> list[dict]:
        q = "SELECT * FROM custody WHERE 1=1"
        args: list = []
        if case_id:
            q += " AND case_id=?"
            args.append(case_id)
        if evidence_id:
            q += " AND evidence_id=?"
            args.append(evidence_id)
        q += " ORDER BY seq ASC"
        return [dict(r) for r in self.conn.execute(q, args).fetchall()]

    def verify_chain(self, case_id: str | None = None) -> dict:
        rows = self.custody_log(case_id)
        prev = "0" * 64
        broken = []
        for r in rows:
            payload = json.dumps({"case": r["case_id"], "evidence": r["evidence_id"],
                                  "ts": r["ts_utc"], "actor": r["actor"], "action": r["action"],
                                  "details": r["details"], "prev": r["prev_hash"]},
                                 ensure_ascii=False, sort_keys=True)
            calc = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            if calc != r["entry_hash"] or r["prev_hash"] != prev:
                broken.append({"seq": r["seq"], "expected_prev": prev,
                               "stored_prev": r["prev_hash"],
                               "recomputed_hash": calc, "stored_hash": r["entry_hash"]})
            prev = r["entry_hash"]
        return {"entries": len(rows), "intact": not broken, "broken_links": broken,
                "head_hash": prev,
                "statement": ("سلسلة الحيازة سليمة تشفيريًا — لم يُعبث بأي قيد."
                              if not broken else
                              "⚠️ السلسلة مكسورة — تم تعديل/حذف قيود في سجل الحيازة.")}
