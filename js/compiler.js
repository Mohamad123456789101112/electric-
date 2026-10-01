/* ============================================================
   إلكترو بلوك — المُترجم: من بلوكات Blockly إلى شجرة برنامج AST
   يعمل في المتصفح وفي اختبارات Node (عن طريق واجهة بلوك مبسطة)
   ============================================================ */

/**
 * تجميع البرنامج من البلوكات.
 * @param {Array} topBlocks قائمة البلوكات العلوية (من workspace.getTopBlocks())
 * @returns {{program: object, warnings: string[]}}
 */
export function compileProgram(topBlocks) {
  const warnings = [];
  const C = new CompilerCtx(warnings);
  const sorted = [...topBlocks].sort((a, b) => {
    const ax = a.getRelativeToSurfaceXY ? a.getRelativeToSurfaceXY().x : 0;
    const bx = b.getRelativeToSurfaceXY ? b.getRelativeToSurfaceXY().x : 0;
    const ay = a.getRelativeToSurfaceXY ? a.getRelativeToSurfaceXY().y : 0;
    const by = b.getRelativeToSurfaceXY ? b.getRelativeToSurfaceXY().y : 0;
    return ay - by || ax - bx;
  });

  let setupTop = null;
  const loopTops = [];
  for (const b of sorted) {
    if (b.type === 'eb_on_start') {
      if (setupTop) warnings.push('⚠️ فيه أكتر من بلوك "عند البدء" — الأول بس هو اللي هيتنفذ');
      else setupTop = b;
    } else if (b.type === 'eb_loop') {
      loopTops.push(b);
    } else {
      warnings.push(`⚠️ فيه بلوكات بره "عند البدء" و"دائمًا" — مش هتتنفذ`);
    }
  }
  if (loopTops.length > 1) warnings.push('⚠️ فيه أكتر من بلوك "دائمًا" — هيتم دمجهم واحد بعد التاني في التكرار');

  const setup = setupTop ? C.stmts(setupTop.getNextBlock ? setupTop.getNextBlock() : null) : [];
  let loop = [];
  for (const lt of loopTops) {
    loop = loop.concat(C.stmts(lt.getNextBlock ? lt.getNextBlock() : null));
  }
  if (!setupTop && loopTops.length === 0) {
    warnings.push('💡 ابدأ ببلوك "🚀 عند البدء" أو "🔁 دائمًا"');
  }
  return { program: { t: 'program', setup, loop }, warnings };
}

class CompilerCtx {
  constructor(warnings) {
    this.w = warnings;
  }

  /* ---------- سلاسل الأوامر ---------- */
  stmts(block, into) {
    const out = into || [];
    while (block) {
      try {
        this.stmt(block, out);
      } catch (e) {
        this.w.push(`⚠️ ${e.message}`);
      }
      block = block.getNextBlock ? block.getNextBlock() : null;
    }
    return out;
  }

  stmt(block, out) {
    const type = block.type;
    const f = (n) => block.getFieldValue(n);
    const val = (name, fallback, kinds) => this.expr(block.getInputTargetBlock(name), fallback, kinds, name);

    switch (type) {
      case 'eb_sleep': {
        const unit = f('UNIT') === 's' ? 's' : 'ms';
        out.push({ t: 'sleep', ms: val('MS', { t: 'num', v: 1000 }), unit });
        break;
      }
      case 'eb_pin_mode': {
        out.push({ t: 'pinmode', pin: this.pin(f('PIN')), mode: f('MODE') });
        break;
      }
      case 'eb_dwrite': {
        out.push({ t: 'dwrite', pin: this.pin(f('PIN')), val: Number(f('VAL')) });
        break;
      }
      case 'eb_awrite': {
        out.push({ t: 'awrite', pin: this.pin(f('PIN')), duty: val('DUTY', { t: 'num', v: 50 }) });
        break;
      }
      case 'eb_swrite': {
        out.push({ t: 'servo', pin: this.pin(f('PIN')), angle: val('ANGLE', { t: 'num', v: 90 }) });
        break;
      }
      case 'eb_tone': {
        out.push({
          t: 'tone',
          pin: this.pin(f('PIN')),
          freq: val('FREQ', { t: 'num', v: 440 }),
          dur: val('DUR', { t: 'num', v: 0 }),
        });
        break;
      }
      case 'eb_notone': {
        out.push({ t: 'notone', pin: this.pin(f('PIN')) });
        break;
      }
      case 'eb_print': {
        out.push({ t: 'print', val: this.exprAny(block.getInputTargetBlock('VAL')) });
        break;
      }
      case 'eb_wait_until': {
        out.push({ t: 'waituntil', cond: this.exprBool(block.getInputTargetBlock('COND')) });
        break;
      }
      // ===== بلوكات Blockly القياسية =====
      case 'controls_if': {
        const clauses = [];
        let i = 0;
        while (block.getInput('IF' + i)) {
          clauses.push({
            cond: this.exprBool(block.getInputTargetBlock('IF' + i)),
            then: this.stmts(block.getInputTargetBlock('DO' + i)),
          });
          i++;
        }
        const orelse = block.getInput('ELSE') ? this.stmts(block.getInputTargetBlock('ELSE')) : null;
        out.push({ t: 'if', clauses, orelse: orelse && orelse.length ? orelse : null });
        break;
      }
      case 'controls_repeat_ext': {
        out.push({ t: 'repeat', count: val('TIMES', { t: 'num', v: 10 }), body: this.stmts(block.getInputTargetBlock('DO')) });
        break;
      }
      case 'controls_whileUntil': {
        const until = f('MODE') === 'UNTIL';
        out.push({
          t: 'while',
          cond: this.exprBool(block.getInputTargetBlock('BOOL')),
          until,
          body: this.stmts(block.getInputTargetBlock('DO')),
        });
        break;
      }
      case 'controls_flow_statements': {
        out.push({ t: 'flow', kind: f('FLOW') === 'CONTINUE' ? 'continue' : 'break' });
        break;
      }
      case 'variables_set': {
        out.push({ t: 'assign', name: f('VAR'), val: this.exprAny(block.getInputTargetBlock('VALUE')) });
        break;
      }
      case 'math_change': {
        out.push({ t: 'change', name: f('VAR'), val: val('DELTA', { t: 'num', v: 1 }) });
        break;
      }
      default:
        throw new Error(`بلوك غير معروف: ${type}`);
    }
  }

