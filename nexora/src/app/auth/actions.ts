"use server";

import { createClient } from "@/lib/supabase/server";
import { loginSchema, registerSchema, forgotPasswordSchema, resetPasswordSchema } from "@/lib/validations/auth";
import { friendlyErrorMessage, logServerError } from "@/lib/errors";

export type ActionResult = { ok: true; message?: string } | { ok: false; error: string; fieldErrors?: Record<string, string> };

function siteUrl() {
  return process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";
}

export async function loginAction(formData: FormData): Promise<ActionResult> {
  const parsed = loginSchema.safeParse({
    email: formData.get("email"),
    password: formData.get("password"),
  });
  if (!parsed.success) {
    return { ok: false, error: "تحقق من البيانات المدخلة", fieldErrors: flatten(parsed.error) };
  }

  const supabase = await createClient();
  const { error, data } = await supabase.auth.signInWithPassword(parsed.data);

  if (error) {
    logServerError("auth.login", error);
    if (error.message.toLowerCase().includes("email not confirmed")) {
      return { ok: false, error: "يرجى تأكيد بريدك الإلكتروني أولاً. تحقق من صندوق الوارد." };
    }
    return { ok: false, error: "البريد الإلكتروني أو كلمة المرور غير صحيحة." };
  }

  if (data.user) {
    await supabase.rpc("log_audit_event", {
      p_org_id: null,
      p_action: "auth.login",
      p_entity_type: "user",
      p_entity_id: data.user.id,
      p_metadata: {},
    });
    // Link any pending invites sent to this email before the account existed.
    await supabase.rpc("accept_pending_invites");
  }

  return { ok: true };
}

export async function registerAction(formData: FormData): Promise<ActionResult> {
  const parsed = registerSchema.safeParse({
    fullName: formData.get("fullName"),
    email: formData.get("email"),
    password: formData.get("password"),
    confirmPassword: formData.get("confirmPassword"),
  });
  if (!parsed.success) {
    return { ok: false, error: "تحقق من البيانات المدخلة", fieldErrors: flatten(parsed.error) };
  }

  const supabase = await createClient();
  const { error } = await supabase.auth.signUp({
    email: parsed.data.email,
    password: parsed.data.password,
    options: {
      data: { full_name: parsed.data.fullName },
      emailRedirectTo: `${siteUrl()}/auth/callback?next=/onboarding`,
    },
  });

  if (error) {
    logServerError("auth.register", error);
    if (error.message.toLowerCase().includes("already registered") || error.message.toLowerCase().includes("already exists")) {
      return { ok: false, error: "هذا البريد الإلكتروني مسجل بالفعل. جرّب تسجيل الدخول." };
    }
    return { ok: false, error: friendlyErrorMessage(error) };
  }

  return { ok: true, message: "تم إنشاء الحساب! تحقق من بريدك الإلكتروني لتأكيد الحساب قبل تسجيل الدخول." };
}

export async function logoutAction(): Promise<ActionResult> {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (user) {
    await supabase.rpc("log_audit_event", {
      p_org_id: null,
      p_action: "auth.logout",
      p_entity_type: "user",
      p_entity_id: user.id,
      p_metadata: {},
    });
  }

  await supabase.auth.signOut();
  return { ok: true };
}

export async function forgotPasswordAction(formData: FormData): Promise<ActionResult> {
  const parsed = forgotPasswordSchema.safeParse({ email: formData.get("email") });
  if (!parsed.success) {
    return { ok: false, error: "أدخل بريداً إلكترونياً صحيحاً" };
  }

  const supabase = await createClient();
  const { error } = await supabase.auth.resetPasswordForEmail(parsed.data.email, {
    redirectTo: `${siteUrl()}/auth/callback?next=/reset-password`,
  });

  if (error) {
    logServerError("auth.forgot-password", error);
    // Do not leak whether the email exists — always return a generic success.
  }

  return { ok: true, message: "إذا كان هذا البريد مسجلاً لدينا، فستصلك رسالة لإعادة تعيين كلمة المرور." };
}

export async function resetPasswordAction(formData: FormData): Promise<ActionResult> {
  const parsed = resetPasswordSchema.safeParse({
    password: formData.get("password"),
    confirmPassword: formData.get("confirmPassword"),
  });
  if (!parsed.success) {
    return { ok: false, error: "تحقق من البيانات المدخلة", fieldErrors: flatten(parsed.error) };
  }

  const supabase = await createClient();
  const { error } = await supabase.auth.updateUser({ password: parsed.data.password });

  if (error) {
    logServerError("auth.reset-password", error);
    return { ok: false, error: "انتهت صلاحية رابط إعادة التعيين أو أنه غير صالح. اطلب رابطاً جديداً." };
  }

  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (user) {
    await supabase.rpc("log_audit_event", {
      p_org_id: null,
      p_action: "auth.password_reset",
      p_entity_type: "user",
      p_entity_id: user.id,
      p_metadata: {},
    });
  }

  return { ok: true, message: "تم تحديث كلمة المرور بنجاح." };
}

function flatten(error: { flatten: () => { fieldErrors: Record<string, string[] | undefined> } }) {
  const { fieldErrors } = error.flatten();
  const out: Record<string, string> = {};
  for (const [key, value] of Object.entries(fieldErrors)) {
    if (value?.[0]) out[key] = value[0];
  }
  return out;
}
