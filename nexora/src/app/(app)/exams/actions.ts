"use server";

import { revalidatePath } from "next/cache";
import { requireActiveOrg, requireRole, STAFF_ROLES } from "@/lib/auth/session";
import { examSchema } from "@/lib/validations/academics";
import { friendlyErrorMessage, logServerError } from "@/lib/errors";
import { z } from "zod";

export type ActionResult = { ok: true; id?: string } | { ok: false; error: string };

async function assertTeachesClass(supabase: Awaited<ReturnType<typeof requireActiveOrg>>["supabase"], role: string, userId: string, classId: string) {
  if (role === "teacher") {
    const { data } = await supabase.from("classes").select("teacher_id").eq("id", classId).maybeSingle();
    if (!data || data.teacher_id !== userId) return false;
  }
  return true;
}

export async function createExamAction(formData: FormData): Promise<ActionResult> {
  const parsed = examSchema.safeParse({
    classId: formData.get("classId"),
    title: formData.get("title"),
    date: formData.get("date"),
    totalScore: formData.get("totalScore") || 100,
  });
  if (!parsed.success) return { ok: false, error: parsed.error.issues[0]?.message ?? "تحقق من البيانات" };

  const { supabase, organization, user, membership } = await requireRole(STAFF_ROLES);
  const v = parsed.data;

  if (!(await assertTeachesClass(supabase, membership.role, user.id, v.classId))) {
    return { ok: false, error: "ليست لديك صلاحية إضافة اختبار لهذا الفصل" };
  }

  const { data, error } = await supabase
    .from("exams")
    .insert({ organization_id: organization.id, class_id: v.classId, title: v.title, date: v.date, total_score: v.totalScore, created_by: user.id })
    .select("id")
    .single();

  if (error) {
    logServerError("exams.create", error);
    return { ok: false, error: friendlyErrorMessage(error) };
  }

  await supabase.rpc("log_audit_event", {
    p_org_id: organization.id,
    p_action: "exam.created",
    p_entity_type: "exam",
    p_entity_id: data.id,
    p_metadata: { title: v.title },
  });

  revalidatePath("/exams");
  return { ok: true, id: data.id };
}

export async function archiveExamAction(examId: string): Promise<ActionResult> {
  const { supabase, organization } = await requireRole(STAFF_ROLES);

  const { error } = await supabase.from("exams").update({ deleted_at: new Date().toISOString() }).eq("id", examId).eq("organization_id", organization.id);

  if (error) {
    logServerError("exams.archive", error);
    return { ok: false, error: friendlyErrorMessage(error) };
  }

  revalidatePath("/exams");
  return { ok: true };
}

const gradeRecordSchema = z.object({
  studentId: z.string().uuid(),
  score: z.coerce.number().min(0).nullable(),
  feedback: z.string().max(2000).optional(),
});

const saveGradesSchema = z.object({
  examId: z.string().uuid(),
  records: z.array(gradeRecordSchema).max(500),
});

export async function saveGradesAction(input: z.infer<typeof saveGradesSchema>): Promise<ActionResult> {
  const parsed = saveGradesSchema.safeParse(input);
  if (!parsed.success) return { ok: false, error: "تحقق من البيانات المُدخلة" };

  const { supabase, organization, user, membership } = await requireRole(STAFF_ROLES);
  const { examId, records } = parsed.data;

  const { data: exam } = await supabase.from("exams").select("class_id, total_score").eq("id", examId).eq("organization_id", organization.id).maybeSingle();
  if (!exam) return { ok: false, error: "الاختبار غير موجود" };

  if (!(await assertTeachesClass(supabase, membership.role, user.id, exam.class_id))) {
    return { ok: false, error: "ليست لديك صلاحية على هذا الفصل" };
  }

  const withScore = records.filter((r) => r.score !== null && r.score !== undefined);
  if (withScore.some((r) => r.score! > exam.total_score)) {
    return { ok: false, error: "لا يمكن أن تتجاوز الدرجة الدرجة الكلية للاختبار" };
  }

  const rows = withScore.map((r) => ({
    organization_id: organization.id,
    exam_id: examId,
    student_id: r.studentId,
    score: r.score,
    feedback: r.feedback || null,
    graded_by: user.id,
  }));

  if (rows.length > 0) {
    const { error } = await supabase.from("grades").upsert(rows, { onConflict: "exam_id,student_id" });
    if (error) {
      logServerError("grades.save", error);
      return { ok: false, error: friendlyErrorMessage(error) };
    }
  }

  await supabase.rpc("log_audit_event", {
    p_org_id: organization.id,
    p_action: "grade.exam_graded",
    p_entity_type: "exam",
    p_entity_id: examId,
    p_metadata: { count: rows.length },
  });

  revalidatePath("/exams");
  revalidatePath(`/exams/${examId}`);
  return { ok: true };
}

