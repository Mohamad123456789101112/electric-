/* ============================================================
   إلكترو بلوك — تثبيت MicroPython على الشريحة (مرة واحدة)
   عبر Web Serial + esptool-js
   ============================================================ */
import { ESPLoader, Transport } from '../libs/esptool/bundle.js';

export const FIRMWARE = {
  esp32: {
    label: 'ESP32 الكلاسيكي',
    hint: 'الأشهر — شريحة سوداء عليها ESP32-WROOM',
    file: 'firmware/esp32/ESP32_GENERIC-20250911-v1.26.1.bin',
    version: 'MicroPython v1.26.1',
    address: 0x1000,
    match: ['ESP32'],
  },
  esp32c3: {
    label: 'ESP32-C3',
    hint: 'الشريحة الصغيرة اللي فيها USB صغير وكерамيات صغيرة',
    file: 'firmware/esp32c3/ESP32_GENERIC_C3-20250911-v1.26.1.bin',
    version: 'MicroPython v1.26.1',
    address: 0x0,
    match: ['ESP32-C3'],
  },
  esp32s3: {
    label: 'ESP32-S3',
    hint: 'اللي فيها RAM أكبر وغالبًا USB مبني جواها',
    file: 'firmware/esp32s3/ESP32_GENERIC_S3-20240602-v1.23.0.bin',
    version: 'MicroPython v1.23.0',
    address: 0x0,
    match: ['ESP32-S3'],
  },
};

/** اختار firmware مناسب حسب اسم الشريحة المكتشف */
export function pickFirmwareKey(chipName) {
  const n = String(chipName || '').toUpperCase();
  if (n.includes('C3')) return 'esp32c3';
  if (n.includes('S3')) return 'esp32s3';
  if (n.includes('ESP32')) return 'esp32';
  return null;
}

/**
 * تثبيت firmware على الشريحة
 * @param {SerialPort} port منفذ مفتوح من Web Serial (مقفول حاليًا)
 */
export async function flashFirmware({ port, key, onLog, onProgress }) {
  const fw = FIRMWARE[key];
  if (!fw) throw new Error('نوع شريحة غير معروف');

  onLog('🔗 بفتح اتصال مع الـ bootloader...');
  const transport = new Transport(port, true);
  const esp = new ESPLoader({
    transport,
    baudrate: 460800,
    romBaudrate: 115200,
    terminal: {
      clean() {},
      writeLine(d) {
        onLog(String(d));
      },
      write(d) {
        onLog(String(d));
      },
    },
  });

  try {
    const chip = await esp.main();
    onLog(`✅ اتصلت بالشريحة: ${chip}`);

    // لو الشريحة المكتشفة مختلفة عن المختارة — نحول تلقائيًا
    let useKey = key;
    const detected = pickFirmwareKey(chip);
    if (detected && detected !== key) {
      onLog(`ℹ️ الشريحة المكتشفة مختلفة — هستخدم firmware بتاع ${FIRMWARE[detected].label}`);
      useKey = detected;
    }
    const useFw = FIRMWARE[useKey];

    onLog(`⬇️ بحمّل ملف النظام (${useFw.version})...`);
    const res = await fetch(useFw.file);
    if (!res.ok) throw new Error(`فشل تحميل ملف النظام (${res.status})`);
    const data = new Uint8Array(await res.arrayBuffer());

    onLog(`🚀 بثبّت النظام على الشريحة... (دقيقة تقريبًا — متفصلش الكابل!)`);
    await esp.writeFlash({
      fileArray: [{ data, address: useFw.address }],
      flashMode: 'keep',
      flashFreq: 'keep',
      flashSize: 'keep',
      eraseAll: false,
      compress: true,
      reportProgress: (fileIndex, written, total) => {
        onProgress(Math.min(1, written / Math.max(1, total)));
      },
    });

    onLog('🔄 بعمل إعادة تشغيل للشريحة...');
    await esp.after('hard_reset');
    await sleep(600);
    onLog('🎉 اتثبّت النظام بنجاح!');
    return { ok: true, usedKey: useKey, chip };
  } finally {
    try {
      await transport.disconnect();
    } catch (e) {
      /* تجاهل */
    }
  }
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}
