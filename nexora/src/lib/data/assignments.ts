import "server-only";
import type { createClient } from "@/lib/supabase/server";
import type { Assignment, OrgRole } from "@/types/database";

type SupabaseServer = Awaited<ReturnType<typeof createClient>>;

export async function listAssignments(
  supabase: SupabaseServer,
  orgId: string,
  opts: { classId?: string; role: OrgRole; userId: string }
) {
  let query = supabase
    .from("assignments")
    .select("*, class:classes(id, name, subject, teacher_id)")
    .eq("organization_id", orgId)
    .is("deleted_at", null)
    .order("deadline", { ascending: false });

  if (opts.classId) query = query.eq("class_id", opts.classId);

  const { data, error } = await query;
  if (error) throw error;

  let assignments = (data ?? []) as Assignment[];

  if (opts.role === "teacher") {
    assignments = assignments.filter((a) => a.class?.teacher_id === opts.userId);
  }

  const ids = assignments.map((a) => a.id);
  if (ids.length > 0) {
    const { data: submissions } = await supabase.from("submissions").select("assignment_id, score, status").in("assignment_id", ids);
    const byAssignment = new Map<string, { count: number; scoreSum: number; scoreCount: number }>();
    (submissions ?? []).forEach((s) => {
      const entry = byAssignment.get(s.assignment_id) ?? { count: 0, scoreSum: 0, scoreCount: 0 };
      if (s.status === "submitted" || s.status === "graded" || s.status === "late") entry.count++;
      if (typeof s.score === "number") {
        entry.scoreSum += s.score;
        entry.scoreCount++;
      }
      byAssignment.set(s.assignment_id, entry);
    });
    assignments = assignments.map((a) => {
      const stats = byAssignment.get(a.id);
      return {
        ...a,
        submission_count: stats?.count ?? 0,
        average_score: stats && stats.scoreCount > 0 ? Math.round((stats.scoreSum / stats.scoreCount) * 10) / 10 : null,
      };
    });
  }

  return assignments;
}

export async function getAssignmentById(supabase: SupabaseServer, orgId: string, assignmentId: string) {
  const { data, error } = await supabase
    .from("assignments")
    .select("*, class:classes(id, name, subject, teacher_id)")
    .eq("organization_id", orgId)
    .eq("id", assignmentId)
    .maybeSingle();
  if (error) throw error;
  return data as Assignment | null;
}

export async function listSubmissionsForAssignment(supabase: SupabaseServer, assignmentId: string) {
  const { data, error } = await supabase
    .from("submissions")
    .select("*, student:students(id, full_name, student_code)")
    .eq("assignment_id", assignmentId);
  if (error) throw error;
  return data ?? [];
}

export async function getMyStudentRecordInOrg(supabase: SupabaseServer, orgId: string, userId: string) {
  const { data } = await supabase.from("students").select("id, full_name").eq("organization_id", orgId).eq("profile_id", userId).maybeSingle();
  return data;
}
