/* ============================================================
   إلكترو بلوك — المحاكي: لوحة ESP32 افتراضية بمكونات
   ============================================================ */

let audioCtx = null;
function getAudio() {
  if (!audioCtx) {
    try {
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    } catch (e) {
      audioCtx = null;
    }
  }
  return audioCtx;
}

const COMPONENT_TYPES = {
  led: {
    label: '💡 ليد',
    color: '#f59e0b',
    defaultPin: 2,
    pinLabel: 'المنفذ',
  },
  button: {
    label: '🔘 زر',
    color: '#3b82f6',
    defaultPin: 4,
    pinLabel: 'المنفذ',
  },
  pot: {
    label: '🎚️ مقاومة متغيرة',
    color: '#8b5cf6',
    defaultPin: 32,
    pinLabel: 'المنفذ التناظري',
  },
  servo: {
    label: '🕹️ سيرفو',
    color: '#10b981',
    defaultPin: 13,
    pinLabel: 'المنفذ',
  },
  buzzer: {
    label: '🔊 بازر',
    color: '#ef4444',
    defaultPin: 15,
    pinLabel: 'المنفذ',
  },
  hcsr04: {
    label: '📏 حساس مسافة',
    color: '#06b6d4',
    defaultTrig: 12,
    defaultEcho: 14,
  },
};

export class SimBoard {
  constructor() {
    this.components = [];
    this.nextId = 1;
    this.pins = new Map(); // pin -> { digital, duty, angle, tone }
    this.monitorEl = null;
    this.hinted = new Set();
    this.oscillators = new Map(); // pin -> oscillator
  }

  attachMonitor(el) {
    this.monitorEl = el;
  }

  /* ===== إدارة المكونات ===== */
  addComponent(type, opts = {}) {
    const def = COMPONENT_TYPES[type];
    if (!def) return null;
    const c = {
      id: this.nextId++,
      type,
      pin: opts.pin != null ? opts.pin : this.pickPin(type, 'pin'),
      trig: opts.trig != null ? opts.trig : def.defaultTrig,
      echo: opts.echo != null ? opts.echo : def.defaultEcho,
      color: opts.color || '#fbbf24',
      pressed: false,
      potValue: 512,
      distance: 30,
      level: 0, // شدة الليد 0..1
      angle: 90,
      soundOn: false,
    };
    this.components.push(c);
    return c;
  }

  pickPin(type, field) {
    const def = COMPONENT_TYPES[type];
    const used = new Set(this.components.filter((c) => c.type === type).map((c) => c[field]));
    let candidate = def[field === 'echo' ? 'defaultEcho' : field === 'trig' ? 'defaultTrig' : 'defaultPin'];
    while (used.has(candidate)) candidate = candidate + 1;
    return candidate;
  }

  removeComponent(id) {
    const c = this.components.find((x) => x.id === id);
    if (c && c.type === 'buzzer') this.stopTone(c.pin);
    this.components = this.components.filter((x) => x.id !== id);
  }

  clear() {
    for (const c of [...this.components]) {
      if (c.type === 'buzzer') this.stopTone(c.pin);
    }
    this.components = [];
    this.pins.clear();
  }

  resetRuntime() {
    for (const c of this.components) {
      if (c.type === 'buzzer') this.stopTone(c.pin);
      if (c.type === 'led') c.level = 0;
      if (c.type === 'servo') c.angle = 90;
      c.pressed = false;
    }
    this.pins.clear();
  }

  /* ===== واجهة اللوحة (بيستخدمها المفسّر) ===== */
  pinState(pin) {
    let st = this.pins.get(pin);
    if (!st) {
      st = { digital: 0, duty: null, angle: null, tone: null };
      this.pins.set(pin, st);
    }
    return st;
  }

  async dwrite(pin, v) {
    this.pinState(pin).digital = v;
    this.pinState(pin).duty = null;
    for (const c of this.components) {
      if (c.type === 'led' && c.pin === pin) c.level = v ? 1 : 0;
    }
  }

