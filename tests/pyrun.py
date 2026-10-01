"""تشغيل الكود المولد في بايثون حقيقي مع stub لوحدة machine — تحقق دلالي"""
import sys, time, types

# ===== stub لوحدة machine =====
LOG = []
class StubPin:
    OUT = 1
    IN = 0
    PULL_UP = 2
    def __init__(self, pin, mode=-1, pull=None):
        self.pin, self.mode, self.pull = pin, mode, pull
        self._value = 0
    def value(self, v=None):
        if v is None:
            return PIN_READS.get(self.pin, 0)
        LOG.append(('dw', self.pin, v))
        self._value = v
class StubPWM:
    def __init__(self, pin, freq=None, duty_u16=None):
        self.pin = pin.pin if isinstance(pin, StubPin) else pin
        self.freq_ = freq or 0
        self.duty_ = duty_u16 or 0
    def freq(self, f):
        self.freq_ = f
        LOG.append(('tone', self.pin, f))
    def duty_u16(self, d):
        self.duty_ = d
        LOG.append(('pwm', self.pin, d))
    def duty_ns(self, ns):
        LOG.append(('servo', self.pin, ns))
class StubADC:
    ATTN_11DB = 3
    def __init__(self, pin):
        self.pin = pin
    def atten(self, a):
        pass
    def read_u16(self):
        return ADC_VALUE

PIN_READS = {4: 0}   # الزر مضغوط (سحب)
ADC_VALUE = 600       # 600//64 = 9
DISTANCE = 50         # سم

machine = types.ModuleType('machine')
machine.Pin = StubPin
machine.PWM = StubPWM
machine.ADC = StubADC
sys.modules['machine'] = machine

# shims للوقت (MicroPython فقط عنده sleep_ms/ticks)
_t0 = time.monotonic_ns() // 1000
time.sleep_ms = lambda ms: time.sleep(ms / 1000)
time.sleep_us = lambda us: None
time.ticks_us = lambda: (time.monotonic_ns() // 1000) - _t0
time.ticks_diff = lambda a, b: a - b

# نقرأ الكود ونحوّل while True إلى 3 لفات عشان البرنامج يخلص
path = sys.argv[1]
code = open(path, encoding='utf-8').read()
code = code.replace('while True:', 'for _eb_loop in range(3):')

g = {'__name__': '__main__'}
old_stdout = sys.stdout
sys.stdout = types.SimpleNamespace(write=lambda s: LOG.append(('print', s)), flush=lambda: None)
try:
    exec(compile(code, path, 'exec'), g)
finally:
    sys.stdout = old_stdout

# ===== التحقق =====
name = path.split('/')[-1]
fails = []
def check(cond, msg):
    if not cond:
        fails.append(msg)

if name == 'blink.py':
    dw = [x for x in LOG if x[0] == 'dw']
    check(('dw', 2, 1) in dw and ('dw', 2, 0) in dw, 'الليد ولاّ وطفي')
    check(any(x[0] == 'print' for x in LOG), 'الطباعة اشتغلت')
elif name == 'full.py':
    dw = [x for x in LOG if x[0] == 'dw']
    sv = [x for x in LOG if x[0] == 'servo']
    tone = [x for x in LOG if x[0] == 'tone']
    pwm = [x for x in LOG if x[0] == 'pwm']
    # الزر مضغوط (قراءة 0) → نغمة 880
    check(('tone', 15, 880) in tone, 'النغمة اتشغلت عند الضغط')
    # pwm duty 50% → 50*655 = 32750
    check(any(x[0] == 'pwm' and x[1] == 2 and abs(x[2] - 32750) < 10 for x in pwm), 'PWM 50%')
    # سيرفو 3 مرات في كل لفة (لوب 3) = 9 على الأقل
    check(len(sv) >= 9, f'السيرفو اتحرك كفاية ({len(sv)})')
    # المسافة اتطبعت (999 = قيمة الـ timeout في الستب)
    check(any(x[0] == 'print' and '999' in str(x[1]) for x in LOG), 'المسافة اتطبعت')
elif name == 'mod.py':
    dw = [x for x in LOG if x[0] == 'dw']
    # i بيبدأ 0 وبيزيد 1 قبل الفحص → دايمًا فردي → else (بدل ما يبقى modulo شغال)
    check(len(dw) == 3 and all(x[2] == 0 for x in dw), 'modulo بيختار الفرع الصح')

if fails:
    print(f'❌ {name}: ' + ' | '.join(fails))
    print('LOG:', LOG[:40])
    sys.exit(1)
print(f'✅ {name} — الكود المولد شغال صح في بايثون حقيقي')
