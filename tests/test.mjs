/* اختبارات إلكترو بلوك — المترجم ومولد كود MicroPython
   تشغيل: node tests/test.mjs */
import { compileProgram, FakeBlock } from '../js/compiler.js';
import { generatePython } from '../js/pygen.js';

let passed = 0, failed = 0;
function ok(cond, name) {
  if (cond) { passed++; console.log('  ✅', name); }
  else { failed++; console.log('  ❌', name); }
}

function compile(blocks) {
  const { program, warnings } = compileProgram(blocks);
  return { program, warnings, py: generatePython(program) };
}

/* ===== 1) وميض LED ===== */
console.log('\n① وميض LED');
{
  const onStart = new FakeBlock('eb_on_start');
  const printB = new FakeBlock('eb_print');
  printB._inputs.VAL = { type: 'text', getFieldValue: () => 'أهلًا', getInputTargetBlock: () => null, getNextBlock: () => null };
  onStart.setNext(printB);

  const loop = new FakeBlock('eb_loop');
  const d1 = new FakeBlock('eb_dwrite', { PIN: '2', VAL: '1' });
  const s1 = new FakeBlock('eb_sleep', { UNIT: 'ms' });
  s1._inputs.MS = numBlock(500);
  const d2 = new FakeBlock('eb_dwrite', { PIN: '2', VAL: '0' });
  const s2 = new FakeBlock('eb_sleep', { UNIT: 'ms' });
  s2._inputs.MS = numBlock(500);
  d1.setNext(s1); s1.setNext(d2); d2.setNext(s2);
  loop.setNext(d1);

  const { program, warnings, py } = compile([onStart, loop]);
  ok(warnings.length === 0, 'مفيش تحذيرات');
  ok(program.setup.length === 1 && program.loop.length === 4, 'عدد الأوامر صح');
  ok(py.includes('dwrite(2, 1)'), 'python: dwrite(2, 1)');
  ok(py.includes('dwrite(2, 0)'), 'python: dwrite(2, 0)');
  ok(py.includes('time.sleep_ms(500)'), 'python: sleep_ms(500)');
  ok(py.includes('while True:'), 'python: while True');
  ok(py.includes('print("أهلًا")'), 'python: print عربي');
}

/* ===== 2) زر يشغل LED (لو جوه شرط) ===== */
console.log('\n② زر يشغّل LED');
{
  const loop = new FakeBlock('eb_loop');
  const ifB = new FakeBlock('controls_if');
  ifB._fields = {};
  ifB._inputs = {
    IF0: cmpBlock(dreadBlock(4), numBlock(0)),
    DO0: new FakeBlock('eb_dwrite', { PIN: '2', VAL: '1' }),
  };
  ifB._inputs.ELSE = new FakeBlock('eb_dwrite', { PIN: '2', VAL: '0' });
  ifB.getInput = (n) => (n === 'IF0' || n === 'DO0' || n === 'ELSE' ? { name: n } : null);
  loop.setNext(ifB);

  const { py } = compile([loop]);
  ok(py.includes('if (dread(4) == 0):'), 'python: الشرط بالزر (سحب = 0)');
  ok(py.includes('dwrite(2, 1)'), 'python: تشغيل الليد');
  ok(py.includes('else:'), 'python: else');
  const ifIdx = py.indexOf('if (dread(4)');
  const doIdx = py.indexOf('dwrite(2, 1)');
  ok(py.slice(ifIdx, doIdx).includes('\n    dwrite') || py[doIdx - 1] === ' ' || py.substring(doIdx - 5, doIdx).trim() === '', 'الترتيب سليم');
  // التحقق من الـ indentation الحقيقي
  const lines = py.split('\n');
  const di = lines.findIndex((l) => l.includes('dwrite(2, 1)'));
  ok(lines[di].startsWith('        '), 'البلوك جوه اللوب جوه الشرط = 8 مسافات');
}

