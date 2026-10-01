/* ============================================================
   إلكترو بلوك — عميل MicroPython REPL عبر Web Serial
   بروتوكول raw REPL متطابق مع tools/pyboard.py الرسمي
   ============================================================ */

const RAW_BANNER = 'raw REPL; CTRL-B to exit\r\n>';

export class SerialLink {
  constructor({ onStream, onDisconnect } = {}) {
    this.port = null;
    this.reader = null;
    this.writer = null;
    this.reading = false;
    this.decoder = new TextDecoder();
    this.buf = '';
    this.onStream = onStream || (() => {});
    this.onDisconnect = onDisconnect || (() => {});
    this.waiters = [];
  }

  static get supported() {
    return 'serial' in navigator;
  }

  async pickPort() {
    this.port = await navigator.serial.requestPort();
  }

  async open(baud = 115200) {
    if (!this.port) throw new Error('مفيش منفذ متحدد');
    await this.port.open({ baudRate: baud });
    this.writer = this.port.writable.getWriter();
    this.startReading();
    // نبضة إعادة تشغيل (زي esptool) عشان نبدأ من الأول
    try {
      await this.port.setSignals({ dataTerminalReady: false, requestToSend: true });
      await sleep(120);
      await this.port.setSignals({ dataTerminalReady: false, requestToSend: false });
    } catch (e) {
      /* بعض المنافذ مش بتدعم */
    }
  }

  startReading() {
    this.reading = true;
    (async () => {
      while (this.reading && this.port && this.port.readable) {
        this.reader = this.port.readable.getReader();
        try {
          while (this.reading) {
            const { value, done } = await this.reader.read();
            if (done) break;
            const text = this.decoder.decode(value, { stream: true });
            this.buf += text;
            this.onStream(text);
            this.checkWaiters();
          }
        } catch (e) {
          break;
        } finally {
          try {
            this.reader.releaseLock();
          } catch (e) {
            /* تجاهل */
          }
        }
      }
    })();
  }

  async write(str) {
    if (!this.writer) throw new Error('المنفذ مقفول');
    await this.writer.write(new TextEncoder().encode(str));
  }

  async writeBytes(bytes) {
    if (!this.writer) throw new Error('المنفذ مقفول');
    await this.writer.write(bytes);
  }

  checkWaiters() {
    for (const w of [...this.waiters]) {
      const idx = this.buf.indexOf(w.marker);
      if (idx !== -1) {
        const pre = this.buf.slice(0, idx);
        this.buf = this.buf.slice(idx + w.marker.length);
        this.waiters = this.waiters.filter((x) => x !== w);
        clearTimeout(w.timer);
        w.resolve(pre);
      }
    }
  }

  /** استنى ظهور نص معين في البافر */
  waitUntil(marker, timeout = 3000) {
    return new Promise((resolve, reject) => {
      const idx = this.buf.indexOf(marker);
      if (idx !== -1) {
        const pre = this.buf.slice(0, idx);
        this.buf = this.buf.slice(idx + marker.length);
        resolve(pre);
        return;
      }
      const w = { marker, resolve, reject };
      w.timer = setTimeout(() => {
        this.waiters = this.waiters.filter((x) => x !== w);
        reject(new Error(`انتهت المهلة والشريحة مبعتتش: ${JSON.stringify(marker)}`));
      }, timeout);
      this.waiters.push(w);
    });
  }

  /** امسح البافر واستنى مدة معينة */
  async drain(ms) {
    this.buf = '';
    await sleep(ms);
    const out = this.buf;
    this.buf = '';
    return out;
  }

  async close() {
    this.reading = false;
    for (const w of [...this.waiters]) {
      clearTimeout(w.timer);
      w.reject(new Error('اتقفل المنفذ'));
    }
    this.waiters = [];
    try {
      if (this.reader) await this.reader.cancel();
    } catch (e) {
      /* تجاهل */
    }
    try {
      if (this.writer) this.writer.releaseLock();
    } catch (e) {
      /* تجاهل */
    }
    try {
      if (this.port) await this.port.close();
    } catch (e) {
      /* تجاهل */
    }
    this.reader = null;
    this.writer = null;
  }
}

export class MpRepl {
  constructor(link) {
    this.link = link;
  }

