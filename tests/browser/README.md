# اختبارات المتصفح (محاكاة بـ jsdom)

الاختبارات دي بتشغّل الموقع كله في بيئة jsdom — من غير متصفح حقيقي.

## التشغيل
```bash
cd tests/browser
npm init -y
npm i jsdom
node appsmoke.mjs      # فحص بنية HTML + تحميل الوحدات
node integration.mjs   # Blockly حقيقي + الأمثلة السبعة + توليد بايثون
node appfull.mjs       # تشغيل التطبيق كامل (initBlockly + الواجهة + دليل التوصيل)
```
