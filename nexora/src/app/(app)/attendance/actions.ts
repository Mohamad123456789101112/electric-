"use server";

import { revalidatePath } from "next/cache";
import { requireRole, STAFF_ROLES } from "@/lib/auth/session";
import { attendanceStatusEnum } from "@/lib/validations/academics";
import { friendlyErrorMessage, logServerError } from "@/lib/errors";
import { z } from "zod";

const saveSchema = z.object({
  classId: z.string().uuid(),
  date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
  records: z.array(z.object({ studentId: z.string().uuid(), status: attendanceStatusEnum })).min(1).max(500),
});

export type ActionResult = { ok: true } | { ok: false; error: string };

export async function saveAttendanceAction(input: z.infer<typeof saveSchema>): Promise<ActionResult> {
  const parsed = saveSchema.safeParse(input);
  if (!parsed.success) return { ok: false, error: "تحقق من البيانات المدخلة" };

  const { supabase, organization, user, membership } = await requireRole(STAFF_ROLES);
  const { classId, date, records } = parsed.data;

  if (membership.role === "teacher") {
    const { data: cls } = await supabase.from("classes").select("teacher_id").eq("id", classId).maybeSingle();
    if (!cls || cls.teacher_id !== user.id) {
      return { ok: false, error: "ليست لديك صلاحية تسجيل حضور هذا الفصل" };
    }
  }

  const rows = records.map((r) => ({
    organization_id: organization.id,
    student_id: r.studentId,
    class_id: classId,
    date,
    status: r.status,
    recorded_by: user.id,
  }));

  const { error } = await supabase.from("attendance").upsert(rows, { onConflict: "student_id,class_id,date" });

  if (error) {
    logServerError("attendance.save", error);
    return { ok: false, error: friendlyErrorMessage(error) };
  }

  await supabase.rpc("log_audit_event", {
    p_org_id: organization.id,
    p_action: "attendance.recorded",
    p_entity_type: "class",
    p_entity_id: classId,
    p_metadata: { date, count: records.length },
  });

  revalidatePath("/attendance");
  return { ok: true };
}
