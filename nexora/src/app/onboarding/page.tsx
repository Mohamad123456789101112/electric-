"use client";

import { useState, useTransition } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Building2, GraduationCap, Users, Check, ArrowLeft, ArrowRight, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { organizationTypeOptions } from "@/lib/validations/organization";
import { createOrganizationAction } from "./actions";

const SUBJECT_SUGGESTIONS = ["رياضيات", "لغة عربية", "لغة إنجليزية", "علوم", "فيزياء", "كيمياء", "أحياء", "تاريخ", "جغرافيا"];

const STEPS = ["المؤسسة", "التفاصيل", "المراجعة"] as const;

export default function OnboardingPage() {
  const [step, setStep] = useState(0);
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [orgType, setOrgType] = useState<string>("academy");
  const [subjects, setSubjects] = useState<string[]>([]);
  const [studentCount, setStudentCount] = useState<string>("");

  const toggleSubject = (s: string) => {
    setSubjects((prev) => (prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]));
  };

  const canProceedStep0 = name.trim().length >= 2;

  const submit = () => {
    setError(null);
    const formData = new FormData();
    formData.set("name", name);
    formData.set("orgType", orgType);
    formData.set("subjects", JSON.stringify(subjects));
    if (studentCount) formData.set("studentCountEstimate", studentCount);

    startTransition(async () => {
      const result = await createOrganizationAction(formData);
      if (result && !result.ok) setError(result.error);
    });
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface px-4 py-12">
      <div className="w-full max-w-xl">
        <div className="mb-8 flex items-center justify-center gap-2">
          {STEPS.map((label, i) => (
            <div key={label} className="flex items-center gap-2">
              <div
                className={cn(
                  "flex h-8 w-8 items-center justify-center rounded-full text-xs font-semibold transition-colors",
                  i < step ? "bg-accent text-white" : i === step ? "bg-ink text-white" : "bg-surface-strong text-ink-muted"
                )}
              >
                {i < step ? <Check className="h-3.5 w-3.5" /> : i + 1}
              </div>
              {i < STEPS.length - 1 && <div className={cn("h-px w-10", i < step ? "bg-accent" : "bg-border")} />}
            </div>
          ))}
        </div>

        <Card className="p-7 sm:p-9">
          <AnimatePresence mode="wait">
            {step === 0 && (
              <motion.div
                key="step0"
                initial={{ opacity: 0, x: 16 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -16 }}
                transition={{ duration: 0.25 }}
              >
                <h1 className="text-xl font-bold text-ink">لنُنشئ مؤسستك التعليمية</h1>
                <p className="mt-1.5 text-sm text-ink-muted">ستصبح تلقائياً المالك (Owner) لهذه المؤسسة.</p>

                <div className="mt-6">
                  <Label htmlFor="org-name">اسم المؤسسة</Label>
                  <Input id="org-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="أكاديمية المستقبل" />
                </div>

                <div className="mt-5">
                  <Label>نوع المؤسسة</Label>
                  <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                    {organizationTypeOptions.map((opt) => (
                      <button
                        key={opt.value}
                        type="button"
                        onClick={() => setOrgType(opt.value)}
                        className={cn(
                          "flex flex-col items-center gap-1.5 rounded-[var(--radius-md)] border px-3 py-3 text-xs font-medium transition-all",
                          orgType === opt.value
                            ? "border-accent bg-accent-soft text-accent"
                            : "border-border text-ink-soft hover:border-border-strong"
                        )}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </div>

                <Button
                  className="mt-7 w-full"
                  variant="accent"
                  size="lg"
                  disabled={!canProceedStep0}
                  onClick={() => setStep(1)}
                >
                  التالي
                  <ArrowLeft className="h-4 w-4" />
                </Button>
              </motion.div>
            )}

            {step === 1 && (
              <motion.div key="step1" initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -16 }} transition={{ duration: 0.25 }}>
                <h1 className="text-xl font-bold text-ink">تفاصيل إضافية</h1>
                <p className="mt-1.5 text-sm text-ink-muted">تساعدنا هذه المعلومات على تهيئة تجربتك (اختياري).</p>

                <div className="mt-6">
                  <Label>المواد الدراسية</Label>
                  <div className="flex flex-wrap gap-2">
                    {SUBJECT_SUGGESTIONS.map((s) => (
                      <button
                        key={s}
                        type="button"
                        onClick={() => toggleSubject(s)}
                        className={cn(
                          "rounded-full border px-3 py-1.5 text-xs font-medium transition-all",
                          subjects.includes(s) ? "border-accent bg-accent-soft text-accent" : "border-border text-ink-soft hover:border-border-strong"
                        )}
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="mt-5">
                  <Label htmlFor="student-count">العدد التقريبي للطلاب</Label>
                  <Input
                    id="student-count"
                    type="number"
                    min={0}
                    value={studentCount}
                    onChange={(e) => setStudentCount(e.target.value)}
                    placeholder="مثال: 120"
                  />
                </div>

                <div className="mt-7 flex gap-2">
                  <Button variant="outline" size="lg" onClick={() => setStep(0)}>
                    <ArrowRight className="h-4 w-4" />
                    السابق
                  </Button>
                  <Button variant="accent" size="lg" className="flex-1" onClick={() => setStep(2)}>
                    التالي
                    <ArrowLeft className="h-4 w-4" />
                  </Button>
                </div>
              </motion.div>
            )}

            {step === 2 && (
              <motion.div key="step2" initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -16 }} transition={{ duration: 0.25 }}>
                <h1 className="text-xl font-bold text-ink">مراجعة وإنشاء</h1>
                <p className="mt-1.5 text-sm text-ink-muted">تأكد من البيانات قبل إنشاء مؤسستك.</p>

                <div className="mt-6 space-y-3 rounded-[var(--radius-md)] bg-surface p-4 text-sm">
                  <SummaryRow icon={Building2} label="اسم المؤسسة" value={name} />
                  <SummaryRow icon={GraduationCap} label="النوع" value={organizationTypeOptions.find((o) => o.value === orgType)?.label ?? ""} />
                  <SummaryRow icon={Users} label="عدد الطلاب التقريبي" value={studentCount || "غير محدد"} />
                  {subjects.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 pt-1">
                      {subjects.map((s) => (
                        <span key={s} className="rounded-full bg-paper px-2.5 py-1 text-xs text-ink-soft">
                          {s}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                {error && <p className="mt-4 text-sm text-danger">{error}</p>}

                <div className="mt-7 flex gap-2">
                  <Button variant="outline" size="lg" onClick={() => setStep(1)} disabled={isPending}>
                    <ArrowRight className="h-4 w-4" />
                    السابق
                  </Button>
                  <Button variant="accent" size="lg" className="flex-1" onClick={submit} disabled={isPending}>
                    {isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
                    إنشاء المؤسسة
                  </Button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </Card>
      </div>
    </div>
  );
}

function SummaryRow({ icon: Icon, label, value }: { icon: React.ComponentType<{ className?: string }>; label: string; value: string }) {
  return (
    <div className="flex items-center gap-3">
      <div className="flex h-8 w-8 items-center justify-center rounded-full bg-paper text-ink-muted">
        <Icon className="h-4 w-4" />
      </div>
      <div>
        <p className="text-xs text-ink-muted">{label}</p>
        <p className="font-medium text-ink">{value}</p>
      </div>
    </div>
  );
}