  /* ---------- التعابير ---------- */
  exprAny(block) {
    if (!block) return { t: 'num', v: 0 };
    const e = this.expr(block, { t: 'num', v: 0 });
    return e;
  }

  exprBool(block) {
    if (!block) return { t: 'bool', v: false };
    return this.expr(block, { t: 'bool', v: false });
  }

  expr(block, fallback, _kinds, inputName) {
    if (!block) {
      if (inputName) this.w.push(`⚠️ قيمة ناقصة في بلوك — هتستخدم القيمة الافتراضية`);
      return fallback;
    }
    const type = block.type;
    const f = (n) => block.getFieldValue(n);
    const sub = (name) => this.expr(block.getInputTargetBlock(name), { t: 'num', v: 0 }, null, name);

    switch (type) {
      case 'math_number':
      case 'eb_num': {
        const v = Number(f('NUM'));
        return { t: 'num', v: Number.isFinite(v) ? v : 0 };
      }
      case 'eb_dread':
        return { t: 'dread', pin: this.pin(f('PIN')) };
      case 'eb_aread':
        return { t: 'aread', pin: this.pin(f('PIN')) };
      case 'eb_distance':
        return { t: 'distance', trig: this.pin(f('TRIG')), echo: this.pin(f('ECHO')) };
      case 'math_arithmetic': {
        const ops = { ADD: '+', MINUS: '-', MULTIPLY: '*', DIVIDE: '/', POWER: '**' };
        return { t: 'bin', op: ops[f('OP')] || '+', a: sub('A'), b: sub('B') };
      }
      case 'math_modulo':
        return { t: 'bin', op: '%', a: sub('DIVIDEND'), b: sub('DIVISOR') };
      case 'math_single': {
        const op = f('OP');
        if (op === 'ABS') return { t: 'un', op: 'abs', a: sub('NUM') };
        throw new Error('العملية الرياضية دي مش مدعومة لسه');
      }
      case 'math_random_int':
        return { t: 'randint', a: sub('FROM'), b: sub('TO') };
      case 'logic_compare': {
        const ops = { EQ: '==', NEQ: '!=', LT: '<', LTE: '<=', GT: '>', GTE: '>=' };
        return { t: 'bin', op: ops[f('OP')] || '==', a: sub('A'), b: sub('B') };
      }
      case 'logic_operation':
        return { t: 'bin', op: f('OP') === 'OR' ? 'or' : 'and', a: sub('A'), b: sub('B') };
      case 'logic_negate':
        return { t: 'un', op: 'not', a: this.exprBool(block.getInputTargetBlock('BOOL')) };
      case 'logic_boolean':
        return { t: 'bool', v: f('BOOL') === 'TRUE' };
      case 'variables_get':
        return { t: 'var', name: f('VAR') };
      case 'text':
        return { t: 'str', v: String(f('TEXT')) };
      case 'text_join': {
        const items = [];
        let i = 0;
        while (block.getInput('ADD' + i)) {
          const b = block.getInputTargetBlock('ADD' + i);
          items.push(b ? this.expr(b, { t: 'str', v: '' }) : { t: 'str', v: '' });
          i++;
        }
        return { t: 'join', items };
      }
      default:
        throw new Error(`تعبير غير معروف: ${type}`);
    }
  }

  pin(p) {
    const n = Number(p);
    if (!Number.isInteger(n) || n < 0 || n > 39) {
      this.w.push(`⚠️ رقم منفذ غريب: ${p}`);
      return 2;
    }
    return n;
  }
}

/* ---------- أدوات مساعدة للاختبارات (بلوكات وهمية) ---------- */
export class FakeBlock {
  constructor(type, fields = {}, inputs = {}) {
    this.type = type;
    this._fields = fields;
    this._inputs = inputs;
    this._next = null;
  }
  getFieldValue(n) {
    return this._fields[n];
  }
  getInput(n) {
    return this._inputs.hasOwnProperty(n) ? { name: n } : null;
  }
  getInputTargetBlock(n) {
    return this._inputs[n] || null;
  }
  getNextBlock() {
    return this._next;
  }
  setNext(b) {
    this._next = b;
    return b;
  }
  chain(...blocks) {
    let cur = this;
    for (const b of blocks) {
      cur._next = b;
      cur = b;
    }
    return this;
  }
  getRelativeToSurfaceXY() {
    return { x: 0, y: 0 };
  }
}
