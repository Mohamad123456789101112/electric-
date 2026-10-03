"use server";

import { revalidatePath } from "next/cache";
import { requireRole, ADMIN_ROLES } from "@/lib/auth/session";
import { classSchema } from "@/lib/validations/academics";
import { friendlyErrorMessage, logServerError } from "@/lib/errors";

export type ActionResult = { ok: true; id?: string } | { ok: false; error: string };

function parseForm(formData: FormData) {
  return classSchema.safeParse({
    name: formData.get("name"),
    subject: formData.get("subject"),
    teacherId: formData.get("teacherId") ?? "",
    academicYear: formData.get("academicYear"),
    capacity: formData.get("capacity") || undefined,
  });
}

export async function createClassAction(formData: FormData): Promise<ActionResult> {
  const parsed = parseForm(formData);
  if (!parsed.success) return { ok: false, error: parsed.error.issues[0]?.message ?? "تحقق من البيانات" };

  const { supabase, organization, user } = await requireRole(ADMIN_ROLES);
  const v = parsed.data;

  const { data, error } = await supabase
    .from("classes")
    .insert({
      organization_id: organization.id,
      name: v.name,
      subject: v.subject,
      teacher_id: v.teacherId || null,
      academic_year: v.academicYear,
      capacity: v.capacity ?? null,
      created_by: user.id,
    })
    .select("id")
    .single();

  if (error) {
    logServerError("classes.create", error);
    return { ok: false, error: friendlyErrorMessage(error) };
  }

  await supabase.rpc("log_audit_event", {
    p_org_id: organization.id,
    p_action: "class.created",
    p_entity_type: "class",
    p_entity_id: data.id,
    p_metadata: { name: v.name },
  });

  revalidatePath("/classes");
  return { ok: true, id: data.id };
}

export async function updateClassAction(classId: string, formData: FormData): Promise<ActionResult> {
  const parsed = parseForm(formData);
  if (!parsed.success) return { ok: false, error: parsed.error.issues[0]?.message ?? "تحقق من البيانات" };

  const { supabase, organization } = await requireRole(ADMIN_ROLES);
  const v = parsed.data;

  const { error } = await supabase
    .from("classes")
    .update({
      name: v.name,
      subject: v.subject,
      teacher_id: v.teacherId || null,
      academic_year: v.academicYear,
      capacity: v.capacity ?? null,
    })
    .eq("id", classId)
    .eq("organization_id", organization.id);

  if (error) {
    logServerError("classes.update", error);
    return { ok: false, error: friendlyErrorMessage(error) };
  }

  await supabase.rpc("log_audit_event", {
    p_org_id: organization.id,
    p_action: "class.updated",
    p_entity_type: "class",
    p_entity_id: classId,
    p_metadata: { name: v.name },
  });

  revalidatePath("/classes");
  revalidatePath(`/classes/${classId}`);
  return { ok: true };
}

export async function archiveClassAction(classId: string): Promise<ActionResult> {
  const { supabase, organization } = await requireRole(ADMIN_ROLES);

  const { error } = await supabase
    .from("classes")
    .update({ deleted_at: new Date().toISOString() })
    .eq("id", classId)
    .eq("organization_id", organization.id);

  if (error) {
    logServerError("classes.archive", error);
    return { ok: false, error: friendlyErrorMessage(error) };
  }

  await supabase.rpc("log_audit_event", {
    p_org_id: organization.id,
    p_action: "class.archived",
    p_entity_type: "class",
    p_entity_id: classId,
    p_metadata: {},
  });

  revalidatePath("/classes");
  return { ok: true };
}

export async function addStudentToClassAction(classId: string, studentId: string): Promise<ActionResult> {
  const { supabase, organization } = await requireRole(ADMIN_ROLES);

  const { error } = await supabase.from("class_members").insert({ organization_id: organization.id, class_id: classId, student_id: studentId });
  if (error) {
    logServerError("classes.add_student", error);
    return { ok: false, error: friendlyErrorMessage(error) };
  }

  revalidatePath(`/classes/${classId}`);
  return { ok: true };
}

export async function removeStudentFromClassAction(classId: string, memberId: string): Promise<ActionResult> {
  const { supabase, organization } = await requireRole(ADMIN_ROLES);

  const { error } = await supabase.from("class_members").delete().eq("id", memberId).eq("organization_id", organization.id);
  if (error) {
    logServerError("classes.remove_student", error);
    return { ok: false, error: friendlyErrorMessage(error) };
  }

  revalidatePath(`/classes/${classId}`);
  return { ok: true };
}
