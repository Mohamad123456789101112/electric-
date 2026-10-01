/* ============================================================
   إلكترو بلوك — توليد كود MicroPython من شجرة البرنامج AST
   ============================================================ */

const HELPERS = {
  pin_common: `# ذاكرة المنافذ — عشان ميتمش إنشاء المنفذ كل مرة
_dpins = {}
_modes = {}

def _get_pin(pin, mode):
    """الحصول على كائن المنفذ بالنوع المطلوب"""
    p = _dpins.get(pin)
    if p is None or p[1] != mode:
        if mode == 'out':
            p = (Pin(pin, Pin.OUT), mode)
        elif mode == 'pullup':
            p = (Pin(pin, Pin.IN, Pin.PULL_UP), mode)
        else:
            p = (Pin(pin, Pin.IN), mode)
        _dpins[pin] = p
    return p[0]`,

  pin_mode: `def pin_mode(pin, mode):
    """ضبط نوع المنفذ من بلوك (اضبط المنفذ)"""
    _modes[pin] = mode
    _get_pin(pin, mode)`,

  dwrite: `def dwrite(pin, v):
    """كتابة رقمية على المنفذ (1 = تشغيل / 0 = إيقاف)"""
    _get_pin(pin, 'out').value(v)`,

  dread: `def dread(pin):
    """قراءة رقمية من المنفذ (زر مضغوط مع مقاومة سحب = 0)"""
    return _get_pin(pin, _modes.get(pin, 'in')).value()`,

  awrite: `_pwm = {}

def pwm(pin, duty):
    """ضبط شدة الإضاءة/السرعة بنسبة من 0 إلى 100 (PWM)"""
    p = _pwm.get(pin)
    if p is None:
        p = PWM(Pin(pin), freq=1000)
        _pwm[pin] = p
    d = int(duty)
    if d < 0: d = 0
    if d > 100: d = 100
    p.duty_u16(d * 655)`,

  servo: `_servo = {}

def servo(pin, angle):
    """تحريك السيرفو لزاوية من 0 إلى 180 درجة"""
    p = _servo.get(pin)
    if p is None:
        p = PWM(Pin(pin), freq=50)
        _servo[pin] = p
    a = int(angle)
    if a < 0: a = 0
    if a > 180: a = 180
    p.duty_ns(500000 + a * 10000)`,

  tone: `def tone(pin, freq):
    """تشغيل نغمة على البازر بالتردد المطلوب"""
    p = _pwm.get(pin)
    if p is None:
        p = PWM(Pin(pin), duty_u16=32768)
        _pwm[pin] = p
    p.freq(max(1, int(freq)))

def no_tone(pin):
    """إيقاف النغمة على البازر"""
    p = _pwm.get(pin)
    if p is not None:
        p.duty_u16(0)`,

  aread: `_adc = {}

def aread(pin):
    """قراءة تناظرية من 0 إلى 1023 (مقاومة متغيرة / حساس)"""
    a = _adc.get(pin)
    if a is None:
        a = ADC(Pin(pin))
        a.atten(ADC.ATTN_11DB)
        _adc[pin] = a
    return a.read_u16() // 64`,

  distance: `def distance(trig, echo):
    """قياس المسافة بالسنتيمتر بحساس الموجات فوق الصوتية"""
    t = _get_pin(trig, 'out')
    e = _get_pin(echo, _modes.get(echo, 'in'))
    t.value(0)
    time.sleep_us(2)
    t.value(1)
    time.sleep_us(10)
    t.value(0)
    start = time.ticks_us()
    while e.value() == 0:
        if time.ticks_diff(time.ticks_us(), start) > 30000:
            return 999
    start = time.ticks_us()
    while e.value() == 1:
        if time.ticks_diff(time.ticks_us(), start) > 30000:
            return 999
    return time.ticks_diff(time.ticks_us(), start) // 58`,
};

/**
 * توليد كود MicroPython كامل من AST
 * @returns {string}
 */
