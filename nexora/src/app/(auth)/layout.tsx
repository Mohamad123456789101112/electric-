import Link from "next/link";
import { Sparkles } from "lucide-react";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid min-h-screen grid-cols-1 lg:grid-cols-2">
      <div className="flex flex-col justify-between p-8 sm:p-12">
        <Link href="/" className="inline-flex items-center gap-2 text-lg font-bold tracking-tight text-ink">
          <span className="flex h-8 w-8 items-center justify-center rounded-[var(--radius-sm)] bg-ink text-white">N</span>
          NEXORA
        </Link>
        <div className="mx-auto w-full max-w-sm py-16">{children}</div>
        <p className="text-center text-xs text-ink-muted">© {new Date().getFullYear()} NEXORA. جميع الحقوق محفوظة.</p>
      </div>
      <div className="relative hidden overflow-hidden bg-ink lg:flex lg:flex-col lg:justify-between lg:p-12">
        <div
          className="absolute inset-0 opacity-[0.07]"
          style={{
            backgroundImage:
              "linear-gradient(to left, white 1px, transparent 1px), linear-gradient(to top, white 1px, transparent 1px)",
            backgroundSize: "44px 44px",
          }}
        />
        <div className="relative z-10 inline-flex w-fit items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3 py-1.5 text-xs text-white/80">
          <Sparkles className="h-3.5 w-3.5" />
          NEXORA Intelligence
        </div>
        <div className="relative z-10 space-y-4">
          <p className="text-3xl font-bold leading-tight text-white">
            نظام تشغيل واحد لإدارة التعليم، من الحضور إلى الدرجات والمدفوعات.
          </p>
          <p className="max-w-md text-sm leading-relaxed text-white/60">
            منصة آمنة متعددة المؤسسات مبنية على صلاحيات دقيقة وعزل كامل للبيانات بين كل مؤسسة وأخرى.
          </p>
        </div>
        <div className="relative z-10 flex items-center gap-6 text-xs text-white/50">
          <span>تشفير شامل</span>
          <span>عزل بيانات كامل</span>
          <span>سجل تدقيق أمني</span>
        </div>
      </div>
    </div>
  );
}
