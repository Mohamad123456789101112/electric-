/* ============================================================
   إلكترو بلوك — التطبيق الرئيسي (واجهة المستخدم)
   ============================================================ */
import { registerBlocks, buildToolboxXml } from './blocks.js';
import { compileProgram } from './compiler.js';
import { generatePython } from './pygen.js';
import { Interpreter } from './interpreter.js';
import { SimBoard, COMPONENT_TYPES } from './simulator.js';
import { SimUI } from './simui.js';
import { SerialLink, MpRepl } from './repl.js';
import { FIRMWARE, flashFirmware, pickFirmwareKey } from './flasher.js';
import { EXAMPLES } from './examples.js';

const $ = (id) => document.getElementById(id);
const el = (sel, root) => (root || document).querySelector(sel);

/* ================= حالة عامة ================= */
let workspace = null;
let simBoard = null;
let simUI = null;
let simInterpreter = null;
let link = null;
let repl = null;
let connected = false;
let compileTimer = null;

/* ================= تابز ================= */
const TABS = ['blocks', 'code', 'sim', 'monitor'];
function showTab(name) {
  for (const t of TABS) {
    const panel = $('tab-' + t);
    if (panel) panel.classList.toggle('active', t === name);
    const nav = $('nav-' + t);
    if (nav) nav.classList.toggle('active', t === name);
  }
  if (name === 'blocks' && workspace) {
    setTimeout(() => Blockly.svgResize(workspace), 50);
  }
}

/* ================= توست ================= */
function toast(msg, kind = 'info', ms = 3500) {
  const box = $('toasts');
  const t = document.createElement('div');
  t.className = 'toast toast-' + kind;
  t.textContent = msg;
  box.appendChild(t);
  setTimeout(() => t.classList.add('show'), 10);
  setTimeout(() => {
    t.classList.remove('show');
    setTimeout(() => t.remove(), 400);
  }, ms);
}

/* ================= بلوكلي ================= */
function initBlockly() {
  registerBlocks(Blockly);
  const theme = Blockly.Theme.defineTheme('ebtheme', {
    base: Blockly.Themes.Classic,
    componentStyles: {
      workspaceBackgroundColour: '#12161f',
      toolboxBackgroundColour: '#0c0f16',
      toolboxColour: '#171c28',
      flyoutBackgroundColour: '#171c28',
      flyoutOpacity: 1,
      flyoutForegroundColour: '#8892a6',
      scrollbarColour: '#2b3345',
      scrollbarOpacity: 0.6,
      insertionMarkerColour: '#ffd166',
      insertionMarkerOpacity: 0.4,
      cursorColour: '#ffd166',
    },
    fontStyle: { family: 'Tajawal, Cairo, sans-serif', weight: '700', size: 12 },
  });

  workspace = Blockly.inject('blocklyDiv', {
    toolbox: buildToolboxXml(),
    rtl: true,
    renderer: 'zelos',
    theme,
    grid: { spacing: 24, length: 2, snap: true, colour: '#1c2230' },
    move: { scrollbars: { horizontal: true, vertical: true }, drag: true, wheel: true },
    zoom: { controls: true, wheel: true, startScale: 0.85, maxScale: 1.6, minScale: 0.4, scaleSpeed: 1.15, pinch: true },
    trashcan: true,
    sounds: false,
  });

  workspace.addChangeListener((ev) => {
    if (ev.type === Blockly.Events.UI) return;
    scheduleCompile();
    scheduleSave();
  });
  window.addEventListener('resize', () => Blockly.svgResize(workspace));
}

/* ================= الترجمة الحية ================= */
function scheduleCompile() {
  clearTimeout(compileTimer);
  compileTimer = setTimeout(compileNow, 200);
}

let lastProgram = null;

