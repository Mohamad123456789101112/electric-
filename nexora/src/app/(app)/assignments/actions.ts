"use server";

import { revalidatePath } from "next/cache";
import { requireActiveOrg, requireRole, STAFF_ROLES } from "@/lib/auth/session";
import { assignmentSchema, gradeEntrySchema } from "@/lib/validations/academics";
import { friendlyErrorMessage, logServerError } from "@/lib/errors";
import { z } from "zod";

export type ActionResult = { ok: true; id?: string } | { ok: false; error: string };

function parseForm(formData: FormData) {
  return assignmentSchema.safeParse({
    classId: formData.get("classId"),
    title: formData.get("title"),
    description: formData.get("description") ?? "",
    maxScore: formData.get("maxScore") || 100,
    deadline: formData.get("deadline"),
  });
}

async function assertTeachesClass(supabase: Awaited<ReturnType<typeof requireActiveOrg>>["supabase"], role: string, userId: string, classId: string) {
  if (role === "teacher") {
    const { data } = await supabase.from("classes").select("teacher_id").eq("id", classId).maybeSingle();
    if (!data || data.teacher_id !== userId) return false;
  }
  return true;
}

export async function createAssignmentAction(formData: FormData): Promise<ActionResult> {
  const parsed = parseForm(formData);
  if (!parsed.success) return { ok: false, error: parsed.error.issues[0]?.message ?? "تحقق من البيانات" };

  const { supabase, organization, user, membership } = await requireRole(STAFF_ROLES);
  const v = parsed.data;

  if (!(await assertTeachesClass(supabase, membership.role, user.id, v.classId))) {
    return { ok: false, error: "ليست لديك صلاحية إضافة واجب لهذا الفصل" };
  }

  const { data, error } = await supabase
    .from("assignments")
    .insert({
      organization_id: organization.id,
      class_id: v.classId,
      title: v.title,
      description: v.description || null,
      max_score: v.maxScore,
      deadline: new Date(v.deadline).toISOString(),
      created_by: user.id,
    })
    .select("id")
    .single();

  if (error) {
    logServerError("assignments.create", error);
    return { ok: false, error: friendlyErrorMessage(error) };
  }

  await supabase.rpc("log_audit_event", {
    p_org_id: organization.id,
    p_action: "assignment.created",
    p_entity_type: "assignment",
    p_entity_id: data.id,
    p_metadata: { title: v.title },
  });

  revalidatePath("/assignments");
  return { ok: true, id: data.id };
}

export async function setAssignmentAttachmentAction(
  assignmentId: string,
  objectPath: string,
  filename: string,
  mimeType: string,
  sizeBytes: number
): Promise<ActionResult> {
  const { supabase, organization, user } = await requireRole(STAFF_ROLES);

  const { error } = await supabase.from("assignments").update({ attachment_path: objectPath }).eq("id", assignmentId).eq("organization_id", organization.id);
  if (error) {
    logServerError("assignments.attach", error);
    return { ok: false, error: friendlyErrorMessage(error) };
  }

  await supabase.from("files").insert({
    organization_id: organization.id,
    owner_id: user.id,
    bucket_id: "assignment-files",
    object_path: objectPath,
    filename,
    mime_type: mimeType,
    size_bytes: sizeBytes,
    entity_type: "assignment",
    entity_id: assignmentId,
  });

  revalidatePath(`/assignments/${assignmentId}`);
  return { ok: true };
}

export async function archiveAssignmentAction(assignmentId: string): Promise<ActionResult> {
  const { supabase, organization } = await requireRole(STAFF_ROLES);

  const { error } = await supabase
    .from("assignments")
    .update({ deleted_at: new Date().toISOString() })
    .eq("id", assignmentId)
    .eq("organization_id", organization.id);

  if (error) {
    logServerError("assignments.archive", error);
    return { ok: false, error: friendlyErrorMessage(error) };
  }

  revalidatePath("/assignments");
  return { ok: true };
}

export async function gradeSubmissionAction(assignmentId: string, studentId: string, formData: FormData): Promise<ActionResult> {
  const parsed = gradeEntrySchema.pick({ score: true, feedback: true }).safeParse({
    score: formData.get("score"),
    feedback: formData.get("feedback") ?? "",
  });
  if (!parsed.success) return { ok: false, error: parsed.error.issues[0]?.message ?? "تحقق من البيانات" };

  const { supabase, organization, user } = await requireRole(STAFF_ROLES);

  // Upsert so a student who never submitted can still be graded directly by
  // staff (creates the submission row), while an existing submission is
  // simply updated with the score/feedback.
  const { error } = await supabase.from("submissions").upsert(
    {
      organization_id: organization.id,
      assignment_id: assignmentId,
      student_id: studentId,
      score: parsed.data.score,
      feedback: parsed.data.feedback || null,
      status: "graded",
      graded_by: user.id,
      graded_at: new Date().toISOString(),
    },
    { onConflict: "assignment_id,student_id" }
  );

  if (error) {
    logServerError("submissions.grade", error);
    return { ok: false, error: friendlyErrorMessage(error) };
  }

  await supabase.rpc("log_audit_event", {
    p_org_id: organization.id,
    p_action: "grade.submission_graded",
    p_entity_type: "assignment",
    p_entity_id: assignmentId,
    p_metadata: { student_id: studentId, score: parsed.data.score },
  });

  revalidatePath("/assignments");
  revalidatePath(`/assignments/${assignmentId}`);
  return { ok: true };
}

const submitSchema = z.object({
  assignmentId: z.string().uuid(),
  studentId: z.string().uuid(),
  filePath: z.string().optional(),
  content: z.string().max(5000).optional(),
});

export async function submitAssignmentAction(input: z.infer<typeof submitSchema>): Promise<ActionResult> {
  const parsed = submitSchema.safeParse(input);
  if (!parsed.success) return { ok: false, error: "تحقق من البيانات" };
  if (!parsed.data.filePath && !parsed.data.content) {
    return { ok: false, error: "أضف ملفاً أو نصاً للتسليم" };
  }

  const { supabase, organization } = await requireActiveOrg();
  const { assignmentId, studentId, filePath, content } = parsed.data;

  const { error } = await supabase.from("submissions").upsert(
    {
      organization_id: organization.id,
      assignment_id: assignmentId,
      student_id: studentId,
      file_path: filePath ?? null,
      content: content ?? null,
      submitted_at: new Date().toISOString(),
      status: "submitted",
    },
    { onConflict: "assignment_id,student_id" }
  );

  if (error) {
    logServerError("submissions.submit", error);
    return { ok: false, error: friendlyErrorMessage(error) };
  }

  revalidatePath(`/assignments/${assignmentId}`);
  return { ok: true };
}
