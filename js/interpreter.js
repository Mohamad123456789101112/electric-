/* ============================================================
   إلكترو بلوك — مفسّر شجرة البرنامج (AST) للمحاكي
   بينفّذ نفس منطق الكود المولد لكن في المتصفح
   ============================================================ */

export class StopSignal extends Error {
  constructor() {
    super('STOP');
    this.isStop = true;
  }
}

let runCounter = 0;

/**
 * مفسّر البرنامج — بينفذ AST ضد واجهة لوحة (board)
 * board لازم يوفّر الدوال دي (كلها ممكن تكون async):
 *   dwrite(pin,v) awrite(pin,duty) servo(pin,angle) tone(pin,freq)
 *   notone(pin) dread(pin) aread(pin) distance(trig,echo)
 *   pinmode(pin,mode) print(text) sleepMs(ms) sleepS(s)
 */
export class Interpreter {
  constructor(board) {
    this.board = board;
    this.stopped = false;
    this.stopWaiter = null;
    this.opsCount = 0;
    this.id = ++runCounter;
    this.onLoopYield = null;
  }

  stop() {
    this.stopped = true;
    if (this.stopWaiter) {
      this.stopWaiter.reject(new StopSignal());
      this.stopWaiter = null;
    }
  }

  checkpoint() {
    if (this.stopped) throw new StopSignal();
  }

  async tick() {
    // كل شوية بيسيب المتصفح يتنفس عشان الواجهة متتهنّجش
    this.opsCount++;
    if (this.stopped) throw new StopSignal();
    if ((this.opsCount & 0x7f) === 0) {
      await new Promise((r) => setTimeout(r, 0));
      if (this.stopped) throw new StopSignal();
    }
  }

  async sleep(ms) {
    this.checkpoint();
    await Promise.race([this.board.sleepMs(ms), this.stopPromise()]);
    this.checkpoint();
  }

  stopPromise() {
    return new Promise((_, reject) => {
      if (this.stopped) reject(new StopSignal());
      else this.stopWaiter = { reject };
    });
  }

  async run(program) {
    try {
      await this.runList(program.setup);
      if (program.loop.length === 0) return { status: 'done' };
      while (true) {
        await this.tick();
        await this.runList(program.loop);
      }
    } catch (e) {
      if (e instanceof StopSignal || e.isStop) return { status: 'stopped' };
      return { status: 'error', message: e && e.message ? e.message : String(e) };
    }
  }

  async runList(list) {
    for (const s of list) {
      await this.tick();
      await this.stmt(s);
    }
  }

  async stmt(s) {
    const B = this.board;
    switch (s.t) {
      case 'sleep': {
        const ms = await this.eval(s.ms);
        if (s.unit === 's') await this.sleep(clampMs(ms * 1000));
        else await this.sleep(clampMs(ms));
        return;
      }
      case 'pinmode':
        await B.pinmode(s.pin, s.mode);
        return;
      case 'dwrite':
        await B.dwrite(s.pin, s.val ? 1 : 0);
        return;
      case 'awrite':
        await B.awrite(s.pin, clamp(await this.eval(s.duty), 0, 100));
        return;
      case 'servo':
        await B.servo(s.pin, clamp(await this.eval(s.angle), 0, 180));
        return;
      case 'tone': {
        const freq = clamp(await this.eval(s.freq), 1, 100000);
        const dur = s.dur ? await this.eval(s.dur) : 0;
        await B.tone(s.pin, freq);
        if (dur && dur > 0) {
          await this.sleep(clampMs(dur));
          await B.notone(s.pin);
        }
        return;
      }
      case 'notone':
        await B.notone(s.pin);
        return;
      case 'print': {
        const v = s.val ? await this.eval(s.val) : '';
        await B.print(typeof v === 'string' ? v : formatNum(v));
        return;
      }
      case 'waituntil': {
        while (!(await this.eval(s.cond))) {
          await this.tick();
          await this.sleep(10);
        }
        return;
      }
      case 'if': {
        for (const cl of s.clauses) {
          if (await this.eval(cl.cond)) {
            await this.runList(cl.then);
            return;
          }
        }
        if (s.orelse) await this.runList(s.orelse);
        return;
      }
      case 'repeat': {
        const n = Math.floor(await this.eval(s.count));
        for (let i = 0; i < n; i++) {
          await this.tick();
          try {
            await this.runList(s.body);
          } catch (e) {
            if (e instanceof StopSignal) throw e;
            if (e && e.isFlow === 'break') break;
            if (e && e.isFlow === 'continue') continue;
            throw e;
          }
        }
        return;
      }
      case 'while': {
        while (true) {
          await this.tick();
          let c = await this.eval(s.cond);
          if (s.until) c = !c;
          if (!c) break;
          try {
            await this.runList(s.body);
          } catch (e) {
            if (e instanceof StopSignal) throw e;
            if (e && e.isFlow === 'break') break;
            if (e && e.isFlow === 'continue') continue;
            throw e;
          }
        }
        return;
      }
      case 'flow':
        throw { isFlow: s.kind, message: s.kind };
      case 'assign':
        this.vars[s.name] = await this.eval(s.val);
        return;
      case 'change':
        this.vars[s.name] = (this.vars[s.name] || 0) + (await this.eval(s.val));
        return;
      default:
        throw new Error(`بلوك غير مدعوم في المحاكي: ${s.t}`);
    }
  }