function compileNow() {
  const { program, warnings } = compileProgram(workspace.getTopBlocks(false));
  const py = generatePython(program);
  lastProgram = program;
  $('codeArea').textContent = py;
  highlightCode();
  // التحذيرات
  const warnBox = $('warnings');
  warnBox.innerHTML = '';
  if (warnings.length) {
    warnBox.style.display = '';
    for (const w of warnings) {
      const d = document.createElement('div');
      d.className = 'warn-chip';
      d.textContent = w;
      warnBox.appendChild(d);
    }
  } else {
    warnBox.style.display = 'none';
  }
  return { program, py, warnings };
}

/* ================= تمييز كود بايثون بسيط ================= */
const PY_TOKENS = /("(?:[^"\\]|\\.)*")|(#[^\n]*)|\b(from|import|def|while|for|in|if|elif|else|True|False|not|and|or|break|continue|return|with|as|print|range|int|str|abs|max|min|time|machine|Pin|PWM|ADC|random)\b|\b(\d+(?:\.\d+)?)\b/g;
function highlightCode() {
  const pre = $('codeArea');
  const code = pre.textContent;
  const esc = code.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  // مرر واحد فقط — عشان ما نتكسرش على الوسوم اللي بنولدها
  const html = esc.replace(PY_TOKENS, (m, str, com, kw, num) => {
    if (str) return '<span class="s">' + str + '</span>';
    if (com) return '<span class="c">' + com + '</span>';
    if (kw) return '<span class="k">' + kw + '</span>';
    if (num) return '<span class="n">' + num + '</span>';
    return m;
  });
  const hl = $('codeHl');
  hl.innerHTML = html;
  hl.style.display = '';
  pre.style.display = 'none';
}

/* ================= المحاكي ================= */
function initSim() {
  simBoard = new SimBoard();
  simBoard.attachMonitor($('simMonitor'));
  simUI = new SimUI($('simBoard'), simBoard);
  simUI.buildAddBar($('simAddBar'));

  $('simRun').addEventListener('click', runSim);
  $('simStop').addEventListener('click', stopSim);
  $('simClearMon').addEventListener('click', () => {
    $('simMonitor').innerHTML = '';
  });
}

async function runSim() {
  if (simInterpreter) return;
  const { program, warnings } = compileNow();
  if (warnings.length) toast('شوف التحذيرات اللي تحت البلوكات 👀', 'warn');
  // تشغيل الصوت محتاج لمسة مستخدم — هنا عندنا ضغطة زر
  simBoard.resetRuntime();
  simBoard.hinted.clear();
  simInterpreter = new Interpreter(simBoard);
  $('simRun').disabled = true;
  $('simStop').disabled = false;
  $('simRun').classList.add('hidden');
  $('simStop').classList.remove('hidden');
  const r = await simInterpreter.run(program);
  simInterpreter = null;
  $('simRun').disabled = false;
  $('simStop').disabled = true;
  $('simRun').classList.remove('hidden');
  $('simStop').classList.add('hidden');
  if (r.status === 'error') {
    toast('خطأ في التشغيل: ' + r.message, 'error', 6000);
    simBoard.print('❌ خطأ: ' + r.message);
  }
}

function stopSim() {
  if (simInterpreter) simInterpreter.stop();
}

/* ================= الشاشة التسلسلية ================= */
function monAppend(text) {
  const mon = $('deviceMonitor');
  const atBottom = mon.scrollTop + mon.clientHeight >= mon.scrollHeight - 40;
  mon.appendChild(document.createTextNode(text));
  // حل خطوط
  if (mon.childNodes.length > 4000) mon.removeChild(mon.firstChild);
  if (atBottom) mon.scrollTop = mon.scrollHeight;
}

/* ================= الرفع على الشريحة ================= */
function openWizard() {
  if (!SerialLink.supported) {
    $('wzUnsupported').style.display = '';
    $('wzBody').style.display = 'none';
  } else {
    $('wzUnsupported').style.display = 'none';
    $('wzBody').style.display = '';
    wzShow(connected ? 'connected' : 'choose');
  }
  openModal('wizardModal');
}

