"""
محرّك تحديد الموقع — «فين اتصوّرت الحاجة دي؟»

يجمع هذا المحرّك **كل إشارة موقع حقيقية** يمكن استخراجها من ملف، ويفصل بوضوح
بين ثلاثة مستويات لا يجوز خلطها في تقرير جنائي:

  1) إحداثيات مُقاسة  — رقم خط عرض/طول مكتوب فعليًا داخل الملف (GPS/ISO 6709…).
  2) أسماء أماكن مكتوبة — مدينة/دولة كتبها برنامج أو إنسان (IPTC/XMP).
  3) مؤشرات ترجيحية  — لا تعطي نقطة على الخريطة لكنها تُضيّق النطاق:
     فرق التوقيت، مفتاح هاتف دولي، نطاق إنترنت لدولة، لغة النص…

كل ما يُحسب هنا إما **مقروء من البايتات** أو **حساب رياضي بحت** (تحويل صيغ،
مسافة، منطقة UTM، جيوهاش، Plus Code). لا توجد قاعدة بيانات خرائط ولا اتصال
بالإنترنت، ولذلك لا يدّعي المحرّك أبدًا معرفة اسم الشارع أو المبنى — يعطي
الإحداثيات بدقتها الحقيقية وروابط خرائط يفتحها المحقق بنفسه.

قيمة إضافية مهمة: الموقع يُستخرج أيضًا من **شظايا الميتاداتا الممسوحة** التي
يستعيدها محرّك الاسترجاع — أي أن صورة «نُظّفت» قد تفضح موقعها رغم ذلك.
"""
from __future__ import annotations

import math
import re

# ===================================================================
#   1) تحويلات وحسابات رياضية بحتة (لا تحتاج أي بيانات خارجية)
# ===================================================================

GEOHASH_ALPHABET = "0123456789bcdefghjkmnpqrstuvwxyz"
OLC_ALPHABET = "23456789CFGHJMPQRVWX"
OLC_PAIR_RES = [20.0, 1.0, 0.05, 0.0025, 0.000125]


def to_dms(value: float, is_lat: bool) -> str:
    """تحويل العدد العشري إلى درجات ودقائق وثوانٍ بصيغة الملاحة المعتادة."""
    hemi = ("N" if value >= 0 else "S") if is_lat else ("E" if value >= 0 else "W")
    v = abs(value)
    d = int(v)
    m_full = (v - d) * 60
    m = int(m_full)
    s = (m_full - m) * 60
    return f"{d}°{m:02d}'{s:05.2f}\"{hemi}"


def utm_zone(lat: float, lon: float) -> dict:
    """منطقة UTM وشريطها (حساب قياسي مع استثناءات النرويج وسفالبارد)."""
    zone = int((lon + 180) / 6) + 1
    if 56 <= lat < 64 and 3 <= lon < 12:
        zone = 32
    if 72 <= lat < 84:
        if 0 <= lon < 9:
            zone = 31
        elif 9 <= lon < 21:
            zone = 33
        elif 21 <= lon < 33:
            zone = 35
        elif 33 <= lon < 42:
            zone = 37
    bands = "CDEFGHJKLMNPQRSTUVWX"
    idx = int((lat + 80) / 8)
    band = bands[idx] if 0 <= idx < len(bands) else "?"
    return {"zone": zone, "band": band, "label": f"{zone}{band}",
            "hemisphere": "شمالي" if lat >= 0 else "جنوبي"}


def geohash(lat: float, lon: float, precision: int = 9) -> str:
    """ترميز Geohash القياسي (تقسيم ثنائي متناوب بين الطول والعرض)."""
    lat_r, lon_r = [-90.0, 90.0], [-180.0, 180.0]
    out, bit, ch, even = [], 0, 0, True
    while len(out) < precision:
        if even:
            mid = (lon_r[0] + lon_r[1]) / 2
            if lon > mid:
                ch = (ch << 1) | 1
                lon_r[0] = mid
            else:
                ch <<= 1
                lon_r[1] = mid
        else:
            mid = (lat_r[0] + lat_r[1]) / 2
            if lat > mid:
                ch = (ch << 1) | 1
                lat_r[0] = mid
            else:
                ch <<= 1
                lat_r[1] = mid
        even = not even
        bit += 1
        if bit == 5:
            out.append(GEOHASH_ALPHABET[ch])
            bit, ch = 0, 0
    return "".join(out)


def plus_code(lat: float, lon: float, length: int = 11) -> str:
    """
    ترميز Open Location Code (Plus Code) — خوارزمية مفتوحة بحتة.

    عشرة أرقام أزواج (دقة ~13.9م) ثم رقم شبكة إضافي (4×5) لدقة ~2.8م.
    """
    lat = max(-90.0, min(90.0, lat))
    if lat >= 90:
        lat = 89.999999
    lon = ((lon + 180) % 360) - 180
    la = lat + 90.0
    lo = lon + 180.0
    code = ""
    for i in range(5):
        res = OLC_PAIR_RES[i]
        d_lat = int(la / res)
        la -= d_lat * res
        d_lon = int(lo / res)
        lo -= d_lon * res
        code += OLC_ALPHABET[min(d_lat, 19)] + OLC_ALPHABET[min(d_lon, 19)]
        if i == 3:
            code += "+"
    if length > 10:
        lat_res, lon_res = OLC_PAIR_RES[4], OLC_PAIR_RES[4]
        for _ in range(min(length, 15) - 10):
            lat_res /= 5.0
            lon_res /= 4.0
            r = min(4, int(la / lat_res))
            c = min(3, int(lo / lon_res))
            la -= r * lat_res
            lo -= c * lon_res
            code += OLC_ALPHABET[r * 4 + c]
    return code


