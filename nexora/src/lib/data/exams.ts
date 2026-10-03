import "server-only";
import type { createClient } from "@/lib/supabase/server";
import type { OrgRole } from "@/types/database";

type SupabaseServer = Awaited<ReturnType<typeof createClient>>;

export interface ExamRow {
  id: string;
  organization_id: string;
  class_id: string;
  title: string;
  date: string;
  total_score: number;
  created_at: string;
  deleted_at: string | null;
  class?: { id: string; name: string; subject: string; teacher_id: string | null } | null;
  statistics?: { average: number | null; median: number | null; highest: number | null; lowest: number | null; graded_count: number } | null;
}

export async function listExams(supabase: SupabaseServer, orgId: string, opts: { classId?: string; role: OrgRole; userId: string }) {
  let query = supabase
    .from("exams")
    .select("*, class:classes(id, name, subject, teacher_id)")
    .eq("organization_id", orgId)
    .is("deleted_at", null)
    .order("date", { ascending: false });

  if (opts.classId) query = query.eq("class_id", opts.classId);

  const { data, error } = await query;
  if (error) throw error;

  let exams = (data ?? []) as ExamRow[];
  if (opts.role === "teacher") {
    exams = exams.filter((e) => e.class?.teacher_id === opts.userId);
  }

  const withStats = await Promise.all(
    exams.map(async (exam) => {
      const { data: statsRaw } = await supabase.rpc("get_exam_statistics", { p_exam_id: exam.id }).maybeSingle();
      const stats = statsRaw as { average: number | null; median: number | null; highest: number | null; lowest: number | null; graded_count: number } | null;
      return {
        ...exam,
        statistics: stats
          ? {
              average: stats.average,
              median: stats.median,
              highest: stats.highest,
              lowest: stats.lowest,
              graded_count: Number(stats.graded_count ?? 0),
            }
          : null,
      };
    })
  );

  return withStats;
}

export async function getExamById(supabase: SupabaseServer, orgId: string, examId: string) {
  const { data, error } = await supabase
    .from("exams")
    .select("*, class:classes(id, name, subject, teacher_id)")
    .eq("organization_id", orgId)
    .eq("id", examId)
    .maybeSingle();
  if (error) throw error;
  return data as ExamRow | null;
}

export async function listGradesForExam(supabase: SupabaseServer, examId: string) {
  const { data, error } = await supabase.from("grades").select("*, student:students(id, full_name, student_code)").eq("exam_id", examId);
  if (error) throw error;
  return data ?? [];
}