export function generatePython(program) {
  const ctx = new PyCtx();
  const setupLines = program.setup.map((s) => ctx.stmt(s, 0)).filter(Boolean);
  const loopLines = program.loop.map((s) => ctx.stmt(s, 0)).filter(Boolean);

  const parts = [];
  parts.push(
    [
      '# ⚡ الكود ده اتولد تلقائيًا من "إلكترو بلوك"',
      '# الجهاز: ESP32 — نظام التشغيل: MicroPython',
      '# تقدر تنقل الكود ده زي ما هو وتشغّله بأي محرر MicroPython',
      'from machine import Pin, PWM, ADC',
      'import time',
    ].join('\n')
  );

  if (ctx.varNotes.length) parts.push('# المتغيرات: ' + ctx.varNotes.join('، '));

  const used = ctx.used;
  const helperList = [];
  if (used.has('dwrite') || used.has('dread') || used.has('pinmode') || used.has('distance')) helperList.push('pin_common');
  if (used.has('pinmode')) helperList.push('pin_mode');
  if (used.has('dwrite')) helperList.push('dwrite');
  if (used.has('dread')) helperList.push('dread');
  if (used.has('awrite')) helperList.push('awrite');
  if (used.has('servo')) helperList.push('servo');
  if (used.has('tone') || used.has('notone')) helperList.push('tone');
  if (used.has('aread')) helperList.push('aread');
  if (used.has('distance')) helperList.push('distance');

  if (helperList.length) {
    parts.push(['', '# ===== دوال مساعدة ====='].concat(helperList.map((k) => HELPERS[k])).join('\n\n'));
  }
  if (used.has('randint')) {
    parts.push('import random');
  }

  const body = [];
  if (setupLines.length) {
    body.push('', '# ===== 🚀 عند البدء (مرة واحدة) =====', ...setupLines);
  }
  if (loopLines.length) {
    body.push('', '# ===== 🔁 دائمًا (يتكرر للأبد) =====', 'while True:', ...indent(loopLines));
  }
  parts.push(body.join('\n'));

  return parts.join('\n\n').replace(/\n{3,}/g, '\n\n').trim() + '\n';
}

function indent(lines) {
  if (!lines.length) return ['    time.sleep_ms(100)'];
  // كل عنصر ممكن يكون متعدد الأسطر (if/for) — لازم نبصّط كل الأسطر الأول
  return lines
    .flatMap((l) => String(l).split('\n'))
    .map((l) => (l.trim() === '' ? '' : '    ' + l));
}

class PyCtx {
  constructor() {
    this.used = new Set();
    this.varMap = new Map();
    this.varNotes = [];
  }

  pyName(name) {
    // أسماء المتغيرات العربية لازم تتحول لأسماء إنجليزية صالحة
    if (/^[A-Za-z_][A-Za-z0-9_]*$/.test(name)) return name;
    if (!this.varMap.has(name)) {
      this.varMap.set(name, `var_${this.varMap.size + 1}`);
      this.varNotes.push(`${this.varMap.get(name)} = "${name}"`);
    }
    return this.varMap.get(name);
  }

