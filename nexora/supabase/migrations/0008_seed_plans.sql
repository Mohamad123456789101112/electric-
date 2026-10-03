-- =============================================================================
-- NEXORA — 0008: Seed data
-- =============================================================================
-- Only the SaaS plan catalog is seeded. No fake organizations, students,
-- classes or other operational records are created — the product starts
-- genuinely empty for every new tenant.
-- =============================================================================

insert into public.plans (code, name, description, price_monthly, currency, max_students, max_teachers, features)
values
  ('starter', 'Starter', 'للمعلمين المستقلين ومراكز التدريس الصغيرة', 0, 'USD', 30, 1,
    '["إدارة الطلاب والحضور", "واجبات واختبارات أساسية", "تقارير أداء مبسطة"]'::jsonb),
  ('pro', 'Pro', 'للأكاديميات متوسطة الحجم التي تحتاج أدوات تشغيل متكاملة', 29, 'USD', 300, 15,
    '["كل مزايا Starter", "تحليلات متقدمة ولوحة ذكاء", "إدارة مدفوعات ومراسلة", "أدوار وصلاحيات متعددة"]'::jsonb),
  ('business', 'Business', 'للمؤسسات التعليمية الكبيرة متعددة الفروع', 99, 'USD', null, null,
    '["كل مزايا Pro", "طلاب ومعلمون بلا حدود", "سجل تدقيق أمني كامل", "دعم أولوية ومدير حساب"]'::jsonb)
on conflict (code) do update set
  name = excluded.name,
  description = excluded.description,
  price_monthly = excluded.price_monthly,
  max_students = excluded.max_students,
  max_teachers = excluded.max_teachers,
  features = excluded.features;
