/* إلكترو بلوك — خدمة العمل للتشغيل بدون إنترنت */
const CACHE = 'eb-cache-v1';
const CORE = [
  './',
  './index.html',
  './css/style.css',
  './js/app.js',
  './js/blocks.js',
  './js/compiler.js',
  './js/pygen.js',
  './js/interpreter.js',
  './js/simulator.js',
  './js/simui.js',
  './js/repl.js',
  './js/flasher.js',
  './js/examples.js',
  './libs/blockly/blockly.min.js',
  './libs/blockly/msg/ar.js',
  './libs/esptool/bundle.js',
  './manifest.json',
  './img/icon.svg',
  './img/icon-192.png',
  './img/icon-512.png',
  './firmware/esp32/ESP32_GENERIC-20250911-v1.26.1.bin',
  './firmware/esp32c3/ESP32_GENERIC_C3-20250911-v1.26.1.bin',
  './firmware/esp32s3/ESP32_GENERIC_S3-20240602-v1.23.0.bin',
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(CORE)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  if (e.request.method !== 'GET') return;
  e.respondWith(
    caches.match(e.request).then(
      (hit) =>
        hit ||
        fetch(e.request)
          .then((res) => {
            if (res.ok && new URL(e.request.url).origin === location.origin) {
              const copy = res.clone();
              caches.open(CACHE).then((c) => c.put(e.request, copy));
            }
            return res;
          })
          .catch(() => caches.match('./index.html'))
    )
  );
});