  async eval(e) {
    if (!e) return 0;
    switch (e.t) {
      case 'num':
        return e.v;
      case 'str':
        return e.v;
      case 'bool':
        return e.v;
      case 'var': {
        const v = this.vars[e.name];
        if (v === undefined) throw new Error(`المتغير "${e.name}" لسه معملش له قيمة`);
        return v;
      }
      case 'bin': {
        const a = await this.eval(e.a);
        const b = await this.eval(e.b);
        switch (e.op) {
          case '+': return a + b;
          case '-': return a - b;
          case '*': return a * b;
          case '/':
            if (b === 0) throw new Error('قسمة على صفر! 🚫');
            return a / b;
          case '%':
            if (b === 0) throw new Error('باقي القسمة على صفر! 🚫');
            return ((a % b) + b) % b;
          case '**': return Math.pow(a, b);
          case '==': return a === b;
          case '!=': return a !== b;
          case '<': return a < b;
          case '<=': return a <= b;
          case '>': return a > b;
          case '>=': return a >= b;
          case 'and': return !!(a && b);
          case 'or': return !!(a || b);
          default: throw new Error(`عملية غير معروفة: ${e.op}`);
        }
      }
      case 'un': {
        const a = await this.eval(e.a);
        if (e.op === 'not') return !a;
        if (e.op === 'neg') return -a;
        return Math.abs(a);
      }
      case 'join': {
        const parts = [];
        for (const it of e.items) {
          const v = await this.eval(it);
          parts.push(typeof v === 'string' ? v : formatNum(v));
        }
        return parts.join('');
      }
      case 'dread':
        return (await this.board.dread(e.pin)) ? 1 : 0;
      case 'aread':
        return await this.board.aread(e.pin);
      case 'distance':
        return await this.board.distance(e.trig, e.echo);
      case 'randint': {
        const a = Math.floor(await this.eval(e.a));
        const b = Math.floor(await this.eval(e.b));
        const lo = Math.min(a, b);
        const hi = Math.max(a, b);
        return lo + Math.floor(Math.random() * (hi - lo + 1));
      }
      default:
        throw new Error(`تعبير غير مدعوم في المحاكي: ${e.t}`);
    }
  }
}

function clampMs(ms) {
  const n = Number(ms);
  if (!Number.isFinite(n)) return 100;
  return Math.max(0, Math.min(60000, n));
}

function clamp(v, lo, hi) {
  const n = Number(v);
  if (!Number.isFinite(n)) return lo;
  return Math.max(lo, Math.min(hi, n));
}

function formatNum(v) {
  if (typeof v === 'boolean') return v ? 'True' : 'False';
  if (Number.isInteger(v)) return String(v);
  return String(Math.round(v * 1000) / 1000);
}
