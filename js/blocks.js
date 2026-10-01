/* ============================================================
   إلكترو بلوك — تعريفات البلوكات المخصصة (ESP32 / MicroPython)
   ============================================================ */

// منافذ ESP32 الآمنة للاستخدام
// 6-11 محجوزة للفلاش — 0/1/3 للبوت واليارت — 34-39 مدخلات فقط
export const OUT_PINS = [2, 4, 5, 12, 13, 14, 15, 16, 17, 18, 19, 21, 22, 23, 25, 26, 27, 32, 33];
export const IN_PINS = [...OUT_PINS, 34, 35, 36, 39];
export const ADC_PINS = [32, 33, 34, 35, 36, 39];

function pinOptions(pins) {
  return pins.map((p) => [`GPIO ${p}`, String(p)]);
}

const OUT_PIN_FIELD = {
  type: 'field_dropdown',
  name: 'PIN',
  options: pinOptions(OUT_PINS),
};
const IN_PIN_FIELD = {
  type: 'field_dropdown',
  name: 'PIN',
  options: pinOptions(IN_PINS),
};
const ADC_PIN_FIELD = {
  type: 'field_dropdown',
  name: 'PIN',
  options: ADC_PINS.map((p) => [`GPIO ${p}`, String(p)]),
};

export const BLOCK_DEFS = [
  // ============ الأحداث ============
  {
    type: 'eb_on_start',
    message0: '🚀 عند البدء (مرة واحدة)',
    nextStatement: null,
    colour: '#FF8A3D',
    tooltip: 'البلوكات اللي هنا بتتنفذ مرة واحدة أول ما الشريحة تشتغل',
    hat: 'cap',
  },
  {
    type: 'eb_loop',
    message0: '🔁 دائمًا (يتكرر للأبد)',
    nextStatement: null,
    colour: '#FF8A3D',
    tooltip: 'البلوكات اللي هنا بتتكرر على طول من غير توقف',
    hat: 'cap',
  },

  // ============ التحكم في الوقت ============
  {
    type: 'eb_sleep',
    message0: '⏳ انتظر %1 %2',
    args0: [
      { type: 'input_value', name: 'MS', check: 'Number' },
      {
        type: 'field_dropdown',
        name: 'UNIT',
        options: [
          ['مللي ثانية', 'ms'],
          ['ثانية', 's'],
        ],
      },
    ],
    previousStatement: null,
    nextStatement: null,
    colour: '#4C8DFF',
    inputsInline: true,
    tooltip: 'وقفة مؤقتة قبل ما يكمل باقي البلوكات',
  },

  // ============ المخرجات ============
  {
    type: 'eb_pin_mode',
    message0: '⚙️ اضبط المنفذ %1 كـ %2',
    args0: [
      OUT_PIN_FIELD,
      {
        type: 'field_dropdown',
        name: 'MODE',
        options: [
          ['🔌 مخرج', 'out'],
          ['📥 مدخل', 'in'],
          ['📥 مدخل مع مقاومة سحب', 'pullup'],
        ],
      },
    ],
    previousStatement: null,
    nextStatement: null,
    colour: '#F5A623',
    inputsInline: true,
    tooltip: 'تحديد وظيفة المنفذ: مخرج (LED/سيرفو/بازر) أو مدخل (زر/حساس)',
  },
  {
    type: 'eb_dwrite',
    message0: '💡 المنفذ %1 ⟶ %2',
    args0: [
      OUT_PIN_FIELD,
      {
        type: 'field_dropdown',
        name: 'VAL',
        options: [
          ['✅ شغّل (1)', '1'],
          ['⛔ أوقف (0)', '0'],
        ],
      },
    ],
    previousStatement: null,
    nextStatement: null,
    colour: '#F5A623',
    inputsInline: true,
    tooltip: 'تشغيل أو إيقاف المنفذ الرقمي (مثلاً LED)',
  },
  {
    type: 'eb_awrite',
    message0: '🔆 المنفذ %1 شدة الإضاءة PWM %2 ٪',
    args0: [
      {
        type: 'field_dropdown',
        name: 'PIN',
        options: pinOptions([2, 4, 5, 12, 13, 14, 15, 16, 17, 18, 19, 21, 22, 23, 25, 26, 27, 32, 33]),
      },
      { type: 'input_value', name: 'DUTY', check: 'Number' },
    ],
    previousStatement: null,
    nextStatement: null,
    colour: '#F5A623',
    inputsInline: true,
    tooltip: 'التحكم في شدة الإضاءة أو سرعة موتور من 0% إلى 100% (PWM)',
  },
  {
    type: 'eb_swrite',
    message0: '🕹️ السيرفو على المنفذ %1 للزاوية %2 درجة',
    args0: [
      OUT_PIN_FIELD,
      { type: 'input_value', name: 'ANGLE', check: 'Number' },
    ],
    previousStatement: null,
    nextStatement: null,
    colour: '#F5A623',
    inputsInline: true,
    tooltip: 'تحريك موتور السيرفو لزاوية من 0 إلى 180 درجة',
  },
  {
    type: 'eb_tone',
    message0: '🔊 نغمة على المنفذ %1 بتردد %2 هرتز لمدة %3 مللي',
    args0: [
      OUT_PIN_FIELD,
      { type: 'input_value', name: 'FREQ', check: 'Number' },
      { type: 'input_value', name: 'DUR', check: 'Number' },
    ],
    previousStatement: null,
    nextStatement: null,
    colour: '#F5A623',
    inputsInline: true,
    tooltip: 'تشغيل نغمة على البازر — المدة بالمللي ثانية (اكتب 0 لنغمة مستمرة)',
  },
  {
    type: 'eb_notone',
    message0: '🔇 أوقف النغمة على المنفذ %1',
    args0: [OUT_PIN_FIELD],
    previousStatement: null,
    nextStatement: null,
    colour: '#F5A623',
    inputsInline: true,
    tooltip: 'إيقاف النغمة الحالية على البازر',
  },

  // ============ المستشعرات (قيم) ============
  {
    type: 'eb_dread',
    message0: '📥 قراءة المنفذ %1',
    args0: [IN_PIN_FIELD],
    output: 'Number',
    colour: '#22C55E',
    inputsInline: true,
    tooltip: 'قراءة قيمة رقمية من منفذ (زر = 0 عند الضغط مع مقاومة السحب)',
  },
  {
    type: 'eb_aread',
    message0: '📊 قراءة المنفذ التناظري %1',
    args0: [ADC_PIN_FIELD],
    output: 'Number',
    colour: '#22C55E',
    inputsInline: true,
    tooltip: 'قراءة قيمة من 0 إلى 1023 (مقاومة متغيرة / حساس ضوء / حساس حرارة)',
  },
  {
    type: 'eb_distance',
    message0: '📏 المسافة بالسنتيمتر (إرسال %1 / استقبال %2)',
    args0: [
      { type: 'field_dropdown', name: 'TRIG', options: pinOptions(OUT_PINS) },
      { type: 'field_dropdown', name: 'ECHO', options: pinOptions(IN_PINS) },
    ],
    output: 'Number',
    colour: '#22C55E',
    inputsInline: true,
    tooltip: 'حساس الموجات فوق الصوتية HC-SR04 — بيرجع المسافة بالسنتيمتر',
  },
  {
    type: 'eb_wait_until',
    message0: '⏸️ انتظر حتى يصبح %1',
    args0: [{ type: 'input_value', name: 'COND', check: 'Boolean' }],
    previousStatement: null,
    nextStatement: null,
    colour: '#4C8DFF',
    inputsInline: true,
    tooltip: 'يوقف البرنامج لحد ما الشرط يتحقق',
  },
  {
    type: 'eb_print',
    message0: '🖨️ اطبع في الشاشة %1',
    args0: [
      {
        type: 'input_value',
        name: 'VAL',
        check: ['Number', 'Boolean', 'String'],
      },
    ],
    previousStatement: null,
    nextStatement: null,
    colour: '#14B8A6',
    inputsInline: true,
    tooltip: 'إظهار قيمة على الشاشة التسلسلية (للتجربة والمراقبة)',
  },
];

