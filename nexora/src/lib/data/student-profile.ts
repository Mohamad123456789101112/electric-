import "server-only";
import type { createClient } from "@/lib/supabase/server";

type SupabaseServer = Awaited<ReturnType<typeof createClient>>;

export async function getStudentProfileBundle(supabase: SupabaseServer, orgId: string, studentId: string) {
  const [attendanceRes, gradesRes, submissionsRes, paymentsRes] = await Promise.all([
    supabase
      .from("attendance")
      .select("id, date, status")
      .eq("organization_id", orgId)
      .eq("student_id", studentId)
      .order("date", { ascending: false })
      .limit(60),
    supabase
      .from("grades")
      .select("id, score, feedback, created_at, exam:exams(id, title, date, total_score)")
      .eq("organization_id", orgId)
      .eq("student_id", studentId)
      .order("created_at", { ascending: false })
      .limit(30),
    supabase
      .from("submissions")
      .select("id, status, score, submitted_at, assignment:assignments(id, title, deadline, max_score)")
      .eq("organization_id", orgId)
      .eq("student_id", studentId)
      .order("created_at", { ascending: false })
      .limit(30),
    supabase
      .from("payments")
      .select("id, amount, currency, status, due_date, paid_at, payment_method")
      .eq("organization_id", orgId)
      .eq("student_id", studentId)
      .order("created_at", { ascending: false })
      .limit(30),
  ]);

  const attendance = attendanceRes.data ?? [];
  const grades = (gradesRes.data ?? []).map((g) => ({
    ...g,
    exam: Array.isArray(g.exam) ? g.exam[0] ?? null : g.exam,
  })) as Array<{ id: string; score: number; feedback: string | null; created_at: string; exam: { id: string; title: string; date: string; total_score: number } | null }>;
  const submissions = (submissionsRes.data ?? []).map((s) => ({
    ...s,
    assignment: Array.isArray(s.assignment) ? s.assignment[0] ?? null : s.assignment,
  })) as Array<{
    id: string;
    status: string;
    score: number | null;
    submitted_at: string | null;
    assignment: { id: string; title: string; deadline: string; max_score: number } | null;
  }>;
  const payments = paymentsRes.data ?? [];

  const presentCount = attendance.filter((a) => a.status === "present").length;
  const attendanceRate = attendance.length > 0 ? Math.round((presentCount / attendance.length) * 100) : null;

  const gradedSubmissions = submissions.filter((s) => s.status === "graded" || s.status === "submitted" || s.status === "late");
  const homeworkCompletionRate = submissions.length > 0 ? Math.round((gradedSubmissions.length / submissions.length) * 100) : null;

  return { attendance, grades, submissions, payments, attendanceRate, homeworkCompletionRate };
}
