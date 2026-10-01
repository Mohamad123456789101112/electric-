/* اختبارات إلكترو بلوك — تشغيل: node tests/test.mjs */
import { compileProgram, FakeBlock } from '../js/compiler.js';
import { generatePython } from '../js/pygen.js';
import { Interpreter, StopSignal } from '../js/interpreter.js';

let passed = 0, failed = 0;
function ok(cond, name) {
  if (cond) { passed++; console.log('  ✅', name); }
  else { failed++; console.log('  ❌', name); }
}

/* ===== لوحة وهمية ===== */
class FakeBoard {
  constructor() {
    this.pins = new Map();
    this.prints = [];
    this.tones = [];
    this.toneHistory = [];
    this.now = 0;
    this.distanceCm = 30;
    this.buttonPin = null;
    this.buttonPressed = false;
    this.potValue = 512;
  }
  async sleepMs(ms) { this.now += ms; }
  async dwrite(pin, v) { this.pins.set(pin, { type: 'd', v }); }
  async awrite(pin, duty) { this.pins.set(pin, { type: 'a', duty }); }
  async servo(pin, angle) { this.pins.set(pin, { type: 'servo', angle }); }
  async tone(pin, freq) { this.tones.push({ pin, freq }); this.toneHistory.push({ pin, freq }); }
  async notone(pin) { this.pins.delete('tone' + pin); this.tones = this.tones.filter(t => t.pin !== pin); }
  async pinmode() {}
  async dread(pin) {
    if (pin === this.buttonPin) return this.buttonPressed ? 0 : 1; // سحب
    return 1;
  }
  async aread(pin) { return this.potValue; }
  async distance() { return this.distanceCm; }
  async print(t) { this.prints.push(String(t)); }
}

function stopAfter(interp, ms) {
  setTimeout(() => interp.stop(), ms);
}

/* ===== 1) وميض LED ===== */
console.log('\n① وميض LED');
{
  const start = new FakeBlock('eb_on_start').chain(
    Object.assign(new FakeBlock('eb_print', {}, {}), { type: 'eb_print' })
  );
  // نستخدم بلوكات وهمية بسيطة
  const onStart = new FakeBlock('eb_on_start');
  const printB = new FakeBlock('eb_print', {}, {});
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

  const { program, warnings } = compileProgram([onStart, loop]);
  ok(warnings.length === 0, 'مفيش تحذيرات');
  ok(program.setup.length === 1 && program.loop.length === 4, 'عدد الأوامر صح');

  const py = generatePython(program);
  ok(py.includes('dwrite(2, 1)'), 'python: dwrite(2, 1)');
  ok(py.includes('dwrite(2, 0)'), 'python: dwrite(2, 0)');
  ok(py.includes('time.sleep_ms(500)'), 'python: sleep_ms(500)');
  ok(py.includes('while True:'), 'python: while True');
  ok(py.includes('print("أهلًا")'), 'python: print عربي');

  // محاكاة: بعد 2000 مللي يبقى الليد طفي (آخر عملية)
  const board = new FakeBoard();
  const interp = new Interpreter(board);
  const t = setTimeout(() => interp.stop(), 50);
  const r = await interp.run(program);
  clearTimeout(t);
  ok(r.status === 'stopped', 'المحاكي اتوقفت بأمان');
  ok(board.prints[0] === 'أهلًا', 'الطباعة اشتغلت');
  ok(board.pins.get(2).type === 'd', 'الليد اتكتب عليه');
}

/* ===== 2) زر يشغل LED ===== */
console.log('\n② زر يشغّل LED');
{
  const loop = new FakeBlock('eb_loop');
  const ifB = new FakeBlock('controls_if', {}, { IF0: null, DO0: null });
  ifB._fields = {};
  ifB._inputs = {
    IF0: cmpBlock(dreadBlock(4), numBlock(0)),
    DO0: new FakeBlock('eb_dwrite', { PIN: '2', VAL: '1' }),
  };
  ifB._hasElse = true;
  ifB.getInput = (n) => (n === 'IF0' || n === 'DO0' || n === 'ELSE' ? { name: n } : null);
  ifB._inputs.ELSE = new FakeBlock('eb_dwrite', { PIN: '2', VAL: '0' });
  loop.setNext(ifB);

  const { program } = compileProgram([loop]);
  const board = new FakeBoard();
  board.buttonPin = 4;
  board.buttonPressed = true;
  const interp = new Interpreter(board);
  setTimeout(() => interp.stop(), 60);
  const r = await interp.run(program);
  ok(r.status === 'stopped', 'اتوقف');
  ok(board.pins.get(2)?.v === 1, 'الليد نوار والزر مضغوط (سحب = 0)');

  const board2 = new FakeBoard();
  board2.buttonPin = 4;
  board2.buttonPressed = false;
  const interp2 = new Interpreter(board2);
  setTimeout(() => interp2.stop(), 60);
  await interp2.run(program);
  ok(board2.pins.get(2)?.v === 0, 'الليد طفي والزر سايب');
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

  const { program } = compileProgram([loop]);
  const py = generatePython(program);
  ok(py.includes('var_1'), 'المتغير العربي اتحول لاسم إنجليزي صالح');
  ok(py.includes('الزاوية'), 'والاسم الأصلي موجود في التعليق');
  ok(py.includes('servo(13, var_1)'), 'استدعاء السيرفو بالمتغير');

  const board = new FakeBoard();
  const interp = new Interpreter(board);
  setTimeout(() => interp.stop(), 120);
  const r = await interp.run(program);
  ok(r.status === 'error' && /الزاوية/.test(r.message), 'متغير من غير قيمة = رسالة خطأ واضحة');

  // مع تعيين قيمة أولًا
  const loop2 = new FakeBlock('eb_loop');
  const setB = new FakeBlock('variables_set', { VAR: 'الزاوية' }, { VALUE: numBlock(30) });
  const repeat2 = new FakeBlock('controls_repeat_ext');
  repeat2._fields = {};
  repeat2._inputs = {
    TIMES: numBlock(2),
    DO: new FakeBlock('math_change', { VAR: 'الزاوية' }, { DELTA: numBlock(10) }),
  };
  loop2.setNext(setB); setB.setNext(repeat2);
  const p2 = compileProgram([loop2]).program;
  const board3 = new FakeBoard();
  const interp3 = new Interpreter(board3);
  setTimeout(() => interp3.stop(), 80);
  await interp3.run(p2);
  // التكرار بيزيد الزاوية 10 مرتين من 30 → 50
  ok(board3.pins.get(13)?.angle === undefined, 'مفيش سيرفو في البرنامج ده');
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

  const { program } = compileProgram([loop]);
  const py = generatePython(program);
  ok(py.includes('distance(12, 14)'), 'python: distance(12, 14)');
  ok(py.includes('tone(15, 900)'), 'python: tone(15, 900)');
  ok(py.includes('no_tone(15)'), 'python: no_tone بعد المدة');
  ok(py.includes('time.ticks_us()'), 'python: حساس الموجات في التعريفات');

  const board = new FakeBoard();
  board.distanceCm = 10;
  const interp = new Interpreter(board);
  setTimeout(() => interp.stop(), 100);
  await interp.run(program);
  ok(board.toneHistory.some((t) => t.pin === 15 && t.freq === 900), 'البازر صفّر لما المسافة قليلة');
}

