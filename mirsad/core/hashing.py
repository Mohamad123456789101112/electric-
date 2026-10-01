"""
البصمات الرقمية: تجزئات تشفيرية معيارية + تجزئة سياقية مُقسّمة (CTPH / spamsum)
لمقارنة التشابه بين الأدلة. كل الخوارزميات منفّذة فعليًا هنا (مش استدعاء وهمي).
"""
from __future__ import annotations

import hashlib
import zlib

# ---------------------------------------------------------------- تجزئات معيارية


def crypto_hashes(data: bytes) -> dict:
    return {
        "md5": hashlib.md5(data).hexdigest(),
        "sha1": hashlib.sha1(data).hexdigest(),
        "sha256": hashlib.sha256(data).hexdigest(),
        "sha512": hashlib.sha512(data).hexdigest(),
        "sha3_256": hashlib.sha3_256(data).hexdigest(),
        "blake2b": hashlib.blake2b(data, digest_size=32).hexdigest(),
        "crc32": format(zlib.crc32(data) & 0xFFFFFFFF, "08x"),
    }


def block_hashes(data: bytes, block: int = 4096) -> list[dict]:
    """تجزئة القطاعات (piecewise hashing) — تحدد أي جزء بالضبط تغيّر بين نسختين."""
    out = []
    for i in range(0, len(data), block):
        chunk = data[i:i + block]
        out.append({"offset": i, "size": len(chunk),
                    "sha256": hashlib.sha256(chunk).hexdigest()})
        if len(out) >= 4096:
            break
    return out


# ------------------------------------------------- CTPH (ssdeep-compatible logic)
# تنفيذ خوارزمية spamsum: نافذة متدحرجة (rolling hash) لتحديد حدود القطع،
# ثم FNV hash لكل قطعة، وأخذ 6 بت كحرف base64.

_B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
_ROLL_WINDOW = 7
_SPAMSUM_LENGTH = 64
_MIN_BLOCKSIZE = 3


class _Roll:
    __slots__ = ("win", "h1", "h2", "h3", "n")

    def __init__(self) -> None:
        self.win = [0] * _ROLL_WINDOW
        self.h1 = self.h2 = self.h3 = 0
        self.n = 0

    def update(self, c: int) -> int:
        self.h2 -= self.h1
        self.h2 = (self.h2 + _ROLL_WINDOW * c) & 0xFFFFFFFF
        self.h1 = (self.h1 + c - self.win[self.n % _ROLL_WINDOW]) & 0xFFFFFFFF
        self.win[self.n % _ROLL_WINDOW] = c
        self.n += 1
        self.h3 = ((self.h3 << 5) & 0xFFFFFFFF) ^ c
        return (self.h1 + self.h2 + self.h3) & 0xFFFFFFFF


def _fnv(h: int, c: int) -> int:
    return ((h * 0x01000193) ^ c) & 0xFFFFFFFF


def fuzzy_hash(data: bytes) -> str:
    """بصمة تشابه سياقية بصيغة  blocksize:hash1:hash2  (متوافقة مع منطق ssdeep)."""
    n = len(data)
    if n == 0:
        return "3::"
    bs = _MIN_BLOCKSIZE
    while bs * _SPAMSUM_LENGTH < n:
        bs *= 2
    while True:
        roll = _Roll()
        h1, h2 = 0x28021967, 0x28021967
        s1, s2 = [], []
        for c in data:
            h1 = _fnv(h1, c)
            h2 = _fnv(h2, c)
            r = roll.update(c)
            if r % bs == bs - 1:
                if len(s1) < _SPAMSUM_LENGTH - 1:
                    s1.append(_B64[h1 & 63])
                    h1 = 0x28021967
            if r % (bs * 2) == (bs * 2) - 1:
                if len(s2) < _SPAMSUM_LENGTH // 2 - 1:
                    s2.append(_B64[h2 & 63])
                    h2 = 0x28021967
        s1.append(_B64[h1 & 63])
        s2.append(_B64[h2 & 63])
        if bs > _MIN_BLOCKSIZE and len(s1) < _SPAMSUM_LENGTH // 2:
            bs //= 2
            continue
        return f"{bs}:{''.join(s1)}:{''.join(s2)}"


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _score(s1: str, s2: str, bs: int) -> int:
    if not s1 or not s2:
        return 0
    d = _levenshtein(s1, s2)
    d = (d * _SPAMSUM_LENGTH) // max(len(s1), len(s2))
    sc = 100 - (100 * d) // _SPAMSUM_LENGTH
    cap = (bs // _MIN_BLOCKSIZE) * min(len(s1), len(s2))
    return max(0, min(sc, cap, 100))


def fuzzy_compare(f1: str, f2: str) -> int:
    """نسبة تشابه 0..100 بين بصمتين سياقيتين — تكشف الملفات المعدّلة جزئيًا."""
    try:
        b1, a1, c1 = f1.split(":")
        b2, a2, c2 = f2.split(":")
        bs1, bs2 = int(b1), int(b2)
    except Exception:
        return 0
    if bs1 == bs2:
        return max(_score(a1, a2, bs1), _score(c1, c2, bs1 * 2))
    if bs1 == bs2 * 2:
        return _score(c2, a1, bs1)
    if bs2 == bs1 * 2:
        return _score(c1, a2, bs2)
    return 0


def full_fingerprint(data: bytes) -> dict:
    h = crypto_hashes(data)
    h["ctph_fuzzy"] = fuzzy_hash(data)
    h["size_bytes"] = len(data)
    return h
