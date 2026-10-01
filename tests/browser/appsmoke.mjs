/* اختبار تحميل الموقع كله: HTML + كل الوحدات + DOMContentLoaded */
import { JSDOM } from 'jsdom';
import { readFileSync } from 'fs';

const html = readFileSync('../../index.html', 'utf-8');
const dom = new JSDOM(html, {
  url: 'https://example.com/',
  pretendToBeVisual: true,
  runScripts: 'outside-only',
});
global.window = dom.window;
global.document = dom.window.document;
global.DOMParser = dom.window.DOMParser;
global.XMLSerializer = dom.window.XMLSerializer;
global.Node = dom.window.Node;

global.localStorage = dom.window.localStorage;
global.confirm = () => true;

// بلوكلي UMD
const code = readFileSync('../../libs/blockly/blockly.min.js', 'utf-8');
const factory = new Function('window','document','DOMParser','XMLSerializer','Node','navigator', code + '\nreturn Blockly;');
const Blockly = factory(dom.window, dom.window.document, dom.window.DOMParser, dom.window.XMLSerializer, dom.window.Node, dom.window.navigator);
global.Blockly = Blockly;
dom.window.Blockly = Blockly;

// رسائل عربي
const arCode = readFileSync('../../libs/blockly/msg/ar.js', 'utf-8');
new Function('window', arCode)(dom.window);

// كل عناصر الواجهة موجودة؟
const ids = ['blocklyDiv','codeArea','codeHl','deviceMonitor','connPill','btnUpload','btnExamples','btnHelp','btnNew','btnCopyCode','btnDownloadCode',
  'wizardModal','wz-choose','wz-checking','wz-flash','wz-flashing','wz-uploading','wz-connected','wzBtnConnect',
  'wzBtnFlash','wzBtnUploadNow','chipSelect','flashLog','flashBar','examplesModal','examplesGrid','helpModal','toasts',
  'tab-blocks','tab-code','tab-wiring','tab-monitor','nav-blocks','nav-code','nav-wiring','nav-monitor','warnings',
  'devStop','devRerun','devClearMain','devClearMon','devDisconnect','fileInput','btnSaveFile','btnOpenFile','wzUnsupported','wzBody','wzBtnClose','wzBtnReinstall','monCta','ctaConnect','devToolbar'];
const missing = ids.filter(id => !document.getElementById(id));
if (missing.length) { console.log('❌ عناصر ناقصة في HTML:', missing.join(', ')); process.exit(1); }
console.log('✅ كل عناصر HTML موجودة (' + ids.length + ' عنصر)');

// استيراد وحدات الموقع (بدون تشغيل init)
try {
  await import('../../js/app.js');
  console.log('✅ كل وحدات JS اتحملت من غير أخطاء');
} catch (e) {
  console.log('❌ خطأ في تحميل الوحدات:', e.message);
  console.log(e.stack.split('\n').slice(0,4).join('\n'));
  process.exit(1);
}
process.exit(0);