  async awrite(pin, duty) {
    this.pinState(pin).duty = duty;
    for (const c of this.components) {
      if (c.type === 'led' && c.pin === pin) c.level = duty / 100;
    }
  }

  async servo(pin, angle) {
    this.pinState(pin).angle = angle;
    for (const c of this.components) {
      if (c.type === 'servo' && c.pin === pin) c.angle = angle;
    }
  }

  async tone(pin, freq) {
    this.pinState(pin).tone = freq;
    for (const c of this.components) {
      if (c.type === 'buzzer' && c.pin === pin) this.playTone(c, freq);
    }
  }

  async notone(pin) {
    this.pinState(pin).tone = null;
    this.stopTone(pin);
  }

  async pinmode(pin, mode) {
    this.pinState(pin).mode = mode;
  }

  async dread(pin) {
    const st = this.pinState(pin);
    const btn = this.components.find((c) => c.type === 'button' && c.pin === pin);
    if (!btn) {
      this.hint('nobtn', `مفيش زر على المنفذ ${pin} في المحاكي — ضيف واحد من زر "+ إضافة مكوّن"`);
      return st.mode === 'pullup' ? 1 : 0;
    }
    if (st.mode === 'pullup') return btn.pressed ? 0 : 1;
    return btn.pressed ? 1 : 0;
  }

  async aread(pin) {
    const pot = this.components.find((c) => c.type === 'pot' && c.pin === pin);
    if (!pot) {
      this.hint('nopot', `مفيش مقاومة متغيرة على المنفذ ${pin} — ضيف واحدة للمحاكي`);
      return 0;
    }
    return Math.round(pot.potValue);
  }

  async distance(trig, echo) {
    const s = this.components.find(
      (c) => c.type === 'hcsr04' && (c.trig === trig || c.trig === echo || c.echo === trig || c.echo === echo)
    );
    if (!s) {
      this.hint('nosonic', 'مفيش حساس مسافة في المحاكي — ضيف واحد من "+ إضافة مكوّن"');
      return 0;
    }
    return Math.round(s.distance);
  }

  async print(text) {
    if (this.monitorEl) {
      const div = document.createElement('div');
      div.className = 'mon-line';
      div.textContent = text;
      this.monitorEl.appendChild(div);
      this.monitorEl.scrollTop = this.monitorEl.scrollHeight;
    }
  }

  async sleepMs(ms) {
    await new Promise((r) => setTimeout(r, ms));
  }

  /* ===== صوت البازر ===== */
  playTone(comp, freq) {
    const ctx = getAudio();
    if (!ctx) return;
    this.stopTone(comp.pin);
    try {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'square';
      osc.frequency.value = Math.max(20, Math.min(8000, freq));
      gain.gain.value = 0.08;
      osc.connect(gain).connect(ctx.destination);
      osc.start();
      this.oscillators.set(comp.pin, { osc, gain });
      comp.soundOn = true;
    } catch (e) {
      /* تجاهل */
    }
  }

  stopTone(pin) {
    const o = this.oscillators.get(pin);
    if (o) {
      try {
        o.osc.stop();
      } catch (e) {
        /* تجاهل */
      }
      this.oscillators.delete(pin);
    }
    for (const c of this.components) {
      if (c.type === 'buzzer' && c.pin === pin) c.soundOn = false;
    }
  }

  hint(key, msg) {
    if (this.hinted.has(key)) return;
    this.hinted.add(key);
    if (this.monitorEl) {
      const div = document.createElement('div');
      div.className = 'mon-line mon-hint';
      div.textContent = '💡 ' + msg;
      this.monitorEl.appendChild(div);
    }
  }

  /* ===== حفظ واسترجاع ===== */
  serialize() {
    return this.components.map((c) => ({
      type: c.type,
      pin: c.pin,
      trig: c.trig,
      echo: c.echo,
      color: c.color,
    }));
  }

  load(data) {
    this.clear();
    for (const d of data || []) {
      this.addComponent(d.type, d);
    }
  }
}

export { COMPONENT_TYPES };
