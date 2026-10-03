"use server";

import { redirect } from "next/navigation";
import { cookies } from "next/headers";
import { createClient } from "@/lib/supabase/server";
import { onboardingSchema } from "@/lib/validations/organization";
import { friendlyErrorMessage, logServerError } from "@/lib/errors";
import { slugify } from "@/lib/utils";
import { ACTIVE_ORG_COOKIE } from "@/lib/auth/session";

export type OnboardingResult = { ok: true } | { ok: false; error: string };

export async function createOrganizationAction(formData: FormData): Promise<OnboardingResult> {
  const subjectsRaw = formData.get("subjects");
  const parsed = onboardingSchema.safeParse({
    name: formData.get("name"),
    orgType: formData.get("orgType"),
    subjects: subjectsRaw ? JSON.parse(String(subjectsRaw)) : [],
    studentCountEstimate: formData.get("studentCountEstimate") || undefined,
  });

  if (!parsed.success) {
    return { ok: false, error: "تحقق من البيانات المدخلة." };
  }

  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) redirect("/login");

  const slug = slugify(parsed.data.name);

  const { data, error } = await supabase.rpc("create_organization", {
    p_name: parsed.data.name,
    p_slug: slug,
    p_org_type: parsed.data.orgType,
    p_subjects: parsed.data.subjects,
    p_student_count_estimate: parsed.data.studentCountEstimate ?? null,
  });

  if (error || !data) {
    logServerError("onboarding.create_organization", error);
    return { ok: false, error: friendlyErrorMessage(error) };
  }

  const cookieStore = await cookies();
  cookieStore.set(ACTIVE_ORG_COOKIE, data.id, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 60 * 60 * 24 * 365,
  });

  redirect("/dashboard");
}