def decode_plus_code(code: str) -> tuple[float, float] | None:
    """فكّ Plus Code كامل (بعلامة + في موضعها القياسي) إلى مركز خليته."""
    c = code.strip().upper()
    if "+" not in c:
        return None
    c = c.replace("+", "")
    if len(c) < 8 or any(ch not in OLC_ALPHABET for ch in c):
        return None
    la, lo = -90.0, -180.0
    pairs = c[:10]
    for i in range(0, min(len(pairs), 10), 2):
        res = OLC_PAIR_RES[i // 2]
        la += OLC_ALPHABET.index(pairs[i]) * res
        lo += OLC_ALPHABET.index(pairs[i + 1]) * res
    lat_res, lon_res = OLC_PAIR_RES[(min(len(pairs), 10) - 1) // 2], \
        OLC_PAIR_RES[(min(len(pairs), 10) - 1) // 2]
    for ch in c[10:]:
        lat_res /= 5.0
        lon_res /= 4.0
        v = OLC_ALPHABET.index(ch)
        la += (v // 4) * lat_res
        lo += (v % 4) * lon_res
    return la + lat_res / 2, lo + lon_res / 2


def haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    """المسافة بين نقطتين على سطح كروي بالمتر (نصف قطر الأرض المتوسط)."""
    R = 6371008.8
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp = p2 - p1
    dl = math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(min(1.0, math.sqrt(h)))


def bearing_deg(a: tuple[float, float], b: tuple[float, float]) -> float:
    """الاتجاه من النقطة أ إلى ب بالدرجات من الشمال."""
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dl = math.radians(b[1] - a[1])
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def timezone_band(lon: float) -> dict:
    """تقدير فرق التوقيت من خط الطول (كل 15° = ساعة) — حساب فلكي لا سياسي."""
    off = round(lon / 15.0)
    return {"estimated_utc_offset": off,
            "note": ("فرق التوقيت الشمسي المحسوب من خط الطول. الحدود الزمنية "
                     "السياسية قد تخالفه بساعة أو أكثر، لكنه يصلح للمقارنة مع "
                     "حقل OffsetTime المكتوب في الصورة لكشف التناقض.")}


def compass_16(deg: float) -> str:
    names = ["شمال", "شمال-شمال شرق", "شمال شرق", "شرق-شمال شرق", "شرق",
             "شرق-جنوب شرق", "جنوب شرق", "جنوب-جنوب شرق", "جنوب",
             "جنوب-جنوب غرب", "جنوب غرب", "غرب-جنوب غرب", "غرب",
             "غرب-شمال غرب", "شمال غرب", "شمال-شمال غرب"]
    return names[int((deg % 360) / 22.5 + 0.5) % 16]


def formats(lat: float, lon: float) -> dict:
    """كل الصيغ المشتقّة من نقطة واحدة + روابط خرائط جاهزة."""
    return {
        "decimal": f"{lat:.6f}, {lon:.6f}",
        "dms": f"{to_dms(lat, True)} {to_dms(lon, False)}",
        "iso_6709": f"{lat:+09.5f}{lon:+010.5f}/",
        "geohash": geohash(lat, lon),
        "plus_code": plus_code(lat, lon),
        "utm": utm_zone(lat, lon),
        "timezone": timezone_band(lon),
        "links": {
            "OpenStreetMap": f"https://www.openstreetmap.org/?mlat={lat:.6f}&mlon={lon:.6f}#map=17/{lat:.6f}/{lon:.6f}",
            "Google Maps": f"https://www.google.com/maps/search/?api=1&query={lat:.6f},{lon:.6f}",
            "Google Earth": f"https://earth.google.com/web/@{lat:.6f},{lon:.6f},0a,500d,35y",
            "Bing Maps": f"https://www.bing.com/maps?cp={lat:.6f}~{lon:.6f}&lvl=17",
            "خريطة مُضمَّنة": (f"https://www.openstreetmap.org/export/embed.html?"
                               f"bbox={lon - 0.004:.6f},{lat - 0.003:.6f},"
                               f"{lon + 0.004:.6f},{lat + 0.003:.6f}&layer=mapnik&"
                               f"marker={lat:.6f},{lon:.6f}"),
        },
    }


def valid_point(lat, lon) -> bool:
    try:
        lat = float(lat)
        lon = float(lon)
    except (TypeError, ValueError):
        return False
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return False
    return True


# ===================================================================
#   2) مستخرجات الإحداثيات من مصادر الملف المختلفة
# ===================================================================

def _f(v):
    """تحويل قيمة EXIF (قد تكون كسرًا [بسط، مقام]) إلى عدد عشري."""
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, (list, tuple)) and len(v) == 2 and all(
            isinstance(x, (int, float)) for x in v):
        return float(v[0]) / float(v[1]) if v[1] else None
    return None


def _raw(ifd: dict, name: str):
    e = (ifd or {}).get(name)
    return e.get("raw") if isinstance(e, dict) else e


PROCESSING_METHODS = {
    "GPS": ("قمر صناعي مباشر", "أدق أنواع التثبيت (عدة أمتار)."),
    "CELLID": ("أبراج الشبكة الخلوية", "دقة منخفضة: مئات الأمتار إلى كيلومترات."),
    "WLAN": ("شبكات الواي-فاي المحيطة", "دقة متوسطة (عشرات الأمتار) داخل المدن."),
    "MANUAL": ("أُدخل يدويًا", "⚠️ الموقع كتبه إنسان أو برنامج، لم يُقس بجهاز."),
    "NETWORK": ("تحديد شبكي", "دقة متغيرة."),
}


def from_exif_gps(tiff: dict, source: str = "EXIF GPS IFD") -> dict | None:
    """
    قراءة كاملة لحقل GPS IFD مع تقييم جودة التثبيت.

    لا نكتفي بخط العرض والطول: حالة الإشارة وعدد الأقمار ومعامل DOP وطريقة
    التثبيت هي ما يحدّد **هل هذا الموقع يصلح دليلًا أم لا**.
    """
    if not isinstance(tiff, dict):
        return None
    g = tiff.get("GPSIFD") or {}
    dec = tiff.get("GPS_decoded") or {}
    lat, lon = dec.get("latitude"), dec.get("longitude")
    if not valid_point(lat, lon):
        return None
    out: dict = {"source": source, "kind": "إحداثيات مُقاسة",
                 "latitude": float(lat), "longitude": float(lon)}

    alt = _f(_raw(g, "GPSAltitude"))
    if alt is not None:
        ref = _raw(g, "GPSAltitudeRef")
        below = (ref == 1) or (isinstance(ref, (bytes, bytearray)) and ref[:1] == b"\x01")
        out["altitude_m"] = round(-alt if below else alt, 2)
        out["altitude_note"] = "تحت سطح البحر" if below else "فوق سطح البحر"

    status = _raw(g, "GPSStatus")
    if status:
        out["status"] = str(status)
        out["status_meaning"] = ("قياس فعّال (A) — الجهاز كان يستقبل إشارة وقت الالتقاط"
                                 if str(status).upper().startswith("A") else
                                 "⚠️ قياس غير فعّال (V) — الإشارة كانت مفقودة، والموقع "
                                 "قد يكون آخر نقطة محفوظة لا موقع الالتقاط")
    mm = _raw(g, "GPSMeasureMode")
    if mm:
        out["measure_mode"] = f"{mm}D" if str(mm) in ("2", "3") else str(mm)
    dop = _f(_raw(g, "GPSDOP"))
    if dop is not None:
        out["dop"] = round(dop, 2)
        out["dop_quality"] = ("ممتاز" if dop < 2 else "جيد" if dop < 5 else
                              "مقبول" if dop < 10 else "⚠️ ضعيف — موقع غير دقيق")
    sats = _raw(g, "GPSSatellites")
    if sats:
        out["satellites"] = str(sats)
    hpe = _f(_raw(g, "GPSHPositioningError"))
    if hpe is not None:
        out["horizontal_error_m"] = round(hpe, 2)

    pm = _raw(g, "GPSProcessingMethod")
    if pm:
        txt = pm.decode("utf-8", "ignore") if isinstance(pm, (bytes, bytearray)) else str(pm)
        txt = txt.replace("ASCII\x00\x00\x00", "").strip("\x00 ")
        out["processing_method_raw"] = txt
        for key, (label, note) in PROCESSING_METHODS.items():
            if key in txt.upper():
                out["fix_type"] = label
                out["fix_note"] = note
                break

    spd = _f(_raw(g, "GPSSpeed"))
    if spd is not None:
        unit = str(_raw(g, "GPSSpeedRef") or "K").upper()
        kmh = spd * {"K": 1.0, "M": 1.609344, "N": 1.852}.get(unit[:1], 1.0)
        out["speed_kmh"] = round(kmh, 2)
        out["speed_note"] = ("الجهاز كان ساكنًا تقريبًا" if kmh < 1 else
                             "حركة مشي" if kmh < 8 else
                             "حركة مركبة" if kmh < 130 else "سرعة عالية جدًا")
    dirv = _f(_raw(g, "GPSImgDirection"))
    if dirv is not None:
        ref = str(_raw(g, "GPSImgDirectionRef") or "T").upper()
        out["camera_direction_deg"] = round(dirv, 2)
        out["camera_direction_text"] = compass_16(dirv)
        out["camera_direction_ref"] = ("الشمال الحقيقي" if ref.startswith("T")
                                       else "الشمال المغناطيسي")
    trk = _f(_raw(g, "GPSTrack"))
    if trk is not None:
        out["movement_direction_deg"] = round(trk, 2)
        out["movement_direction_text"] = compass_16(trk)

    datum = _raw(g, "GPSMapDatum")
    if datum:
        out["map_datum"] = str(datum)
    area = _raw(g, "GPSAreaInformation")
    if area:
        txt = area.decode("utf-8", "ignore") if isinstance(area, (bytes, bytearray)) else str(area)
        txt = txt.strip("\x00 ")
        if txt:
            out["area_information"] = txt

    ds, ts = _raw(g, "GPSDateStamp"), _raw(g, "GPSTimeStamp")
    if ds:
        out["gps_date_utc"] = str(ds)
    if isinstance(ts, (list, tuple)) and len(ts) == 3:
        hms = [_f(x) for x in ts]
        if all(x is not None for x in hms):
            out["gps_time_utc"] = f"{int(hms[0]):02d}:{int(hms[1]):02d}:{hms[2]:05.2f}"

    # وجهة مسجّلة (تستخدمها بعض أجهزة الملاحة والكاميرات)
    dlat = dec.get("dest_latitude")
    if dlat is None:
        from .exif import _gps_decimal  # إعادة استخدام نفس الدالة المُختبَرة
        dlat = _gps_decimal(_raw(g, "GPSDestLatitude"), _raw(g, "GPSDestLatitudeRef"))
        dlon = _gps_decimal(_raw(g, "GPSDestLongitude"), _raw(g, "GPSDestLongitudeRef"))
        if valid_point(dlat, dlon):
            out["destination"] = {"latitude": dlat, "longitude": dlon,
                                  "note": "وجهة مسجّلة داخل الملف إضافةً لموقع الالتقاط"}
    out["confidence"] = _gps_confidence(out)
    return out


def _gps_confidence(p: dict) -> dict:
    """تقييم مدى صلاحية هذه النقطة كدليل، بأسباب صريحة."""
    score, why = 100, []
    if str(p.get("status", "A")).upper().startswith("V"):
        score -= 45
        why.append("حالة الإشارة V (غير فعّالة)")
    if p.get("dop") is not None and p["dop"] >= 10:
        score -= 25
        why.append(f"معامل DOP مرتفع ({p['dop']})")
    if p.get("horizontal_error_m") and p["horizontal_error_m"] > 100:
        score -= 20
        why.append(f"خطأ أفقي معلن {p['horizontal_error_m']} م")
    ft = p.get("fix_type") or ""
    if "خلوية" in ft:
        score -= 30
        why.append("التثبيت من أبراج الشبكة لا من الأقمار")
    elif "يدويًا" in ft:
        score -= 60
        why.append("الموقع أُدخل يدويًا")
    elif "واي-فاي" in ft:
        score -= 15
        why.append("التثبيت من شبكات الواي-فاي")
    if p.get("measure_mode") == "2D":
        score -= 5
        why.append("قياس ثنائي الأبعاد (بلا ارتفاع موثوق)")
    score = max(0, min(100, score))
    level = ("عالية" if score >= 80 else "متوسطة" if score >= 50 else "منخفضة")
    return {"score": score, "level": level, "reasons": why or ["لا تحفّظات مرصودة"]}


ISO6709_RE = re.compile(r"^([+-]\d{2,6}(?:\.\d+)?)([+-]\d{3,7}(?:\.\d+)?)"
                        r"(?:([+-]\d+(?:\.\d+)?))?/?$")


def parse_iso6709(text: str) -> dict | None:
    """
    فكّ صيغة ISO 6709 المستخدمة في مقاطع الفيديو (الوسم ©xyz في MP4/MOV).

    تدعم الصيغة العشرية المباشرة (+30.0444+031.2357/) وصيغة الدرجات/الدقائق
    المضغوطة (+3002.66+03114.14/) كما تكتبها بعض الهواتف.
    """
    if not text:
        return None
    m = ISO6709_RE.match(text.strip().rstrip("/") + "/")
    if not m:
        return None

    def conv(tok: str, deg_digits: int):
        sign = -1.0 if tok[0] == "-" else 1.0
        body = tok[1:]
        if "." in body:
            ip, fp = body.split(".", 1)
        else:
            ip, fp = body, ""
        if len(ip) <= deg_digits:            # صيغة عشرية مباشرة
            return sign * float(body)
        deg = float(ip[:deg_digits])
        rest = ip[deg_digits:] + ("." + fp if fp else "")
        if len(ip) - deg_digits == 2:        # DDMM.MM
            return sign * (deg + float(rest) / 60.0)
        if len(ip) - deg_digits == 4:        # DDMMSS.SS
            mm = float(rest[:2])
            ss = float(rest[2:]) if len(rest) > 2 else 0.0
            return sign * (deg + mm / 60.0 + ss / 3600.0)
        return sign * float(body)

    lat = conv(m.group(1), 2)
    lon = conv(m.group(2), 3)
    if not valid_point(lat, lon):
        return None
    out = {"latitude": lat, "longitude": lon}
    if m.group(3):
        try:
            out["altitude_m"] = float(m.group(3))
        except ValueError:
            pass
    return out


def from_bmff(bmff: dict) -> list[dict]:
    """استخراج الموقع من حاويات MP4/MOV/HEIC (الوسم ©xyz أو صندوق loci)."""
    pts = []
    md = (bmff or {}).get("metadata") or {}
    cands: list[tuple[str, str]] = []
    for key, val in (md.get("location_boxes") or {}).items():
        if isinstance(val, str):
            cands.append((f"صندوق {key}", val))
    for key, val in (md.get("tags") or {}).items():
        if isinstance(val, str) and ("GPS" in str(key) or "xyz" in str(key)):
            cands.append((f"وسم {key}", val))
    for key, val in md.items():
        if isinstance(val, str) and ("xyz" in str(key) or "loci" in str(key).lower()):
            cands.append((f"وسم {key}", val))
    for label, val in cands:
        p = parse_iso6709(val)
        if p:
            pts.append({**p, "source": f"حاوية فيديو/صورة — {label}",
                        "kind": "إحداثيات مُقاسة",
                        "raw_value": val,
                        "confidence": {"score": 85, "level": "عالية",
                                       "reasons": ["إحداثيات مكتوبة بصيغة ISO 6709 "
                                                   "داخل بنية الحاوية — يكتبها الجهاز "
                                                   "وقت التسجيل"]}})
    place = (md.get("location_boxes") or {}).get("loci_place_name")
    if place:
        for p in pts:
            p["place_name"] = place
    return pts


XMP_GEO = {
    "exif:GPSLatitude": "latitude", "exif:GPSLongitude": "longitude",
}
XMP_PLACES = {
    "Iptc4xmpExt:City": "المدينة", "Iptc4xmpExt:CountryName": "الدولة",
    "Iptc4xmpExt:ProvinceState": "المحافظة/الولاية",
    "Iptc4xmpExt:Sublocation": "الموقع التفصيلي",
    "Iptc4xmpExt:CountryCode": "رمز الدولة",
    "Iptc4xmpExt:WorldRegion": "الإقليم",
    "photoshop:City": "المدينة", "photoshop:State": "المحافظة/الولاية",
    "photoshop:Country": "الدولة", "photoshop:Location": "الموقع التفصيلي",
}


def _xmp_num(tok: str) -> float | None:
    """XMP يكتب الإحداثي هكذا: 30,2.6667N  (درجات، دقائق عشرية، اتجاه)."""
    if not tok:
        return None
    t = tok.strip()
    hemi = t[-1].upper() if t and t[-1].upper() in "NSEW" else ""
    if hemi:
        t = t[:-1]
    try:
        if "," in t:
            parts = t.split(",")
            deg = float(parts[0])
            mins = float(parts[1]) if len(parts) > 1 else 0.0
            secs = float(parts[2]) if len(parts) > 2 else 0.0
            v = deg + mins / 60.0 + secs / 3600.0
        else:
            v = float(t)
    except ValueError:
        return None
    if hemi in ("S", "W"):
        v = -v
    return v


def from_xmp(xmp_text: str) -> dict:
    """أسماء الأماكن والإحداثيات المكتوبة داخل حزمة XMP."""
    out: dict = {"points": [], "places": {}}
    if not xmp_text:
        return out
    lat = lon = None
    for tag, field in XMP_GEO.items():
        m = re.search(rf"{tag}\s*=\s*\"([^\"]+)\"", xmp_text) or \
            re.search(rf"<{tag}>([^<]+)</{tag}>", xmp_text)
        if m:
            v = _xmp_num(m.group(1))
            if field == "latitude":
                lat = v
            else:
                lon = v
    if valid_point(lat, lon):
        out["points"].append({
            "latitude": lat, "longitude": lon, "source": "XMP (exif:GPS*)",
            "kind": "إحداثيات مُقاسة",
            "confidence": {"score": 75, "level": "متوسطة",
                           "reasons": ["إحداثيات من حزمة XMP — قد يكتبها برنامج تحرير "
                                       "لا الجهاز نفسه"]}})
    for tag, label in XMP_PLACES.items():
        m = re.search(rf"{tag}\s*=\s*\"([^\"]+)\"", xmp_text) or \
            re.search(rf"<{tag}>([^<]+)</{tag}>", xmp_text)
        if m and m.group(1).strip():
            out["places"][label] = {"value": m.group(1).strip(), "source": f"XMP {tag}"}
    return out


IPTC_PLACE_FIELDS = {
    "City": "المدينة", "Sub-location": "الموقع التفصيلي",
    "Province/State": "المحافظة/الولاية", "Country/Primary Location Name": "الدولة",
    "Country/Primary Location Code": "رمز الدولة",
    "Original Transmission Reference": "مرجع الإرسال",
}


def from_iptc(iptc: dict) -> dict:
    places = {}
    for k, v in (iptc or {}).items():
        for needle, label in IPTC_PLACE_FIELDS.items():
            if needle.lower() in str(k).lower() and isinstance(v, str) and v.strip():
                places[label] = {"value": v.strip(), "source": f"IPTC {k}"}
    return places


# ===================================================================
#   3) إشارات الموقع داخل النصوص الخام (روابط، إحداثيات مكتوبة، رموز)
# ===================================================================

DEC_PAIR = re.compile(
    r"(?<![\d.])([-+]?\d{1,2}\.\d{4,})\s*[,،;]\s*([-+]?\d{1,3}\.\d{4,})(?![\d.])")
DMS_PAIR = re.compile(
    r"(\d{1,3})\s*[°º]\s*(\d{1,2})\s*['′]\s*([\d.]+)\s*[\"″]?\s*([NSns])"
    r"[\s,،]*(\d{1,3})\s*[°º]\s*(\d{1,2})\s*['′]\s*([\d.]+)\s*[\"″]?\s*([EWew])")
GEO_URI = re.compile(r"geo:([-+]?\d+\.?\d*),([-+]?\d+\.?\d*)")
GMAPS_AT = re.compile(r"google\.[a-z.]+/maps[^\s\"'<>]*?@([-+]?\d+\.\d+),([-+]?\d+\.\d+)")
GMAPS_Q = re.compile(r"(?:maps\.google|google\.[a-z.]+/maps)[^\s\"'<>]*?[?&]q=([-+]?\d+\.\d+),([-+]?\d+\.\d+)")
OSM_URL = re.compile(r"openstreetmap\.org[^\s\"'<>]*?[#?][^\s\"'<>]*?(?:map=\d+/|mlat=)([-+]?\d+\.\d+)[/&](?:mlon=)?([-+]?\d+\.\d+)")
APPLE_MAPS = re.compile(r"maps\.apple\.com[^\s\"'<>]*?ll=([-+]?\d+\.\d+),([-+]?\d+\.\d+)")
PLUS_CODE_RE = re.compile(r"\b([23456789CFGHJMPQRVWX]{4,8}\+[23456789CFGHJMPQRVWX]{2,3})\b")
W3W_RE = re.compile(r"(?:^|\s)///([a-z]{3,}\.[a-z]{3,}\.[a-z]{3,})\b")
MAC_RE = re.compile(r"\b([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})\b")

# رموز الاتصال الدولية (ITU-T E.164) — مجموعة مختارة عالية الثبات
PHONE_CC = {
    "20": "مصر", "212": "المغرب", "213": "الجزائر", "216": "تونس", "218": "ليبيا",
    "249": "السودان", "962": "الأردن", "961": "لبنان", "963": "سوريا",
    "964": "العراق", "965": "الكويت", "966": "السعودية", "967": "اليمن",
    "968": "عُمان", "970": "فلسطين", "971": "الإمارات", "973": "البحرين",
    "974": "قطر", "90": "تركيا", "98": "إيران", "1": "أمريكا/كندا",
    "44": "المملكة المتحدة", "33": "فرنسا", "49": "ألمانيا", "39": "إيطاليا",
    "34": "إسبانيا", "7": "روسيا/كازاخستان", "86": "الصين", "91": "الهند",
    "81": "اليابان", "82": "كوريا الجنوبية", "92": "باكستان", "234": "نيجيريا",
    "27": "جنوب أفريقيا", "254": "كينيا", "251": "إثيوبيا", "60": "ماليزيا",
    "62": "إندونيسيا", "61": "أستراليا", "55": "البرازيل", "52": "المكسيك",
}
CCTLD = {
    ".eg": "مصر", ".sa": "السعودية", ".ae": "الإمارات", ".ma": "المغرب",
    ".dz": "الجزائر", ".tn": "تونس", ".ly": "ليبيا", ".sd": "السودان",
    ".jo": "الأردن", ".lb": "لبنان", ".sy": "سوريا", ".iq": "العراق",
    ".kw": "الكويت", ".qa": "قطر", ".bh": "البحرين", ".om": "عُمان",
    ".ps": "فلسطين", ".ye": "اليمن", ".tr": "تركيا", ".ir": "إيران",
    ".uk": "المملكة المتحدة", ".fr": "فرنسا", ".de": "ألمانيا", ".it": "إيطاليا",
    ".es": "إسبانيا", ".ru": "روسيا", ".cn": "الصين", ".in": "الهند",
    ".jp": "اليابان", ".br": "البرازيل", ".za": "جنوب أفريقيا",
}

PHONE_RE = re.compile(r"\+(\d{1,3})[\s\-.]?\d[\d\s\-.()]{6,16}\d")


def from_text(blob: str, limit: int = 40) -> dict:
    """
    مسح النص المستخرج من الملف بحثًا عن أي إشارة موقع مكتوبة.

    مفيد جدًا للمستندات وملفات HTML وملفات التطبيقات ورسائل المحادثات
    وملفات KML/GPX، ولأي ملف بقيت فيه بقايا نصية.
    """
    pts: list[dict] = []
    indicators: list[dict] = []
    if not blob:
        return {"points": pts, "indicators": indicators}
    seen = set()

    def add(lat, lon, src, snippet=""):
        if not valid_point(lat, lon):
            return
        key = (round(float(lat), 5), round(float(lon), 5), src)
        if key in seen or len(pts) >= limit:
            return
        seen.add(key)
        pts.append({"latitude": float(lat), "longitude": float(lon), "source": src,
                    "kind": "إحداثيات مكتوبة في النص", "snippet": snippet[:120],
                    "confidence": {"score": 60, "level": "متوسطة",
                                   "reasons": ["إحداثيات موجودة كنص داخل الملف — "
                                               "تدل على مكان ذُكر، وليس بالضرورة "
                                               "مكان التقاط الملف"]}})

    for m in GEO_URI.finditer(blob):
        add(m.group(1), m.group(2), "رابط geo: داخل النص", m.group(0))
    for rx, name in ((GMAPS_AT, "رابط خرائط جوجل"), (GMAPS_Q, "رابط خرائط جوجل (q=)"),
                     (OSM_URL, "رابط OpenStreetMap"), (APPLE_MAPS, "رابط خرائط آبل")):
        for m in rx.finditer(blob):
            add(m.group(1), m.group(2), name, m.group(0))
    for m in DMS_PAIR.finditer(blob):
        la = float(m.group(1)) + float(m.group(2)) / 60 + float(m.group(3)) / 3600
        lo = float(m.group(5)) + float(m.group(6)) / 60 + float(m.group(7)) / 3600
        if m.group(4).upper() == "S":
            la = -la
        if m.group(8).upper() == "W":
            lo = -lo
        add(la, lo, "إحداثيات بصيغة درجات/دقائق/ثوانٍ", m.group(0))
    for m in DEC_PAIR.finditer(blob):
        add(m.group(1), m.group(2), "زوج إحداثيات عشرية في النص", m.group(0))
    for m in PLUS_CODE_RE.finditer(blob):
        d = decode_plus_code(m.group(1))
        if d:
            add(d[0], d[1], f"Plus Code ({m.group(1)})", m.group(0))

    for m in W3W_RE.finditer(blob):
        indicators.append({"type": "what3words", "value": m.group(1),
                           "note": "عنوان what3words — يحتاج خدمة خارجية لفكّه، "
                                   "لم يُحلَّل محليًا."})
    macs = {m.group(1) for m in MAC_RE.finditer(blob)}
    if macs:
        indicators.append({"type": "عناوين MAC / معرّفات نقاط واي-فاي",
                           "value": sorted(macs)[:10], "count": len(macs),
                           "note": "معرّفات أجهزة شبكة. يمكن تحديد موقعها عبر قواعد "
                                   "خارجية لمسح الواي-فاي (WiGLE)، وهذا خارج نطاق "
                                   "التحليل المحلي."})
    ccs = {}
    for m in PHONE_RE.finditer(blob):
        raw = m.group(0)
        digits = m.group(1)
        for ln in (3, 2, 1):
            cand = digits[:ln]
            if cand in PHONE_CC:
                ccs.setdefault(PHONE_CC[cand], []).append(raw.strip())
                break
    for country, nums in ccs.items():
        indicators.append({"type": "مفتاح هاتف دولي", "country": country,
                           "value": sorted(set(nums))[:5], "count": len(nums),
                           "note": "مؤشر ترجيحي على ارتباط الملف بهذه الدولة "
                                   "(رموز ITU-T E.164)."})
    low = blob.lower()
    tlds = {}
    for m in re.finditer(r"\b[a-z0-9][a-z0-9\-]{1,62}(\.[a-z]{2,})\b", low):
        t = m.group(1)
        if t in CCTLD:
            tlds.setdefault(CCTLD[t], set()).add(m.group(0))
    for country, doms in tlds.items():
        indicators.append({"type": "نطاق إنترنت لدولة", "country": country,
                           "value": sorted(doms)[:5], "count": len(doms),
                           "note": "مؤشر ترجيحي ضعيف — النطاق قد يُستضاف في أي مكان."})
    return {"points": pts, "indicators": indicators}


# ===================================================================
#   4) التجميع والحكم
# ===================================================================

def _enrich(p: dict) -> dict:
    p = dict(p)
    p["formats"] = formats(p["latitude"], p["longitude"])
    return p


def _dedupe(points: list[dict]) -> list[dict]:
    out: list[dict] = []
    for p in points:
        dup = None
        for q in out:
            if haversine_m((p["latitude"], p["longitude"]),
                           (q["latitude"], q["longitude"])) < 1.0:
                dup = q
                break
        if dup:
            dup.setdefault("also_from", []).append(p.get("source"))
        else:
            out.append(dict(p))
    return out


def _consistency(points: list[dict], exif_times: dict, primary: dict | None) -> list[dict]:
    """فحوص تناقض حقيقية تكشف تزوير الموقع أو الوقت."""
    notes: list[dict] = []
    if primary:
        lat, lon = primary["latitude"], primary["longitude"]
        if abs(lat) < 1e-6 and abs(lon) < 1e-6:
            notes.append({"severity": "عالية",
                          "note": "⚠️ الإحداثيات (0,0) — نقطة «الجزيرة الوهمية» في "
                                  "المحيط الأطلسي، وتعني عمليًا فشل التثبيت أو حذف "
                                  "القيمة لا موقعًا حقيقيًا."})
        if (abs(lat * 1000 - round(lat * 1000)) < 1e-9
                and abs(lon * 1000 - round(lon * 1000)) < 1e-9
                and abs(lat) > 0.001):
            notes.append({"severity": "متوسطة",
                          "note": "⚠️ الإحداثيات مُقرّبة بدقة غير معتادة لأجهزة GPS "
                                  "(ثلاث خانات عشرية بالضبط) — نمط شائع عند إدخال "
                                  "الموقع يدويًا أو تزويره."})
        gdate = primary.get("gps_date_utc")
        local = exif_times.get("DateTimeOriginal")
        if gdate and local:
            try:
                gd = str(gdate).replace("-", ":")[:10]
                ld = str(local)[:10]
                if gd and ld and gd != ld:
                    notes.append({"severity": "عالية",
                                  "note": f"⚠️ تاريخ GPS ({gd}) يخالف تاريخ الالتقاط "
                                          f"({ld}). تاريخ GPS يأتي من الأقمار ولا "
                                          "يُعدَّل بسهولة، فالاختلاف مؤشر قوي على تعديل "
                                          "ساعة الجهاز أو تركيب ميتاداتا من ملف آخر."})
            except Exception:
                pass
        off = exif_times.get("OffsetTimeOriginal") or exif_times.get("OffsetTime")
        if off and isinstance(off, str) and re.match(r"^[+-]\d{2}:\d{2}$", off.strip()):
            declared = int(off[:3])
            solar = timezone_band(lon)["estimated_utc_offset"]
            if abs(declared - solar) > 2:
                notes.append({"severity": "متوسطة",
                              "note": f"⚠️ فرق التوقيت المكتوب في الصورة ({off}) يبعد "
                                      f"{abs(declared - solar)} ساعات عن التوقيت الشمسي "
                                      f"لخط الطول المسجَّل (UTC{solar:+d}) — تناقض "
                                      "يستحق التفسير."})
    if len(points) > 1:
        far = []
        for i in range(len(points)):
            for j in range(i + 1, len(points)):
                d = haversine_m((points[i]["latitude"], points[i]["longitude"]),
                                (points[j]["latitude"], points[j]["longitude"]))
                if d > 1000:
                    far.append((d, points[i].get("source"), points[j].get("source")))
        if far:
            d, s1, s2 = max(far)
            notes.append({"severity": "متوسطة",
                          "note": f"⚠️ الملف يحوي أكثر من موقع متباعد (أقصى فرق "
                                  f"{d / 1000:.1f} كم بين «{s1}» و«{s2}») — قد يدل على "
                                  "تركيب ميتاداتا أو على محتوى يذكر أماكن أخرى."})
    return notes


def analyze(containers: dict | None = None, metadata: dict | None = None,
            recovery: dict | None = None, text_blob: str = "",
            makernote: dict | None = None) -> dict:
    """
    المحرّك الكامل: يجمع كل إشارات الموقع من كل مصادر الملف ويرتّبها.

    يُستدعى من المحلّل بعد تحليل الحاويات والاسترجاع، ولا يحتاج أي اتصال شبكي.
    """
    c = containers or {}
    points: list[dict] = []
    places: dict = {}
    indicators: list[dict] = []

    # (1) EXIF GPS من كل الحاويات الممكنة
    exif_sources = [
        (((c.get("jpeg") or {}).get("app_payloads") or {}).get("Exif"), "EXIF (JPEG APP1)"),
        ((c.get("png") or {}).get("exif"), "EXIF (PNG eXIf)"),
        (c.get("tiff"), "TIFF/RAW"),
        ((c.get("riff") or {}).get("exif"), "EXIF (WebP)"),
        ((c.get("iso_bmff") or {}).get("exif"), "EXIF (HEIC/MP4)"),
    ]
    exif_times: dict = {}
    for src, label in exif_sources:
        if not isinstance(src, dict):
            continue
        p = from_exif_gps(src, label)
        if p:
            points.append(p)
        for key in ("DateTimeOriginal", "OffsetTime", "OffsetTimeOriginal"):
            v = ((src.get("ExifIFD") or {}).get(key) or {}).get("raw")
            if v and key not in exif_times:
                exif_times[key] = v

    # (2) حاويات الفيديو/الصور الحديثة (ISO 6709)
    points.extend(from_bmff(c.get("iso_bmff") or {}))

    # (3) XMP وIPTC
    xmp = ((c.get("jpeg") or {}).get("app_payloads") or {}).get("XMP")
    if isinstance(xmp, str):
        x = from_xmp(xmp)
        points.extend(x["points"])
        places.update(x["places"])
    irb = ((c.get("jpeg") or {}).get("app_payloads") or {}).get("Photoshop_IRB") or {}
    places.update(from_iptc(irb.get("IPTC") or {}))

    # (4) الموقع من الميتاداتا الممسوحة المستعادة — أهم ما يميّز هذا المحرّك
    for frag in (recovery or {}).get("exif_fragments", []):
        g = frag.get("gps") or {}
        if valid_point(g.get("latitude"), g.get("longitude")):
            points.append({
                "latitude": float(g["latitude"]), "longitude": float(g["longitude"]),
                "source": f"♻️ شظية EXIF مستعادة عند الإزاحة {frag.get('offset')}",
                "kind": "إحداثيات مُقاسة (مُستعادة بعد المسح)",
                "altitude_m": g.get("altitude_m"),
                "confidence": {"score": 80, "level": "عالية",
                               "reasons": ["إحداثيات نجت داخل بقايا ميتاداتا مُزالة — "
                                           "دليل قوي لأنها لم تُكتب للعرض"]}})
    for pkt in (recovery or {}).get("xmp_packets", [])[:10]:
        raw = pkt.get("raw") or pkt.get("text") or ""
        if raw:
            x = from_xmp(raw)
            for p in x["points"]:
                p["source"] = f"♻️ XMP مستعادة عند الإزاحة {pkt.get('offset')}"
            points.extend(x["points"])
            places.update(x["places"])

    # (5) النصوص الخام
    t = from_text(text_blob or "")
    points.extend(t["points"])
    indicators.extend(t["indicators"])

    # (6) ترتيب وتجميع
    points = _dedupe(points)
    measured = [p for p in points if "مُقاسة" in (p.get("kind") or "")]
    measured.sort(key=lambda p: -(p.get("confidence", {}).get("score", 0)))
    primary = measured[0] if measured else (points[0] if points else None)

    out: dict = {
        "located": bool(primary),
        "points_count": len(points),
        "measured_points": len(measured),
        "points": [_enrich(p) for p in points],
        "place_names": places,
        "indirect_indicators": indicators,
        "exif_time_context": exif_times,
    }
    if primary:
        out["primary"] = _enrich(primary)
    out["consistency_checks"] = _consistency(points, exif_times, primary)

    if primary:
        f = out["primary"]["formats"]
        conf = primary.get("confidence", {})
        out["verdict"] = (
            f"📍 الموقع محدَّد: {f['decimal']} ({f['dms']}) — المصدر: "
            f"{primary.get('source')} · ثقة {conf.get('level', '—')} "
            f"({conf.get('score', '—')}/100).")
    elif places:
        out["verdict"] = ("🗺️ لا توجد إحداثيات رقمية، لكن الملف يحمل أسماء أماكن "
                          "مكتوبة: " + "، ".join(
                              f"{k}: {v['value']}" for k, v in list(places.items())[:4]))
    elif indicators:
        out["verdict"] = ("🧭 لا يوجد موقع مباشر. توجد مؤشرات ترجيحية فقط "
                          f"({len(indicators)}) تُضيّق النطاق الجغرافي ولا تحدّد نقطة.")
    else:
        out["verdict"] = ("لا توجد أي إشارة موقع في هذا الملف — لا إحداثيات ولا أسماء "
                          "أماكن ولا مؤشرات غير مباشرة.")
    return out


# ===================================================================
#   5) الربط بين أدلة القضية مكانيًا
# ===================================================================

def cluster(points: list[dict], radius_m: float = 150.0) -> dict:
    """
    تجميع نقاط عدة أدلة مكانيًا: هل التُقطت في نفس المكان؟ وما أقصى تباعد؟

    تجميع بسيط بالوصل المتعدي ضمن نصف قطر — بلا مكتبات خارجية.
    """
    pts = [p for p in points if valid_point(p.get("latitude"), p.get("longitude"))]
    n = len(pts)
    if not n:
        return {"clusters": [], "count": 0}
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    maxd, pair = 0.0, None
    for i in range(n):
        for j in range(i + 1, n):
            d = haversine_m((pts[i]["latitude"], pts[i]["longitude"]),
                            (pts[j]["latitude"], pts[j]["longitude"]))
            if d > maxd:
                maxd, pair = d, (i, j)
            if d <= radius_m:
                parent[find(i)] = find(j)
    groups: dict = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(pts[i])
    clusters = []
    for members in groups.values():
        la = sum(m["latitude"] for m in members) / len(members)
        lo = sum(m["longitude"] for m in members) / len(members)
        clusters.append({"center": {"latitude": la, "longitude": lo},
                         "size": len(members),
                         "members": [m.get("label") or m.get("source") for m in members],
                         "formats": formats(la, lo)})
    clusters.sort(key=lambda c: -c["size"])
    return {"clusters": clusters, "count": len(clusters),
            "max_separation_m": round(maxd, 1),
            "max_separation_pair": ([pts[pair[0]].get("label") or pts[pair[0]].get("source"),
                                     pts[pair[1]].get("label") or pts[pair[1]].get("source")]
                                    if pair else None)}