/** تسجيل البلوكات على Blockly */
export function registerBlocks(Blockly) {
  // بلوك الأرقام الافتراضي بالعربي
  Blockly.Msg['MATH_NUMBER_TOOLTIP'] = 'رقم';
  Blockly.defineBlocksWithJsonArray(BLOCK_DEFS);

  // بلوك رقم افتراضي عربي — يساعد الأطفال
  if (!Blockly.Blocks['eb_num']) {
    Blockly.Blocks['eb_num'] = {
      init() {
        this.appendDummyInput().appendField(
          new Blockly.FieldNumber(5),
          'NUM'
        );
        this.setOutput(true, 'Number');
        this.setColour('#8B5CF6');
        this.setTooltip('رقم');
      },
    };
  }
}

/** قائمة الأدوات (Toolbox) مصنفة بالعربي */
export function buildToolboxXml() {
  const num = (v) =>
    `<block type="math_number"><field name="NUM">${v}</field></block>`;
  const bool = () => `<block type="logic_boolean"></block>`;
  const sep = `<sep gap="12"></sep>`;

  return `<?xml version="1.0"?>
<xml xmlns="https://developers.google.com/blockly/xml" dir="rtl">
  <category name="🚀 الأحداث" colour="#FF8A3D">
    <block type="eb_on_start"></block>
    ${sep}
    <block type="eb_loop"></block>
  </category>

  <category name="💡 المخرجات" colour="#F5A623">
    <block type="eb_dwrite"></block>
    ${sep}
    <block type="eb_awrite">
      <value name="DUTY">${num(50)}</value>
    </block>
    ${sep}
    <block type="eb_swrite">
      <value name="ANGLE">${num(90)}</value>
    </block>
    ${sep}
    <block type="eb_tone">
      <value name="FREQ">${num(440)}</value>
      <value name="DUR">${num(500)}</value>
    </block>
    ${sep}
    <block type="eb_notone"></block>
    ${sep}
    <block type="eb_pin_mode"></block>
  </category>

  <category name="📥 المستشعرات" colour="#22C55E">
    <block type="eb_dread"></block>
    ${sep}
    <block type="eb_aread"></block>
    ${sep}
    <block type="eb_distance"></block>
  </category>

  <category name="⏳ التحكم" colour="#4C8DFF">
    <block type="eb_sleep">
      <value name="MS">${num(500)}</value>
    </block>
    ${sep}
    <block type="controls_if"></block>
    ${sep}
    <block type="controls_if">
      <mutation else="1"></mutation>
    </block>
    ${sep}
    <block type="controls_repeat_ext">
      <value name="TIMES">${num(10)}</value>
    </block>
    ${sep}
    <block type="controls_whileUntil"></block>
    ${sep}
    <block type="eb_wait_until"></block>
    ${sep}
    <block type="controls_flow_statements"></block>
  </category>

  <category name="🔢 الرياضيات" colour="#8B5CF6">
    <block type="math_number"></block>
    ${sep}
    <block type="math_arithmetic"></block>
    ${sep}
    <block type="math_modulo"></block>
    ${sep}
    <block type="math_random_int">
      <value name="FROM">${num(1)}</value>
      <value name="TO">${num(10)}</value>
    </block>
    ${sep}
    <block type="math_single">
      <field name="OP">ABS</field>
    </block>
  </category>

  <category name="🧠 المنطق" colour="#EF4444">
    ${bool()}
    ${sep}
    <block type="logic_compare"></block>
    ${sep}
    <block type="logic_operation"></block>
    ${sep}
    <block type="logic_negate"></block>
  </category>

  <category name="🔤 النصوص" colour="#14B8A6">
    <block type="eb_print">
      <value name="VAL"><block type="text"><field name="TEXT">أهلًا 👋</field></block></value>
    </block>
    ${sep}
    <block type="text"></block>
    ${sep}
    <block type="text_join"></block>
  </category>

  <category name="📦 المتغيرات" colour="#9333EA" custom="VARIABLE"></category>
</xml>`;
}