function wzShow(step) {
  for (const s of ['choose', 'checking', 'flash', 'flashing', 'uploading', 'connected', 'done']) {
    const e = $('wz-' + s);
    if (e) e.style.display = 'none';
  }
  const map = {
    choose: 'wz-choose',
    checking: 'wz-checking',
    flash: 'wz-flash',
    flashing: 'wz-flashing',
    uploading: 'wz-uploading',
    connected: 'wz-connected',
    done: 'wz-done',
  };
  const target = $(map[step]);
  if (target) target.style.display = '';
}

async function wzConnect() {
  try {
    if (link) {
      await link.close();
      link = null;
      repl = null;
    }
    link = new SerialLink({
      onStream: (t) => monAppend(t),
      onDisconnect: () => {
        setConnected(false);
        toast('🔌 اتصل المنفذ بالشريحة انفصل', 'warn');
      },
    });
    await link.pickPort();
    wzShow('checking');
    await link.open(115200);
    const probe = await new MpRepl(link).probe(4000);
    if (probe.ok) {
      setConnected(true);
      await wzUpload(true);
    } else {
      wzShow('flash');
    }
  } catch (e) {
    if (e && e.name === 'NotFoundError') {
      wzShow('choose');
      return;
    }
    toast('مشكلة في الاتصال: ' + e.message, 'error', 6000);
    wzShow('choose');
  }
}

async function wzFlash() {
  const key = $('chipSelect').value;
  try {
    if (link) {
      await link.close();
    }
    wzShow('flashing');
    $('flashLog').textContent = '';
    $('flashBar').style.width = '0%';
    const port = link ? link.port : null;
    if (!port) throw new Error('مفيش منفذ — ابدأ من الأول');
    const r = await flashFirmware({
      port,
      key,
      onLog: (line) => {
        const lg = $('flashLog');
        lg.textContent += line + '\n';
        lg.scrollTop = lg.scrollHeight;
      },
      onProgress: (p) => {
        $('flashBar').style.width = Math.round(p * 100) + '%';
      },
    });
    toast('🎉 اتثبّت MicroPython بنجاح!', 'ok', 5000);
    // اتصال تاني وارفع البرنامج
    link = new SerialLink({
      onStream: (t) => monAppend(t),
      onDisconnect: () => setConnected(false),
    });
    await link.open(115200);
    const probe = await new MpRepl(link).probe(4000);
    if (probe.ok) {
      setConnected(true);
      await wzUpload(true);
    } else {
      wzShow('flash');
      toast('التثبيت تم بس الشريحة مش بترد — جرّب تفرقها وتوصلها تاني', 'warn', 7000);
    }
  } catch (e) {
    toast('فشل التثبيت: ' + (e.message || e), 'error', 8000);
    wzShow('flash');
  }
}

async function wzUpload(skipConnCheck) {
  if (!skipConnCheck && !connected) {
    openWizard();
    return;
  }
  try {
    if (!repl) repl = new MpRepl(link);
    wzShow('uploading');
    const { py } = compileNow();
    await repl.writeMain(py);
    toast('✅ البرنامج اتسجل على الشريحة — شغال دلوقتي!', 'ok', 5000);
    await repl.resetAndRun();
    monAppend('\r\n===== ✅ البرنامج بيشتغل على الشريحة! =====\r\n');
    closeModal('wizardModal');
    showTab('monitor');
  } catch (e) {
    toast('فشل رفع البرنامج: ' + (e.message || e), 'error', 8000);
    wzShow('connected');
  }
}

function setConnected(v) {
  connected = v;
  $('connPill').classList.toggle('on', v);
  $('connPill').textContent = v ? '🟢 متصل' : '⚫ غير متصل';
  $('nav-monitor').classList.toggle('disabled', !v);
}