/* ===== 3) متغير عربي + سيرفو ===== */
console.log('\n③ متغيرات وسيرفو');
{
  const loop = new FakeBlock('eb_loop');
  const repeat = new FakeBlock('controls_repeat_ext');
  repeat._fields = {};
  repeat._inputs = {
    TIMES: numBlock(3),
    DO: new FakeBlock('eb_swrite', { PIN: '13' }, { ANGLE: varBlock('الزاوية') }),
  };
  loop.setNext(repeat);

  const { py } = compile([loop]);
  ok(py.includes('var_1'), 'المتغير العربي اتحول لاسم إنجليزي صالح');
  ok(py.includes('الزاوية'), 'والاسم الأصلي موجود في التعليق');
  ok(py.includes('servo(13, var_1)'), 'استدعاء السيرفو بالمتغير');
  ok(py.includes('for _i in range(3):'), 'python: for range');
  // indentation: السيرفو جوه التكرار
  const lines = py.split('\n');
  const si = lines.findIndex((l) => l.includes('servo(13, var_1)'));
  ok(lines[si].startsWith('        '), 'سيرفو جوه for جوه while = 8 مسافات');
}

/* ===== 4) حساس مسافة + بازر ===== */
console.log('\n④ حساس المسافة');
{
  const loop = new FakeBlock('eb_loop');
  const ifB = new FakeBlock('controls_if');
  ifB._fields = {};
  ifB._inputs = {
    IF0: cmpBlock(distBlock(12, 14), numBlock(20), 'LT'),
    DO0: new FakeBlock('eb_tone', { PIN: '15' }, { FREQ: numBlock(900), DUR: numBlock(150) }),
  };
  ifB.getInput = (n) => (n === 'IF0' || n === 'DO0' ? { name: n } : null);
  loop.setNext(ifB);

  const { py } = compile([loop]);
  ok(py.includes('distance(12, 14)'), 'python: distance(12, 14)');
  ok(py.includes('tone(15, 900)'), 'python: tone(15, 900)');
  ok(py.includes('no_tone(15)'), 'python: no_tone بعد المدة');
  ok(py.includes('time.ticks_us()'), 'python: حساس الموجات في التعريفات');
  ok(py.includes('if (distance(12, 14) < 20):'), 'python: الشرط كامل');
}

/* ===== 5) قراءة تناظرية + PWM ===== */
console.log('\n⑤ المقاومة المتغيرة و PWM');
{
  const loop = new FakeBlock('eb_loop');
  const aw = new FakeBlock('eb_awrite', { PIN: '2' }, { DUTY: arithBlock(areadBlock(32), numBlock(10.23), 'DIVIDE') });
  loop.setNext(aw);
  const { py } = compile([loop]);
  ok(py.includes('aread(32)'), 'python: aread(32)');
  ok(py.includes('duty_u16'), 'python: PWM duty');
  ok(py.includes('pwm(2, (aread(32) / 10.23))'), 'python: القسمة كاملة');
}

/* ===== 6) انتظر حتى ===== */
console.log('\n⑥ انتظر حتى');
{
  const loop = new FakeBlock('eb_loop');
  const w = new FakeBlock('eb_wait_until', {}, { COND: cmpBlock(dreadBlock(4), numBlock(0), 'EQ') });
  loop.setNext(w);
  const { py } = compile([loop]);
  ok(py.includes('while not ('), 'python: while not');
  ok(py.includes('time.sleep_ms(10)'), 'python: الانتظار الصغير جوه اللوب');
}

