/* ============================================================
   إلكترو بلوك — أمثلة جاهزة (بصيغة Blockly JSON المضمونة)
   ============================================================ */

/* أدوات مختصرة لبناء البلوكات */
const B = (type, extra) => Object.assign({ type }, extra || {});
const N = (v) => ({ shadow: { type: 'math_number', fields: { NUM: v } } });
const NB = (v) => ({ block: { type: 'math_number', fields: { NUM: v } } });
const TXT = (t) => ({ block: { type: 'text', fields: { TEXT: t } } });
const VAR = (id) => ({ block: { type: 'variables_get', fields: { VAR: { id } } } });

/* ربط بلوكات في سلسلة (next) */
function chain(first, ...rest) {
  let cur = first;
  for (const b of rest) {
    cur.next = { block: b };
    cur = b;
  }
  return first;
}

/* غلاف البرنامج */
const wrap = (blocks, variables) =>
  variables ? { variables, blocks: { languageVersion: 0, blocks } } : { blocks: { languageVersion: 0, blocks } };

/* بلوك controls_if مع else */
function ifElse(IF0, DO0, ELSE) {
  return {
    type: 'controls_if',
    extraState: { hasElse: true },
    inputs: { IF0, DO0, ELSE },
  };
}

/* ===== 1) وميض LED ===== */
const ex1 = wrap([
  B('eb_on_start', {
    x: 40, y: 20,
    next: { block: B('eb_print', { inputs: { VAL: TXT('أهلًا! 👋 أنا شريحتك ESP32') } }) },
  }),
  B('eb_loop', {
    x: 40, y: 170,
    next: {
      block: chain(
        B('eb_dwrite', { fields: { PIN: '2', VAL: '1' } }),
        B('eb_sleep', { fields: { UNIT: 'ms' }, inputs: { MS: N(500) } }),
        B('eb_dwrite', { fields: { PIN: '2', VAL: '0' } }),
        B('eb_sleep', { fields: { UNIT: 'ms' }, inputs: { MS: N(500) } })
      ),
    },
  }),
]);

/* ===== 2) زر يشغّل LED ===== */
const ex2 = wrap([
  B('eb_on_start', {
    x: 40, y: 20,
    next: {
      block: chain(
        B('eb_pin_mode', { fields: { PIN: '4', MODE: 'pullup' } }),
        B('eb_print', { inputs: { VAL: TXT('دوس الزر! 👆') } })
      ),
    },
  }),
  B('eb_loop', {
    x: 40, y: 220,
    next: {
      block: ifElse(
        {
          block: B('logic_compare', {
            fields: { OP: 'EQ' },
            inputs: {
              A: { block: B('eb_dread', { fields: { PIN: '4' } }) },
              B: NB(0),
            },
          }),
        },
        { block: B('eb_dwrite', { fields: { PIN: '2', VAL: '1' } }) },
        { block: B('eb_dwrite', { fields: { PIN: '2', VAL: '0' } }) }
      ),
    },
  }),
]);

/* ===== 3) إشارة مرور ===== */
const ex3 = wrap([
  B('eb_on_start', {
    x: 40, y: 20,
    next: { block: B('eb_print', { inputs: { VAL: TXT('إشارة المرور 🚦') } }) },
  }),
  B('eb_loop', {
    x: 40, y: 140,
    next: {
      block: chain(
        B('eb_dwrite', { fields: { PIN: '2', VAL: '1' } }),
        B('eb_sleep', { fields: { UNIT: 'ms' }, inputs: { MS: N(2000) } }),
        B('eb_dwrite', { fields: { PIN: '2', VAL: '0' } }),
        B('eb_dwrite', { fields: { PIN: '4', VAL: '1' } }),
        B('eb_sleep', { fields: { UNIT: 'ms' }, inputs: { MS: N(800) } }),
        B('eb_dwrite', { fields: { PIN: '4', VAL: '0' } }),
        B('eb_dwrite', { fields: { PIN: '5', VAL: '1' } }),
        B('eb_sleep', { fields: { UNIT: 'ms' }, inputs: { MS: N(2000) } }),
        B('eb_dwrite', { fields: { PIN: '5', VAL: '0' } })
      ),
    },
  }),
]);

