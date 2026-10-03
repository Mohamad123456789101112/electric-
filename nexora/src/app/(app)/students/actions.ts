"use server";

import { revalidatePath } from "next/cache";
import { requireRole, ADMIN_ROLES } from "@/lib/auth/session";
import { studentSchema } from "@/lib/validations/students";
import { friendlyErrorMessage, logServerError } from "@/lib/errors";

export type ActionResult = { ok: true; id?: string } | { ok: false; error: string };

function parseForm(formData: FormData) {
  return studentSchema.safeParse({
    fullName: formData.get("fullName"),
    studentCode: formData.get("studentCode"),
    email: formData.get("email") ?? "",
    phone: formData.get("phone") ?? "",
    dateOfBirth: formData.get("dateOfBirth") ?? "",
    gender: formData.get("gender") || undefined,
    classId: formData.get("classId") ?? "",
    guardianName: formData.get("guardianName") ?? "",
    guardianPhone: formData.get("guardianPhone") ?? "",
    status: formData.get("status") || "active",
    notes: formData.get("notes") ?? "",
  });
}

export async function createStudentAction(formData: FormData): Promise<ActionResult> {
  const parsed = parseForm(formData);
  if (!parsed.success) {
    return { ok: false, error: parsed.error.issues[0]?.message ?? "تحقق من البيانات المدخلة" };
  }

  const { supabase, organization, user } = await requireRole(ADMIN_ROLES);
  const v = parsed.data;

  const { data, error } = await supabase
    .from("students")
    .insert({
      organization_id: organization.id,
      full_name: v.fullName,
      student_code: v.studentCode,
      email: v.email || null,
      phone: v.phone || null,
      date_of_birth: v.dateOfBirth || null,
      gender: v.gender || null,
      class_id: v.classId || null,
      guardian_name: v.guardianName || null,
      guardian_phone: v.guardianPhone || null,
      status: v.status,
      notes: v.notes || null,
      created_by: user.id,
    })
    .select("id")
    .single();

  if (error) {
    logServerError("students.create", error);
    return { ok: false, error: friendlyErrorMessage(error) };
  }

  await supabase.rpc("log_audit_event", {
    p_org_id: organization.id,
    p_action: "student.created",
    p_entity_type: "student",
    p_entity_id: data.id,
    p_metadata: { full_name: v.fullName, student_code: v.studentCode },
  });

  revalidatePath("/students");
  return { ok: true, id: data.id };
}

export async function updateStudentAction(studentId: string, formData: FormData): Promise<ActionResult> {
  const parsed = parseForm(formData);
  if (!parsed.success) {
    return { ok: false, error: parsed.error.issues[0]?.message ?? "تحقق من البيانات المدخلة" };
  }

  const { supabase, organization } = await requireRole(ADMIN_ROLES);
  const v = parsed.data;

  const { error } = await supabase
    .from("students")
    .update({
      full_name: v.fullName,
      student_code: v.studentCode,
      email: v.email || null,
      phone: v.phone || null,
      date_of_birth: v.dateOfBirth || null,
      gender: v.gender || null,
      class_id: v.classId || null,
      guardian_name: v.guardianName || null,
      guardian_phone: v.guardianPhone || null,
      status: v.status,
      notes: v.notes || null,
    })
    .eq("id", studentId)
    .eq("organization_id", organization.id);

  if (error) {
    logServerError("students.update", error);
    return { ok: false, error: friendlyErrorMessage(error) };
  }

  await supabase.rpc("log_audit_event", {
    p_org_id: organization.id,
    p_action: "student.updated",
    p_entity_type: "student",
    p_entity_id: studentId,
    p_metadata: { full_name: v.fullName },
  });

  revalidatePath("/students");
  revalidatePath(`/students/${studentId}`);
  return { ok: true };
}

export async function setStudentStatusAction(studentId: string, status: "active" | "archived"): Promise<ActionResult> {
  const { supabase, organization } = await requireRole(ADMIN_ROLES);

  const { error } = await supabase
    .from("students")
    .update({ status })
    .eq("id", studentId)
    .eq("organization_id", organization.id);

  if (error) {
    logServerError("students.set_status", error);
    return { ok: false, error: friendlyErrorMessage(error) };
  }

  await supabase.rpc("log_audit_event", {
    p_org_id: organization.id,
    p_action: status === "archived" ? "student.archived" : "student.restored",
    p_entity_type: "student",
    p_entity_id: studentId,
    p_metadata: {},
  });

  revalidatePath("/students");
  return { ok: true };
}

export async function bulkImportStudentsAction(
  rows: Array<{ fullName: string; studentCode: string; email?: string; phone?: string; classId?: string }>
): Promise<{ ok: true; inserted: number; skipped: number; errors: string[] } | { ok: false; error: string }> {
  if (rows.length === 0) return { ok: false, error: "لا توجد بيانات صالحة للاستيراد" };
  if (rows.length > 1000) return { ok: false, error: "الحد الأقصى 1000 طالب في المرة الواحدة" };

  const { supabase, organization, user } = await requireRole(ADMIN_ROLES);

  let inserted = 0;
  const errors: string[] = [];
  const chunkSize = 100;

  for (let i = 0; i < rows.length; i += chunkSize) {
    const chunk = rows.slice(i, i + chunkSize).map((r) => ({
      organization_id: organization.id,
      full_name: r.fullName,
      student_code: r.studentCode,
      email: r.email || null,
      phone: r.phone || null,
      class_id: r.classId || null,
      created_by: user.id,
    }));

    const { data, error } = await supabase.from("students").insert(chunk).select("id");
    if (error) {
      errors.push(friendlyErrorMessage(error));
    } else {
      inserted += data?.length ?? 0;
    }
  }

  await supabase.rpc("log_audit_event", {
    p_org_id: organization.id,
    p_action: "student.bulk_imported",
    p_entity_type: "student",
    p_metadata: { inserted, attempted: rows.length },
  });

  revalidatePath("/students");
  return { ok: true, inserted, skipped: rows.length - inserted, errors };
}