/* ===== 7) نغمات متتالية (عند البدء بس = من غير while True) ===== */
console.log('\n⑦ نغمة عند البدء بدون تكرار');
{
  const onStart = new FakeBlock('eb_on_start');
  const t1 = new FakeBlock('eb_tone', { PIN: '15' }, { FREQ: numBlock(262), DUR: numBlock(300) });
  onStart.setNext(t1);
  const { warnings, py } = compile([onStart]);
  ok(warnings.length === 0, 'مفيش تحذيرات');
  ok(!py.includes('while True:'), 'مفيش تكرار — البرنامج يعمل مرة واحدة');
  ok(py.includes('tone(15, 262)'), 'النغمة موجودة');
  ok(py.includes('time.sleep_ms(300)'), 'مدة النغمة موجودة');
}

/* ===== 8) التحذيرات ===== */
console.log('\n⑧ التحذيرات والبلوكات السايبة');
{
  // بلوك سايب من غير hat
  const stray = new FakeBlock('eb_dwrite', { PIN: '2', VAL: '1' });
  const { warnings } = compile([stray]);
  ok(warnings.some((w) => w.includes('بره')), 'بلوك سايب بينتج تحذير');

  // من غير أي حاجة
  const { warnings: w2 } = compile([]);
  ok(w2.some((w) => w.includes('ابدأ')), 'برنامج فاضي = نصيحة البداية');
}

/* ===== 9) elif والتكرار المتداخل ===== */
console.log('\n⑨ شروط متعددة وتكرار متداخل');
{
  const loop = new FakeBlock('eb_loop');
  const outer = new FakeBlock('controls_repeat_ext');
  outer._fields = {};
  const inner = new FakeBlock('controls_repeat_ext');
  inner._fields = {};
  inner._inputs = { TIMES: numBlock(2), DO: new FakeBlock('eb_dwrite', { PIN: '2', VAL: '1' }) };
  outer._inputs = { TIMES: numBlock(3), DO: inner };
  loop.setNext(outer);

  const { py } = compile([loop]);
  const lines = py.split('\n');
  const iOuter = lines.findIndex((l) => l.trim().startsWith('for _i in range(3)'));
  const iInner = lines.findIndex((l) => l.trim().startsWith('for _i in range(2)'));
  const iD = lines.findIndex((l) => l.trim() === 'dwrite(2, 1)');
  ok(iOuter !== -1 && iInner > iOuter && iD > iInner, 'الترتيب: الخارجي ← الداخلي ← الأمر');
  ok(lines[iOuter].startsWith('    ') && lines[iInner].startsWith('        ') && lines[iD].startsWith('            '), 'الـ indentation متداخل صح (4/8/12)');
}

/* ===== بلوكات مساعدة ===== */
function numBlock(v) {
  return { type: 'math_number', getFieldValue: () => String(v), getInputTargetBlock: () => null, getNextBlock: () => null };
}
function varBlock(name) {
  return { type: 'variables_get', getFieldValue: () => name, getInputTargetBlock: () => null, getNextBlock: () => null };
}
function dreadBlock(pin) {
  return { type: 'eb_dread', getFieldValue: () => String(pin), getInputTargetBlock: () => null, getNextBlock: () => null };
}
function areadBlock(pin) {
  return { type: 'eb_aread', getFieldValue: () => String(pin), getInputTargetBlock: () => null, getNextBlock: () => null };
}
function distBlock(trig, echo) {
  return {
    type: 'eb_distance',
    getFieldValue: (n) => (n === 'TRIG' ? String(trig) : String(echo)),
    getInputTargetBlock: () => null,
    getNextBlock: () => null,
  };
}
function cmpBlock(a, b, op = 'EQ') {
  return {
    type: 'logic_compare',
    getFieldValue: () => op,
    getInputTargetBlock: (n) => (n === 'A' ? a : b),
    getNextBlock: () => null,
  };
}
function arithBlock(a, b, op = 'ADD') {
  return {
    type: 'math_arithmetic',
    getFieldValue: () => op,
    getInputTargetBlock: (n) => (n === 'A' ? a : b),
    getNextBlock: () => null,
  };
}

console.log(`\n========== النتيجة: ${passed} نجح | ${failed} فشل ==========`);
process.exit(failed ? 1 : 0);
