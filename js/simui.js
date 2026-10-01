/* ============================================================
   إلكترو بلوك — واجهة مكونات المحاكي (عرض وتحكم)
   ============================================================ */
import { SimBoard, COMPONENT_TYPES } from './simulator.js';

const ALL_PINS = [2, 4, 5, 12, 13, 14, 15, 16, 17, 18, 19, 21, 22, 23, 25, 26, 27, 32, 33, 34, 35, 36, 39];
const ADC_PINS = [32, 33, 34, 35, 36, 39];

function pinSelect(current, pins, onChange) {
  const sel = document.createElement('select');
  sel.className = 'pin-select';
  for (const p of pins) {
    const o = document.createElement('option');
    o.value = String(p);
    o.textContent = 'GPIO ' + p;
    if (p === current) o.selected = true;
    sel.appendChild(o);
  }
  sel.addEventListener('change', () => onChange(Number(sel.value)));
  return sel;
}

export class SimUI {
  constructor(containerEl, board) {
    this.el = containerEl;
    this.board = board;
    this.renderFns = new Map();
    this.raf = null;
  }

  /** بناء واجهة إضافة المكوّنات */
  buildAddBar(barEl) {
    barEl.innerHTML = '';
    for (const [key, def] of Object.entries(COMPONENT_TYPES)) {
      const btn = document.createElement('button');
      btn.className = 'chip-btn';
      btn.style.setProperty('--c', def.color);
      btn.textContent = def.label;
      btn.addEventListener('click', () => {
        this.board.addComponent(key);
        this.renderAll();
      });
      barEl.appendChild(btn);
    }
    const clearBtn = document.createElement('button');
    clearBtn.className = 'chip-btn chip-danger';
    clearBtn.textContent = '🗑️ مسح الكل';
    clearBtn.addEventListener('click', () => {
      this.board.clear();
      this.renderAll();
    });
    barEl.appendChild(clearBtn);
  }

  renderAll() {
    this.el.innerHTML = '';
    this.renderFns.clear();
    if (!this.board.components.length) {
      const empty = document.createElement('div');
      empty.className = 'sim-empty';
      empty.innerHTML = `
        <div class="sim-empty-icon">🧩</div>
        <div><b>المحاكي فاضي!</b></div>
        <div class="muted">ضيف مكوّنات (ليد، زر، سيرفو…) من الأزرار فوق، وبعدين دوس ▶️ تشغيل</div>`;
      this.el.appendChild(empty);
      return;
    }
    for (const c of this.board.components) {
      this.el.appendChild(this.renderComponent(c));
    }
    this.scheduleRefresh();
  }

