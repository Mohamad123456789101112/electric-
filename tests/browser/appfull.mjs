/* تشغيل التطبيق بالكامل في jsdom — بتفعيل DOMContentLoaded */
import { JSDOM } from 'jsdom';
import { readFileSync } from 'fs';

const html = readFileSync('../../index.html', 'utf-8');
const dom = new JSDOM(html, { url: 'https://example.com/', pretendToBeVisual: true });
global.window = dom.window;
global.document = dom.window.document;
global.DOMParser = dom.window.DOMParser;
global.XMLSerializer = dom.window.XMLSerializer;
global.Node = dom.window.Node;
global.localStorage = dom.window.localStorage;
global.Element = dom.window.Element;
global.SVGElement = dom.window.SVGElement;
global.HTMLElement = dom.window.HTMLElement;
global.Event = dom.window.Event;
global.TouchEvent = dom.window.TouchEvent || class TouchEvent extends Event {};
global.MouseEvent = dom.window.MouseEvent;
global.KeyboardEvent = dom.window.KeyboardEvent;
global.WheelEvent = dom.window.WheelEvent;
global.FocusEvent = dom.window.FocusEvent;
global.CustomEvent = dom.window.CustomEvent;
global.getComputedStyle = dom.window.getComputedStyle.bind(dom.window);
global.requestAnimationFrame = (cb) => setTimeout(() => cb(Date.now()), 16);
global.cancelAnimationFrame = clearTimeout;
global.confirm = () => true;
global.navigator_serial_absent = true;

const code = readFileSync('../../libs/blockly/blockly.min.js', 'utf-8');
const factory = new Function('window','document','DOMParser','XMLSerializer','Node','navigator', code + '\nreturn Blockly;');
const Blockly = factory(dom.window, dom.window.document, dom.window.DOMParser, dom.window.XMLSerializer, dom.window.Node, dom.window.navigator);
global.Blockly = Blockly;
dom.window.Blockly = Blockly;
new Function('window', readFileSync('../../libs/blockly/msg/ar.js', 'utf-8'))(dom.window);

let boomed = null;
window.addEventListener('error', (e) => { boomed = e.message; });

await import('../../js/app.js');

try {
  window.dispatchEvent(new window.Event('DOMContentLoaded'));
  await new Promise(r => setTimeout(r, 400));
  if (boomed) { console.log('❌ runtime error:', boomed); process.exit(1); }
  console.log('✅ التطبيق اشتغل بالكامل (DOMContentLoaded) بدون أخطاء');
  // فحوصات حالة
  const blocks = Blockly.getMainWorkspace ? Blockly.getMainWorkspace().getAllBlocks(false).length : -1;
  console.log('   بلوكات في مساحة الشغل:', blocks);
  const codeText = document.getElementById('codeArea').textContent;
  console.log('   كود مولد؟', codeText.includes('while True') || codeText.includes('dwrite') ? '✅ نعم' : '❌ لأ — ' + codeText.slice(0,80));
  const nEx = document.getElementById('examplesGrid').children.length;
  console.log('   أمثلة في القايمة:', nEx);
  const nComp = document.getElementById('simBoard').children.length;
  console.log('   مكونات المحاكي:', nComp, nComp ? `(${document.querySelector('.comp-card') ? 'كروت شغالة' : 'فاضي!'})` : '');
  // جرّب زر الأمثلة يفتح المودال
  document.getElementById('btnExamples').click();
  const opened = document.getElementById('examplesModal').classList.contains('open');
  console.log('   مودال الأمثلة بيفتح؟', opened ? '✅' : '❌');
  // جرّب تبويب المحاكي والكود
  document.getElementById('nav-code').click();
  console.log('   تبويب الكود بيفتح؟', document.getElementById('tab-code').classList.contains('active') ? '✅' : '❌');
  document.getElementById('nav-sim').click();
  console.log('   تبويب المحاكي بيفتح؟', document.getElementById('tab-sim').classList.contains('active') ? '✅' : '❌');
} catch (e) {
  console.log('❌ استثناء:', e.message);
  console.log(e.stack.split('\n').slice(0, 5).join('\n'));
  process.exit(1);
}
process.exit(0);
