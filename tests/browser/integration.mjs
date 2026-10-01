/* الاختبار التكاملي الشامل: Blockly حقيقي + أمثلة الموقع + المترجم + مولد البايثون + فحص بايثون */
import { JSDOM } from 'jsdom';
import { readFileSync, writeFileSync } from 'fs';

const dom = new JSDOM('<!DOCTYPE html><html><body></body></html>', { pretendToBeVisual: true });
global.window = dom.window;
global.document = dom.window.document;
global.DOMParser = dom.window.DOMParser;
global.XMLSerializer = dom.window.XMLSerializer;
global.Node = dom.window.Node;

const code = readFileSync('../../libs/blockly/blockly.min.js', 'utf-8');
const factory = new Function('window', 'document', 'DOMParser', 'XMLSerializer', 'Node', 'navigator', code + '\nreturn Blockly;');
const Blockly = factory(dom.window, dom.window.document, dom.window.DOMParser, dom.window.XMLSerializer, dom.window.Node, dom.window.navigator);
global.Blockly = Blockly;

const { registerBlocks, buildToolboxXml } = await import('../../js/blocks.js');
const { compileProgram } = await import('../../js/compiler.js');
const { generatePython } = await import('../../js/pygen.js');
const { EXAMPLES } = await import('../../js/examples.js');

registerBlocks(Blockly);

// 1) صلاحية الـ toolbox
const toolboxXml = buildToolboxXml();
const tdom = new dom.window.DOMParser().parseFromString(toolboxXml, 'text/xml');
if (tdom.getElementsByTagName('parsererror').length) throw new Error('toolbox XML به خطأ');
console.log('✅ toolbox XML سليم:', tdom.getElementsByTagName('category').length, 'قسم');

// 2) كل مثال: تحميل + ترجمة + توليد بايثون
let allOk = true;
for (let i = 0; i < EXAMPLES.length; i++) {
  const ex = EXAMPLES[i];
  const ws = new Blockly.Workspace();
  try {
    Blockly.serialization.workspaces.load(ex.blocks, ws);
    const nBlocks = ws.getAllBlocks(false).length;
    if (nBlocks < 2) throw new Error(`بلوكات قليلة جدًا (${nBlocks})`);
    const { program, warnings } = compileProgram(ws.getTopBlocks(false));
    if (warnings.length) console.log(`   ⚠️ ${ex.title}: ${warnings.join(' | ')}`);
    const py = generatePython(program);
    if (py.trim().length < 30) throw new Error('كود فاضي');
    if (warnings.some(w => w.includes('مش هتتنفذ') || w.includes('أكثر من'))) throw new Error('تحذير حرج: ' + warnings[0]);
    writeFileSync(`/tmp/py/ex_${i}.py`, py);
    console.log(`✅ ${ex.title} — ${nBlocks} بلوك → ${py.split('\n').length} سطر بايثون`);
  } catch (e) {
    allOk = false;
    console.log(`❌ ${ex.title}: ${e.message}`);
  } finally {
    ws.dispose();
  }
}
process.exit(allOk ? 0 : 1);