  renderComponent(c) {
    const def = COMPONENT_TYPES[c.type];
    const card = document.createElement('div');
    card.className = 'comp-card';
    card.style.setProperty('--c', def.color);
    this.renderFns.set(c.id, () => this.paint(c, card));

    // ===== الهيدر =====
    const head = document.createElement('div');
    head.className = 'comp-head';
    const title = document.createElement('span');
    title.className = 'comp-title';
    title.textContent = def.label;
    head.appendChild(title);

    if (c.type === 'hcsr04') {
      const tr = pinSelect(c.trig, ALL_PINS, (v) => {
        c.trig = v;
      });
      const ec = pinSelect(c.echo, ALL_PINS, (v) => {
        c.echo = v;
      });
      const l1 = document.createElement('span');
      l1.className = 'muted small'; l1.textContent = 'إرسال';
      const l2 = document.createElement('span');
      l2.className = 'muted small'; l2.textContent = 'استقبال';
      head.append(l1, tr, l2, ec);
    } else {
      const pins = c.type === 'pot' ? ADC_PINS : ALL_PINS;
      const s = pinSelect(c.pin, pins, (v) => {
        const old = c.pin;
        if (c.type === 'buzzer' && old !== v) this.board.stopTone(old);
        c.pin = v;
      });
      head.appendChild(s);
    }

    const del = document.createElement('button');
    del.className = 'comp-del';
    del.textContent = '✕';
    del.title = 'حذف المكوّن';
    del.addEventListener('click', () => {
      this.board.removeComponent(c.id);
      this.renderAll();
    });
    head.appendChild(del);
    card.appendChild(head);

    // ===== الجسم =====
    const body = document.createElement('div');
    body.className = 'comp-body';

    if (c.type === 'led') {
      body.innerHTML = `<div class="led-wrap"><div class="led" style="--led:${c.color}"></div><div class="led-label"></div></div>`;
    } else if (c.type === 'button') {
      const b = document.createElement('button');
      b.className = 'sim-btn';
      b.textContent = 'اضغط';
      const down = (e) => {
        e.preventDefault();
        c.pressed = true;
        this.paint(c, card);
      };
      const up = () => {
        c.pressed = false;
        this.paint(c, card);
      };
      b.addEventListener('pointerdown', down);
      b.addEventListener('pointerup', up);
      b.addEventListener('pointerleave', up);
      b.addEventListener('pointercancel', up);
      const note = document.createElement('div');
      note.className = 'muted small center';
      note.textContent = '(زر = 0 عند الضغط مع مقاومة السحب)';
      body.append(b, note);
    } else if (c.type === 'pot') {
      const wrap = document.createElement('div');
      wrap.className = 'pot-wrap';
      const range = document.createElement('input');
      range.type = 'range';
      range.min = 0;
      range.max = 1023;
      range.value = c.potValue;
      range.className = 'pot-range';
      range.style.direction = 'ltr';
      const lab = document.createElement('span');
      lab.className = 'pot-val';
      lab.textContent = c.potValue;
      range.addEventListener('input', () => {
        c.potValue = Number(range.value);
        lab.textContent = range.value;
      });
      wrap.append(range, lab);
      body.appendChild(wrap);
    } else if (c.type === 'servo') {
      body.innerHTML = `
        <div class="servo-wrap">
          <div class="servo-dial">
            <div class="servo-needle"></div>
            <div class="servo-center"></div>
          </div>
          <div class="servo-deg">90°</div>
        </div>`;
    } else if (c.type === 'buzzer') {
      body.innerHTML = `
        <div class="buzzer-wrap">
          <div class="buzzer-body">🔊</div>
          <div class="buzzer-waves"><span></span><span></span><span></span></div>
          <div class="buzzer-freq muted small"></div>
        </div>`;
    } else if (c.type === 'hcsr04') {
      const wrap = document.createElement('div');
      wrap.className = 'sonic-wrap';
      const range = document.createElement('input');
      range.type = 'range';
      range.min = 2;
      range.max = 200;
      range.value = c.distance;
      range.className = 'pot-range';
      range.style.direction = 'ltr';
      const lab = document.createElement('span');
      lab.className = 'pot-val';
      lab.textContent = c.distance + ' سم';
      range.addEventListener('input', () => {
        c.distance = Number(range.value);
        lab.textContent = range.value + ' سم';
      });
      const eyes = document.createElement('div');
      eyes.className = 'sonic-eyes';
      eyes.innerHTML = '<span></span><span></span>';
      wrap.append(eyes, range, lab);
      body.appendChild(wrap);
    }
    card.appendChild(body);
    this.paint(c, card);
    return card;
  }

  paint(c, card) {
    if (!card.isConnected) return;
    if (c.type === 'led') {
      const led = card.querySelector('.led');
      const lab = card.querySelector('.led-label');
      if (led) {
        led.style.setProperty('--glow', String(c.level));
        led.classList.toggle('on', c.level > 0.05);
      }
      if (lab) lab.textContent = c.level > 0 ? `${Math.round(c.level * 100)}%` : 'مطفي';
    } else if (c.type === 'servo') {
      const needle = card.querySelector('.servo-needle');
      const deg = card.querySelector('.servo-deg');
      if (needle) needle.style.transform = `rotate(${c.angle - 90}deg)`;
      if (deg) deg.textContent = Math.round(c.angle) + '°';
    } else if (c.type === 'buzzer') {
      const waves = card.querySelector('.buzzer-waves');
      const freq = card.querySelector('.buzzer-freq');
      if (waves) waves.classList.toggle('active', !!c.soundOn);
      if (freq) freq.textContent = c.soundOn ? `${Math.round(this.board.pins.get(c.pin)?.tone || 0)} هرتز` : 'صامت';
    } else if (c.type === 'button') {
      const b = card.querySelector('.sim-btn');
      if (b) b.classList.toggle('pressed', !!c.pressed);
    }
  }

  /** تحديث مستمر خفيف أثناء التشغيل */
  scheduleRefresh() {
    if (this.raf) cancelAnimationFrame(this.raf);
    const loop = () => {
      for (const c of this.board.components) {
        const fn = this.renderFns.get(c.id);
        if (fn) fn();
      }
      this.raf = requestAnimationFrame(loop);
    };
    this.raf = requestAnimationFrame(loop);
  }

  destroy() {
    if (this.raf) cancelAnimationFrame(this.raf);
    this.renderFns.clear();
  }
}

export { SimBoard, COMPONENT_TYPES };
