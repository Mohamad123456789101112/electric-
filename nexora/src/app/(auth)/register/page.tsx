"use client";

import { useState, useTransition } from "react";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { registerSchema, type RegisterInput } from "@/lib/validations/auth";
import { registerAction } from "@/app/auth/actions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AlertCircle, CheckCircle2 } from "lucide-react";

export default function RegisterPage() {
  const [isPending, startTransition] = useTransition();
  const [serverError, setServerError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterInput>({ resolver: zodResolver(registerSchema) });

  const onSubmit = (values: RegisterInput) => {
    setServerError(null);
    const formData = new FormData();
    formData.set("fullName", values.fullName);
    formData.set("email", values.email);
    formData.set("password", values.password);
    formData.set("confirmPassword", values.confirmPassword);

    startTransition(async () => {
      const result = await registerAction(formData);
      if (!result.ok) {
        setServerError(result.error);
        return;
      }
      setSuccessMessage(result.message ?? "تم إنشاء الحساب بنجاح.");
    });
  };

  if (successMessage) {
    return (
      <div className="animate-fade-in text-center">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-success-soft">
          <CheckCircle2 className="h-6 w-6 text-success" />
        </div>
        <h1 className="text-xl font-bold text-ink">تحقق من بريدك الإلكتروني</h1>
        <p className="mt-2 text-sm text-ink-muted">{successMessage}</p>
        <Link href="/login" className="mt-6 inline-block text-sm font-medium text-accent hover:underline">
          العودة لتسجيل الدخول
        </Link>
      </div>
    );
  }

  return (
    <div className="animate-fade-in">
      <h1 className="text-2xl font-bold text-ink">إنشاء حساب جديد</h1>
      <p className="mt-1.5 text-sm text-ink-muted">ابدأ في إدارة مؤسستك التعليمية خلال دقائق.</p>

      <form onSubmit={handleSubmit(onSubmit)} className="mt-8 space-y-4" noValidate>
        {serverError && (
          <div role="alert" className="flex items-start gap-2 rounded-[var(--radius-md)] border border-danger/20 bg-danger-soft px-3.5 py-3 text-sm text-danger">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            {serverError}
          </div>
        )}

        <div>
          <Label htmlFor="fullName">الاسم الكامل</Label>
          <Input id="fullName" autoComplete="name" aria-invalid={!!errors.fullName} {...register("fullName")} />
          {errors.fullName && <p className="mt-1 text-xs text-danger">{errors.fullName.message}</p>}
        </div>

        <div>
          <Label htmlFor="email">البريد الإلكتروني</Label>
          <Input id="email" type="email" autoComplete="email" aria-invalid={!!errors.email} {...register("email")} />
          {errors.email && <p className="mt-1 text-xs text-danger">{errors.email.message}</p>}
        </div>

        <div>
          <Label htmlFor="password">كلمة المرور</Label>
          <Input id="password" type="password" autoComplete="new-password" aria-invalid={!!errors.password} {...register("password")} />
          {errors.password && <p className="mt-1 text-xs text-danger">{errors.password.message}</p>}
        </div>

        <div>
          <Label htmlFor="confirmPassword">تأكيد كلمة المرور</Label>
          <Input id="confirmPassword" type="password" autoComplete="new-password" aria-invalid={!!errors.confirmPassword} {...register("confirmPassword")} />
          {errors.confirmPassword && <p className="mt-1 text-xs text-danger">{errors.confirmPassword.message}</p>}
        </div>

        <Button type="submit" variant="accent" size="lg" className="w-full" loading={isPending}>
          إنشاء الحساب
        </Button>
      </form>

      <p className="mt-6 text-center text-sm text-ink-muted">
        لديك حساب بالفعل؟{" "}
        <Link href="/login" className="font-medium text-accent hover:underline">
          تسجيل الدخول
        </Link>
      </p>
    </div>
  );
}
