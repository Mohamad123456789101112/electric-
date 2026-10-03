"use client";

import { useState, useTransition } from "react";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { forgotPasswordSchema } from "@/lib/validations/auth";
import { forgotPasswordAction } from "@/app/auth/actions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { CheckCircle2 } from "lucide-react";
import { z } from "zod";

type FormValues = z.infer<typeof forgotPasswordSchema>;

export default function ForgotPasswordPage() {
  const [isPending, startTransition] = useTransition();
  const [sentMessage, setSentMessage] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(forgotPasswordSchema) });

  const onSubmit = (values: FormValues) => {
    const formData = new FormData();
    formData.set("email", values.email);
    startTransition(async () => {
      const result = await forgotPasswordAction(formData);
      setSentMessage(result.ok ? result.message ?? null : null);
    });
  };

  if (sentMessage) {
    return (
      <div className="animate-fade-in text-center">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-success-soft">
          <CheckCircle2 className="h-6 w-6 text-success" />
        </div>
        <h1 className="text-xl font-bold text-ink">تحقق من بريدك الإلكتروني</h1>
        <p className="mt-2 text-sm text-ink-muted">{sentMessage}</p>
        <Link href="/login" className="mt-6 inline-block text-sm font-medium text-accent hover:underline">
          العودة لتسجيل الدخول
        </Link>
      </div>
    );
  }

  return (
    <div className="animate-fade-in">
      <h1 className="text-2xl font-bold text-ink">نسيت كلمة المرور؟</h1>
      <p className="mt-1.5 text-sm text-ink-muted">أدخل بريدك الإلكتروني وسنرسل لك رابطاً لإعادة التعيين.</p>

      <form onSubmit={handleSubmit(onSubmit)} className="mt-8 space-y-4" noValidate>
        <div>
          <Label htmlFor="email">البريد الإلكتروني</Label>
          <Input id="email" type="email" autoComplete="email" aria-invalid={!!errors.email} {...register("email")} />
          {errors.email && <p className="mt-1 text-xs text-danger">{errors.email.message}</p>}
        </div>

        <Button type="submit" variant="accent" size="lg" className="w-full" loading={isPending}>
          إرسال رابط إعادة التعيين
        </Button>
      </form>

      <p className="mt-6 text-center text-sm text-ink-muted">
        تذكرت كلمة المرور؟{" "}
        <Link href="/login" className="font-medium text-accent hover:underline">
          تسجيل الدخول
        </Link>
      </p>
    </div>
  );
}