/* ================= مودالز ================= */
function openModal(id) {
  $(id).classList.add('open');
}
function closeModal(id) {
  $(id).classList.remove('open');
}

/* ================= الحفظ والتحميل ================= */
function scheduleSave() {
  clearTimeout(scheduleSave._t);
  scheduleSave._t = setTimeout(() => {
    try {
      const xml = Blockly.Xml.domToText(Blockly.Xml.workspaceToDom(workspace));
      localStorage.setItem('eb_workspace', xml);
      localStorage.setItem('eb_components', JSON.stringify(simBoard.serialize()));
    } catch (e) {
      /* تجاهل */
    }
  }, 600);
}

function loadSaved() {
  const xml = localStorage.getItem('eb_workspace');
  const comps = localStorage.getItem('eb_components');
  if (comps) {
    try {
      simBoard.load(JSON.parse(comps));
    } catch (e) {
      /* تجاهل */
    }
  }
  simUI.renderAll();
  if (xml) {
    try {
      workspace.clear();
      const dom = xmlToDom(xml);
      Blockly.Xml.domToWorkspace(dom, workspace);
      compileNow();
      return;
    } catch (e) {
      /* تجاهل */
    }
  }
  loadExample(0, true);
}

function loadExample(i, silent) {
  const ex = EXAMPLES[i];
  if (!ex) return;
  workspace.clear();
  Blockly.serialization.workspaces.load(ex.blocks, workspace);
  simBoard.clear();
  for (const c of ex.components || []) simBoard.addComponent(c.type, c);
  simUI.renderAll();
  compileNow();
  scheduleSave();
  if (!silent) {
    toast('اتحمّل مثال: ' + ex.title + ' ✨', 'ok');
    showTab('blocks');
  }
}

function exportProject() {
  const data = {
    app: 'electro-block',
    version: 1,
    name: 'مشروعي',
    workspace: Blockly.Xml.domToText(Blockly.Xml.workspaceToDom(workspace)),
    components: simBoard.serialize(),
  };
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  downloadBlob(blob, 'مشروع-الكتروبلوك.json');
  toast('اتحفظ الملف 💾', 'ok');
}

function importProject(file) {
  const reader = new FileReader();
  reader.onload = () => {
    try {
      const data = JSON.parse(reader.result);
      if (data.app !== 'electro-block') throw new Error('ملف غير صالح');
      workspace.clear();
      Blockly.Xml.domToWorkspace(xmlToDom(data.workspace), workspace);
      simBoard.load(data.components);
      simUI.renderAll();
      compileNow();
      scheduleSave();
      toast('اتحمّل المشروع 📂', 'ok');
    } catch (e) {
      toast('الملف ده مش مشروع إلكترو بلوك', 'error');
    }
  };
  reader.readAsText(file);
}

function downloadBlob(blob, name) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 5000);
}