  stmt(s, depth) {
    switch (s.t) {
      case 'sleep': {
        const v = this.expr(s.ms);
        if (s.unit === 's') return `time.sleep(${v})`;
        return `time.sleep_ms(${maybeInt(v)})`;
      }
      case 'pinmode': {
        this.used.add('pinmode');
        return `pin_mode(${s.pin}, '${s.mode === 'pullup' ? 'pullup' : s.mode === 'in' ? 'in' : 'out'}')`;
      }
      case 'dwrite': {
        this.used.add('dwrite');
        return `dwrite(${s.pin}, ${s.val})`;
      }
      case 'awrite': {
        this.used.add('awrite');
        return `pwm(${s.pin}, ${this.expr(s.duty)})`;
      }
      case 'servo': {
        this.used.add('servo');
        return `servo(${s.pin}, ${this.expr(s.angle)})`;
      }
      case 'tone': {
        this.used.add('tone');
        const dur = s.dur && s.dur.t === 'num' ? s.dur.v : null;
        const freq = this.expr(s.freq);
        if (dur && dur > 0) {
          return [`tone(${s.pin}, ${freq})`, `time.sleep_ms(${dur})`, `no_tone(${s.pin})`].join('\n');
        }
        return `tone(${s.pin}, ${freq})`;
      }
      case 'notone': {
        this.used.add('notone');
        return `no_tone(${s.pin})`;
      }
      case 'print': {
        const v = s.val ? this.expr(s.val) : "''";
        return `print(${v})`;
      }
      case 'waituntil': {
        const c = this.expr(s.cond);
        return `while not (${c}):\n    time.sleep_ms(10)`;
      }
      case 'if': {
        const chunks = [];
        s.clauses.forEach((cl, i) => {
          const kw = i === 0 ? 'if' : 'elif';
          chunks.push(`${kw} ${this.expr(cl.cond)}:`);
          chunks.push(...this.body(cl.then));
        });
        if (s.orelse) {
          chunks.push('else:');
          chunks.push(...this.body(s.orelse));
        }
        return chunks.join('\n');
      }
      case 'repeat': {
        return [`for _i in range(${maybeInt(this.expr(s.count))}):`, ...this.body(s.body)].join('\n');
      }
      case 'while': {
        const c = this.expr(s.cond);
        return [`while ${s.until ? 'not ' : ''}(${c}):`, ...this.body(s.body)].join('\n');
      }
      case 'flow':
        return s.kind === 'continue' ? 'continue' : 'break';
      case 'assign':
        return `${this.pyName(s.name)} = ${this.expr(s.val)}`;
      case 'change':
        return `${this.pyName(s.name)} = ${this.pyName(s.name)} + (${this.expr(s.val)})`;
      default:
        return `# (بلوك غير معروف: ${s.t})`;
    }
  }

  body(stmts) {
    const lines = stmts.map((x) => this.stmt(x)).filter(Boolean);
    return indent(lines);
  }

  expr(e) {
    if (!e) return '0';
    switch (e.t) {
      case 'num':
        return numLit(e.v);
      case 'str':
        return pyStr(e.v);
      case 'bool':
        return e.v ? 'True' : 'False';
      case 'var':
        return this.pyName(e.name);
      case 'bin': {
        const a = this.expr(e.a);
        const b = this.expr(e.b);
        return `(${a} ${e.op} ${b})`;
      }
      case 'un': {
        if (e.op === 'not') return `(not ${this.expr(e.a)})`;
        if (e.op === 'neg') return `(-${this.expr(e.a)})`;
        return `abs(${this.expr(e.a)})`;
      }
      case 'join': {
        if (!e.items.length) return "''";
        return '(' + e.items.map((i) => `str(${this.expr(i)})`).join(' + ') + ')';
      }
      case 'dread':
        this.used.add('dread');
        return `dread(${e.pin})`;
      case 'aread':
        this.used.add('aread');
        return `aread(${e.pin})`;
      case 'distance':
        this.used.add('distance');
        return `distance(${e.trig}, ${e.echo})`;
      case 'randint':
        this.used.add('randint');
        return `random.randint(${maybeInt(this.expr(e.a))}, ${maybeInt(this.expr(e.b))})`;
      default:
        return '0';
    }
  }
}

function maybeInt(v) {
  // حوّل القيم الحرفية لـ int(...) لو مش رقم صريح
  if (/^-?\d+$/.test(v.trim())) return v.trim();
  return `int(${v})`;
}

function numLit(v) {
  if (Number.isInteger(v)) return String(v);
  return String(v);
}

function pyStr(s) {
  return '"' + String(s).replace(/\\/g, '\\\\').replace(/"/g, '\\"').replace(/\n/g, '\\n').replace(/\r/g, '\\r').replace(/\t/g, '\\t') + '"';
}