  /** هل MicroPython موجود وشغال؟ */
  async probe() {
    try {
      // استنى شوية بعد الفتح — الشريحة ممكن تكون لسه بتعمل reboot
      await this.link.drain(400);
      // 3 محاولات: لو برنامج قديم شغال، Ctrl-C بيوقفة ويظهر البرومبت
      for (let attempt = 0; attempt < 3; attempt++) {
        await this.link.write('\r\x03\x03');
        try {
          const pre = await this.link.waitUntil('>>>', attempt === 0 ? 2500 : 1500);
          return { ok: true, banner: pre };
        } catch (e) {
          /* البورمبت لسه ماهدفش — هجرب تاني */
        }
      }
      await this.link.drain(200);
      return { ok: false };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  }

  /** تنفيذ كود وارجاع الناتج (raw REPL زي pyboard.py) */
  async exec(code, timeout = 10000) {
    // 1) أوقف أي حاجة شغالة وادخل الـ raw REPL
    await this.link.write('\r\x03\x03');
    await sleep(80);
    await this.link.drain(100);
    await this.link.write('\r\x01');
    await this.link.waitUntil('raw REPL', 2000);
    await this.link.waitUntil('>', 800).catch(() => {});
    this.link.buf = '';

    // 2) ابعت الكود على أجزاء 256 بايت كل 10 مللي (زي الأداة الرسمية)
    const bytes = new TextEncoder().encode(code);
    for (let i = 0; i < bytes.length; i += 256) {
      await this.link.writeBytes(bytes.slice(i, Math.min(i + 256, bytes.length)));
      await sleep(10);
    }
    await this.link.write('\x04');

    // 3) لازم يرجع OK
    const ok = await this.waitChars(2, 3000);
    if (ok !== 'OK') {
      let err = '';
      try {
        err = await this.link.waitUntil('\x04', 2000);
      } catch (e) {
        /* تجاهل */
      }
      await this.exitRaw();
      throw new Error(`الشريحة رفضت الكود${err ? ':\n' + err.trim() : ''}`);
    }

    // 4) اقرا الناتج (stdout) وبعدها الأخطاء (stderr)
    let out = '';
    let errOut = '';
    try {
      out = await this.link.waitUntil('\x04', timeout);
    } catch (e) {
      /* ممكن مفيش ناتج */
    }
    try {
      errOut = await this.link.waitUntil('\x04', 1500);
    } catch (e) {
      /* اختياري */
    }
    await this.exitRaw();
    return { out, err: errOut };
  }

  waitChars(n, timeout) {
    return new Promise((resolve, reject) => {
      const started = Date.now();
      const tick = () => {
        if (this.link.buf.length >= n) {
          const s = this.link.buf.slice(0, n);
          this.link.buf = this.link.buf.slice(n);
          resolve(s);
        } else if (Date.now() - started > timeout) {
          resolve(this.link.buf.slice(0, n)); // اللي احنا اخدناه
          this.link.buf = '';
        } else {
          setTimeout(tick, 15);
        }
      };
      tick();
    });
  }

  async exitRaw() {
    try {
      await this.link.write('\x02'); // Ctrl-B: خروج من الـ raw REPL
      this.link.buf = '';
    } catch (e) {
      /* تجاهل */
    }
  }

  /** كتابة البرنامج في main.py عشان يشتغل لوحده بعد الفصل */
  async writeMain(pyCode) {
    const lit = JSON.stringify(pyCode); // literal صالح لباثون كمان
    const code = `with open("main.py", "w") as f:\n    f.write(${lit})\nprint("EB_OK")\n`;
    const r = await this.exec(code, 15000);
    if (!/EB_OK/.test(r.out)) {
      throw new Error('كتابة الملف مكتملتش');
    }
    return true;
  }

  /** إعادة تشغيل الشريحة — البرنامج في main.py هيعمل ري ستارت لوحده */
  async resetAndRun() {
    try {
      await this.exec('import machine\nmachine.reset()\n', 4000).catch(() => {});
    } catch (e) {
      /* الريسيت بيقطع الاتصال لحظيًا — عادي */
    }
    this.link.buf = '';
  }

  /** إيقاف البرنامج الشغال */
  async interrupt() {
    await this.link.write('\r\x03\x03');
  }

  /** مسح main.py من الشريحة */
  async clearMain() {
    await this.exec('import os\ntry:\n    os.remove("main.py")\nexcept:\n    pass\nprint("EB_CLEARED")', 8000);
  }
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}
