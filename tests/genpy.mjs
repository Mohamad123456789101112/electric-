/* توليد ملفات بايثون من برامج الاختبار للتحقق منها بـ python3 حقيقي */
import { compileProgram } from '../js/compiler.js';
import { FakeBlock } from './fakeblock.mjs';
import { generatePython } from '../js/pygen.js';
import { mkdirSync, writeFileSync } from 'fs';

mkdirSync('/tmp/py', { recursive: true });

const numBlock = (v) => ({ type: 'math_number', getFieldValue: () => String(v), getInputTargetBlock: () => null, getNextBlock: () => null });
const varBlock = (name) => ({ type: 'variables_get', getFieldValue: () => name, getInputTargetBlock: () => null, getNextBlock: () => null });
const dreadBlock = (pin) => ({ type: 'eb_dread', getFieldValue: () => String(pin), getInputTargetBlock: () => null, getNextBlock: () => null });
const areadBlock = (pin) => ({ type: 'eb_aread', getFieldValue: () => String(pin), getInputTargetBlock: () => null, getNextBlock: () => null });
const distBlock = (t, e) => ({ type: 'eb_distance', getFieldValue: (n) => (n === 'TRIG' ? String(t) : String(e)), getInputTargetBlock: () => null, getNextBlock: () => null });
const cmpBlock = (a, b, op = 'EQ') => ({ type: 'logic_compare', getFieldValue: () => op, getInputTargetBlock: (n) => (n === 'A' ? a : b), getNextBlock: () => null });
const arithBlock = (a, b, op = 'ADD') => ({ type: 'math_arithmetic', getFieldValue: () => op, getInputTargetBlock: (n) => (n === 'A' ? a : b), getNextBlock: () => null });
function ifBlock(cond, then, orelse) {
  const b = new FakeBlock('controls_if');
  b._fields = {};
  b._inputs = { IF0: cond, DO0: then };
  if (orelse) {
    b._inputs.ELSE = orelse;
    b.getInput = (n) => (n === 'IF0' || n === 'DO0' || n === 'ELSE' ? { name: n } : null);
  } else {
    b.getInput = (n) => (n === 'IF0' || n === 'DO0' ? { name: n } : null);
  }
  return b;
}
function gen(blocks, filename) {
  const { program } = compileProgram(blocks);
  const py = generatePython(program);
  writeFileSync('/tmp/py/' + filename, py);
  return py;
}

/* --- برنامج 1: وميض + طباعة --- */
{
  const onStart = new FakeBlock('eb_on_start');
  const pr = new FakeBlock('eb_print');
  pr._inputs.VAL = { type: 'text', getFieldValue: () => 'أهلًا 👋', getInputTargetBlock: () => null, getNextBlock: () => null };
  onStart.setNext(pr);

  const loop = new FakeBlock('eb_loop');
  const d1 = new FakeBlock('eb_dwrite', { PIN: '2', VAL: '1' });
  const s1 = new FakeBlock('eb_sleep', { UNIT: 'ms' });
  s1._inputs.MS = numBlock(100);
  const d2 = new FakeBlock('eb_dwrite', { PIN: '2', VAL: '0' });
  const s2 = new FakeBlock('eb_sleep', { UNIT: 'ms' });
  s2._inputs.MS = numBlock(100);
  d1.setNext(s1); s1.setNext(d2); d2.setNext(s2);
  loop.setNext(d1);

  gen([onStart, loop], 'blink.py');
}

/* --- برنامج 2: كل الميزات مع بعض --- */
{
  const onStart = new FakeBlock('eb_on_start');
  const pm = new FakeBlock('eb_pin_mode', { PIN: '4', MODE: 'pullup' });
  const setv = new FakeBlock('variables_set', { VAR: 'عدد' }, { VALUE: numBlock(0) });
  onStart.setNext(pm); pm.setNext(setv);

  const loop = new FakeBlock('eb_loop');
  const ch = new FakeBlock('math_change', { VAR: 'عدد' }, { DELTA: arithBlock(areadBlock(32), numBlock(4), 'MULTIPLY') });
  const rep = new FakeBlock('controls_repeat_ext');
  rep._fields = {};
  rep._inputs = {
    TIMES: numBlock(3),
    DO: new FakeBlock('eb_swrite', { PIN: '13' }, { ANGLE: arithBlock(varBlock('عدد'), numBlock(2), 'ADD') }),
  };
  const iff = ifBlock(
    cmpBlock(dreadBlock(4), numBlock(0)),
    new FakeBlock('eb_tone', { PIN: '15' }, { FREQ: numBlock(880), DUR: numBlock(100) }),
    new FakeBlock('eb_notone', { PIN: '15' })
  );
  const aw = new FakeBlock('eb_awrite', { PIN: '2' }, { DUTY: numBlock(50) });
  const wu = new FakeBlock('eb_wait_until', {}, { COND: cmpBlock(distBlock(12, 14), numBlock(1000), 'LT') });
  const pr2 = new FakeBlock('eb_print');
  pr2._inputs.VAL = distBlock(12, 14);
  loop.setNext(ch); ch.setNext(rep); rep.setNext(iff); iff.setNext(aw); aw.setNext(wu); wu.setNext(pr2);

  gen([onStart, loop], 'full.py');
}

/* --- برنامج 3: باقي القسمة --- */
{
  const loop = new FakeBlock('eb_loop');
  const setv = new FakeBlock('variables_set', { VAR: 'i' }, { VALUE: numBlock(0) });
  const ch = new FakeBlock('math_change', { VAR: 'i' }, { DELTA: numBlock(1) });
  const mod = new FakeBlock('math_modulo', {}, { DIVIDEND: varBlock('i'), DIVISOR: numBlock(2) });
  const iff = ifBlock(
    cmpBlock(mod, numBlock(0)),
    new FakeBlock('eb_dwrite', { PIN: '2', VAL: '1' }),
    new FakeBlock('eb_dwrite', { PIN: '2', VAL: '0' })
  );
  const s = new FakeBlock('eb_sleep', { UNIT: 's' });
  s._inputs.MS = numBlock(0.5);
  loop.setNext(setv); setv.setNext(ch); ch.setNext(iff); iff.setNext(s);
  gen([loop], 'mod.py');
}

console.log('generated ✓');
