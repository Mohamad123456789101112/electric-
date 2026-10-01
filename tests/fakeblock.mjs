/* أداة لاختبارات الكود فقط — مش جزء من الموقع ولا بيوصله لأي متصفح
   بتحاكي شكل بلوك Blockly كـ object عادي عشان الاختبارات تشتغل من غير متصفح */
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