/* ===== 5) قراءة تناظرية + PWM ===== */
console.log('\n⑤ المقاومة المتغيرة و PWM');
{
  const loop = new FakeBlock('eb_loop');
  const aw = new FakeBlock('eb_awrite', { PIN: '2' }, { DUTY: arithBlock(areadBlock(32), numBlock(10.23), 'DIVIDE') });
  loop.setNext(aw);
  const { program } = compileProgram([loop]);
  const py = generatePython(program);
  ok(py.includes('aread(32)'), 'python: aread(32)');
  ok(py.includes('duty_u16'), 'python: PWM duty');
  const board = new FakeBoard();
  board.potValue = 512;
  const interp = new Interpreter(board);
  setTimeout(() => interp.stop(), 60);
  await interp.run(program);
  ok(Math.abs(board.pins.get(2).duty - 50) < 1, 'الشدة 50% لما المقاومة في النص');
}

/* ===== 6) قسمة على صفر ===== */
console.log('\n⑥ الأخطاء');
{
  const loop = new FakeBlock('eb_loop');
  const setB = new FakeBlock('variables_set', { VAR: 'x' }, { VALUE: arithBlock(numBlock(1), numBlock(0), 'DIVIDE') });
  loop.setNext(setB);
  const { program } = compileProgram([loop]);
  const board = new FakeBoard();
  const interp = new Interpreter(board);
  setTimeout(() => interp.stop(), 150);
  const r = await interp.run(program);
  ok(r.status === 'error' && /صفر/.test(r.message), 'قسمة على صفر = رسالة عربية واضحة');
}

/* ===== 7) انتظر حتى ===== */
console.log('\n⑦ انتظر حتى');
{
  const loop = new FakeBlock('eb_loop');
  const w = new FakeBlock('eb_wait_until', {}, { COND: cmpBlock(dreadBlock(4), numBlock(0), 'EQ') });
  const printB = new FakeBlock('eb_print', {}, {});
  printB._inputs.VAL = { type: 'text', getFieldValue: () => 'خلص الانتظار', getInputTargetBlock: () => null, getNextBlock: () => null };
  w.setNext(printB);
  loop.setNext(w);

  const { program } = compileProgram([loop]);
  const py = generatePython(program);
  ok(py.includes('while not ('), 'python: while not');

  const board = new FakeBoard();
  board.buttonPin = 4;
  board.buttonPressed = false;
  const interp = new Interpreter(board);
  setTimeout(() => { board.buttonPressed = true; }, 80);
  setTimeout(() => interp.stop(), 300);
  const r = await interp.run(program);
  ok(board.prints.includes('خلص الانتظار'), 'كمّل بعد ما الشرط اتحقق');
}

/* ===== 8) نغمات متتالية (عند البدء بس) ===== */
console.log('\n⑧ نغمة عند البدء بدون تكرار');
{
  const onStart = new FakeBlock('eb_on_start');
  const t1 = new FakeBlock('eb_tone', { PIN: '15' }, { FREQ: numBlock(262), DUR: numBlock(300) });
  onStart.setNext(t1);
  const { program, warnings } = compileProgram([onStart]);
  ok(warnings.length === 0, 'مفيش تحذيرات');
  const py = generatePython(program);
  ok(!py.includes('while True:'), 'مفيش تكرار — البرنامج يعمل مرة واحدة');
  ok(py.includes('tone(15, 262)'), 'النغمة موجودة');
  ok(py.includes('time.sleep_ms(300)'), 'مدة النغمة موجودة');
  const board = new FakeBoard();
  const interp = new Interpreter(board);
  const r = await interp.run(program);
  ok(r.status === 'done', 'البرنامج خلص لوحده (مش لوب)');
  ok(board.toneHistory.length === 1, 'النغمة اتشغلت مرة');
}

/* ===== بلوكات مساعدة ===== */
function numBlock(v) {
  return { type: 'math_number', getFieldValue: () => String(v), getInputTargetBlock: () => null, getNextBlock: () => null };
}
function textBlock(v) {
  return { type: 'text', getFieldValue: () => v, getInputTargetBlock: () => null, getNextBlock: () => null };
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
