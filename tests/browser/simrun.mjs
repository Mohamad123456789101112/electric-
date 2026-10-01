/* تشغيل المحاكي فعليًا في jsdom */
import { JSDOM } from 'jsdom';
import { readFileSync } from 'fs';

const html = readFileSync('../../index.html', 'utf-8');
const dom = new JSDOM(html, { url: 'https://example.com/', pretendToBeVisual: true });
global.window = dom.window; global.document = dom.window.document;
global.DOMParser = dom.window.DOMParser; global.XMLSerializer = dom.window.XMLSerializer; global.Node = dom.window.Node;
global.localStorage = dom.window.localStorage; global.confirm = () => true;
global.Element = dom.window.Element; global.SVGElement = dom.window.SVGElement; global.HTMLElement = dom.window.HTMLElement;
global.Event = dom.window.Event; global.MouseEvent = dom.window.MouseEvent; global.KeyboardEvent = dom.window.KeyboardEvent;
global.FocusEvent = dom.window.FocusEvent; global.CustomEvent = dom.window.CustomEvent; global.WheelEvent = dom.window.WheelEvent;
global.getComputedStyle = dom.window.getComputedStyle.bind(dom.window);
global.requestAnimationFrame = (cb) => setTimeout(() => cb(Date.now()), 16);
global.cancelAnimationFrame = clearTimeout;

const code = readFileSync('../../libs/blockly/blockly.min.js', 'utf-8');
const factory = new Function('window','document','DOMParser','XMLSerializer','Node','navigator', code + '\nreturn Blockly;');
const Blockly = factory(dom.window, dom.window.document, dom.window.DOMParser, dom.window.XMLSerializer, dom.window.Node, dom.window.navigator);
global.Blockly = Blockly; dom.window.Blockly = Blockly;
new Function('window', readFileSync('../../libs/blockly/msg/ar.js', 'utf-8'))(dom.window);

await import('../../js/app.js');
window.dispatchEvent(new window.Event('DOMContentLoaded'));
await new Promise(r => setTimeout(r, 300));

// المثال الافتراضي: وميض ليد على GPIO2 + ليد في المحاكي على 2
document.getElementById('nav-sim').click();
window.__errLog = [];
const origConsoleError = console.error; console.error = (...a) => { window.__errLog.push(a.join(' ')); };
const led = document.querySelector('.led');
const before = led.className;
console.log('حالة الليد قبل التشغيل:', led.className);

document.getElementById('simRun').click();
// الوميض: ينور عند t=0، يطفي عند t=500، ينور تاني عند t=1000
await new Promise(r => setTimeout(r, 250));
console.log('عند 250ms الليد نوار؟', document.querySelector('.led').classList.contains('on') ? '✅' : '❌');
await new Promise(r => setTimeout(r, 500));
console.log('عند 750ms الليد طفي؟', !document.querySelector('.led').classList.contains('on') ? '✅' : '❌');
await new Promise(r => setTimeout(r, 500));
console.log('عند 1250ms رجع نوار؟', document.querySelector('.led').classList.contains('on') ? '✅' : '❌');
console.log('توستات:', document.getElementById('toasts').textContent || 'فاضي');
console.log('الليد style:', document.querySelector('.led')?.getAttribute('style'));

// الطباعة في شاشة المحاكي
const mon = document.getElementById('simMonitor').textContent;
console.log('الشاشة فيها رسالة الترحيب؟', mon.includes('أهلًا') ? '✅' : '❌ → ' + JSON.stringify(mon.slice(0,60)));

// زر الإيقاف
document.getElementById('simStop').click();
await new Promise(r => setTimeout(r, 300));
const runBtnBack = !document.getElementById('simRun').classList.contains('hidden');
console.log('زر التشغيل رجع بعد الإيقاف؟', runBtnBack ? '✅' : '❌');
process.exit(0);