/* ================= ربط الواجهة ================= */
function wireUi() {
  // تابز
  for (const t of TABS) {
    const nav = $('nav-' + t);
    if (nav) nav.addEventListener('click', () => showTab(t));
  }

  $('btnUpload').addEventListener('click', openWizard);
  $('btnUpload2')?.addEventListener('click', openWizard);

  // ويزارد
  $('wzBtnConnect').addEventListener('click', wzConnect);
  $('wzBtnFlash').addEventListener('click', wzFlash);
  $('wzBtnUploadNow').addEventListener('click', () => wzUpload(true));
  $('wzBtnClose').addEventListener('click', () => closeModal('wizardModal'));
  $('wzBtnReinstall').addEventListener('click', () => wzShow('flash'));

  // شاشة تسلسلية
  $('devStop').addEventListener('click', async () => {
    if (repl) {
      await repl.interrupt();
      toast('أرسلتنا إشارة إيقاف ⏹️', 'ok', 2000);
    }
  });
  $('devRerun').addEventListener('click', async () => {
    if (repl) {
      await repl.resetAndRun();
    }
  });
  $('devClearMain').addEventListener('click', async () => {
    if (repl) {
      try {
        await repl.clearMain();
        toast('اتمسح main.py — الشريحة فضيت 🗑️', 'ok');
      } catch (e) {
        toast('مشكلة: ' + e.message, 'error');
      }
    }
  });
  $('devClearMon').addEventListener('click', () => {
    $('deviceMonitor').textContent = '';
  });
  $('devDisconnect').addEventListener('click', async () => {
    if (link) {
      await link.close();
    }
    link = null;
    repl = null;
    setConnected(false);
    toast('اتفصلنا عن الشريحة 👋', 'info');
  });

  // كود
  $('btnCopyCode').addEventListener('click', async () => {
    const { py } = compileNow();
    try {
      await navigator.clipboard.writeText(py);
      toast('اتنسخ الكود 📋', 'ok', 2000);
    } catch (e) {
      toast('المتصفح رفض النسخ — اعمل تحديد يدوي', 'warn');
    }
  });
  $('btnDownloadCode').addEventListener('click', () => {
    const { py } = compileNow();
    downloadBlob(new Blob([py], { type: 'text/x-python' }), 'main.py');
  });

  // قوائم
  $('btnExamples').addEventListener('click', () => openModal('examplesModal'));
  $('btnHelp').addEventListener('click', () => openModal('helpModal'));
  $('btnNew').addEventListener('click', () => {
    if (confirm('تبدأ مشروع جديد؟ (الحالي هيتمسح)')) {
      loadExample(0, true);
      toast('مشروع جديد نظيف 🧹', 'ok');
    }
  });
  $('btnSaveFile').addEventListener('click', exportProject);
  $('btnOpenFile').addEventListener('click', () => $('fileInput').click());
  $('fileInput').addEventListener('change', (e) => {
    if (e.target.files[0]) importProject(e.target.files[0]);
    e.target.value = '';
  });

  // أمثلة
  const grid = $('examplesGrid');
  EXAMPLES.forEach((ex, i) => {
    const card = document.createElement('button');
    card.className = 'ex-card';
    card.innerHTML = `<div class="ex-emoji">${ex.emoji}</div><div class="ex-title">${ex.title}</div><div class="ex-desc">${ex.desc}</div>`;
    card.addEventListener('click', () => {
      closeModal('examplesModal');
      loadExample(i);
    });
    grid.appendChild(card);
  });

  // إغلاق المودالز
  document.querySelectorAll('.modal-back').forEach((m) => {
    m.addEventListener('click', (e) => {
      if (e.target === m) m.classList.remove('open');
    });
  });
  document.querySelectorAll('[data-close]').forEach((b) => {
    b.addEventListener('click', () => b.closest('.modal-back').classList.remove('open'));
  });

  // رسائل الترحيب
  if (!localStorage.getItem('eb_seen')) {
    localStorage.setItem('eb_seen', '1');
    setTimeout(() => openModal('helpModal'), 600);
  }
}

/* ================= أدوات XML ================= */
function xmlToDom(text) {
  if (window.Blockly && Blockly.utils && Blockly.utils.xml && Blockly.utils.xml.textToDom) {
    return Blockly.utils.xml.textToDom(text);
  }
  const doc = new DOMParser().parseFromString(text, 'text/xml');
  if (doc.getElementsByTagName('parsererror').length) throw new Error('ملف المشروع فيه خطأ');
  return doc.documentElement;
}

/* ================= البداية ================= */
window.addEventListener('DOMContentLoaded', () => {
  initBlockly();
  initSim();
  wireUi();
  loadSaved();
  setConnected(false);
  showTab('blocks');

  // خدمة العمل للشغل أوفلاين
  if ('serviceWorker' in navigator && location.protocol === 'https:') {
    navigator.serviceWorker.register('sw.js').catch(() => {});
  }
});