/* ===== 4) سيرفو بيمسح (بالمتغيرات) ===== */
const V1 = 'var-angle';
const repeatBody = (delta) => ({
  block: chain(
    B('math_change', { fields: { VAR: { id: V1 } }, inputs: { DELTA: N(delta) } }),
    B('eb_swrite', { fields: { PIN: '13' }, inputs: { ANGLE: VAR(V1) } }),
    B('eb_sleep', { fields: { UNIT: 'ms' }, inputs: { MS: N(20) } })
  ),
});
const ex4 = wrap(
  [
    B('eb_on_start', {
      x: 40, y: 20,
      next: {
        block: chain(
          B('variables_set', { fields: { VAR: { id: V1 } }, inputs: { VALUE: NB(0) } }),
          B('eb_print', { inputs: { VAL: TXT('السيرفو بيمسح 🕹️') } })
        ),
      },
    }),
    B('eb_loop', {
      x: 40, y: 220,
      next: {
        block: chain(
          B('controls_repeat_ext', { inputs: { TIMES: N(18), DO: repeatBody(10) } }),
          B('controls_repeat_ext', { inputs: { TIMES: N(18), DO: repeatBody(-10) } })
        ),
      },
    }),
  ],
  [{ name: 'الزاوية', id: V1 }]
);

/* ===== 5) نغمة موسيقية ===== */
const ex5 = wrap([
  B('eb_on_start', {
    x: 40, y: 20,
    next: {
      block: chain(
        B('eb_tone', { fields: { PIN: '15' }, inputs: { FREQ: N(262), DUR: N(300) } }),
        B('eb_tone', { fields: { PIN: '15' }, inputs: { FREQ: N(294), DUR: N(300) } }),
        B('eb_tone', { fields: { PIN: '15' }, inputs: { FREQ: N(330), DUR: N(300) } }),
        B('eb_tone', { fields: { PIN: '15' }, inputs: { FREQ: N(392), DUR: N(600) } })
      ),
    },
  }),
]);

/* ===== 6) إنذار المسافة ===== */
const ex6 = wrap([
  B('eb_loop', {
    x: 40, y: 30,
    next: {
      block: ifElse(
        {
          block: B('logic_compare', {
            fields: { OP: 'LT' },
            inputs: {
              A: { block: B('eb_distance', { fields: { TRIG: '12', ECHO: '14' } }) },
              B: NB(20),
            },
          }),
        },
        { block: B('eb_tone', { fields: { PIN: '15' }, inputs: { FREQ: N(900), DUR: N(150) } }) },
        { block: B('eb_notone', { fields: { PIN: '15' } }) }
      ),
    },
  }),
]);

/* ===== 7) مقاومة تظبط الإضاءة ===== */
const ex7 = wrap([
  B('eb_loop', {
    x: 40, y: 30,
    next: {
      block: B('eb_awrite', {
        fields: { PIN: '2' },
        inputs: {
          DUTY: {
            block: B('math_arithmetic', {
              fields: { OP: 'DIVIDE' },
              inputs: {
                A: { block: B('eb_aread', { fields: { PIN: '32' } }) },
                B: NB(10.23),
              },
            }),
          },
        },
      }),
    },
  }),
]);

export const EXAMPLES = [
  {
    emoji: '💡',
    title: 'وميض LED',
    desc: 'أول برنامج ليك: ليد بينور ويطفي كل نص ثانية',
    blocks: ex1,
    components: [{ type: 'led', pin: 2, color: '#fbbf24' }],
  },
  {
    emoji: '🔘',
    title: 'زر يشغّل LED',
    desc: 'دوس الزر يتنور، اشتان يطفي',
    blocks: ex2,
    components: [
      { type: 'led', pin: 2, color: '#22d3ee' },
      { type: 'button', pin: 4 },
    ],
  },
  {
    emoji: '🚦',
    title: 'إشارة مرور',
    desc: 'أحمر، أصفر، أخضر — زي الشارع بالظبط',
    blocks: ex3,
    components: [
      { type: 'led', pin: 2, color: '#ef4444' },
      { type: 'led', pin: 4, color: '#fbbf24' },
      { type: 'led', pin: 5, color: '#22c55e' },
    ],
  },
  {
    emoji: '🕹️',
    title: 'سيرفو بيمسح',
    desc: 'موتور السيرفو يلف يمين وشمال — بالمتغيرات',
    blocks: ex4,
    components: [{ type: 'servo', pin: 13 }],
  },
  {
    emoji: '🎵',
    title: 'نغمة موسيقية',
    desc: 'البازر بيعزف دو ري مي فا',
    blocks: ex5,
    components: [{ type: 'buzzer', pin: 15 }],
  },
  {
    emoji: '📏',
    title: 'إنذار المسافة',
    desc: 'لو حد قرّب أقل من 20 سم… بيصفر! 🔊',
    blocks: ex6,
    components: [
      { type: 'hcsr04', trig: 12, echo: 14 },
      { type: 'buzzer', pin: 15 },
    ],
  },
  {
    emoji: '🎚️',
    title: 'مقاومة تظبط الإضاءة',
    desc: 'لف المقاومة المتغيرة وشدّة الليد تتغير',
    blocks: ex7,
    components: [
      { type: 'pot', pin: 32 },
      { type: 'led', pin: 2, color: '#fbbf24' },
    ],
  },
];
