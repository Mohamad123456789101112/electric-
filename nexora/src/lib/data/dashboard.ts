import "server-only";
import type { createClient } from "@/lib/supabase/server";

type SupabaseServer = Awaited<ReturnType<typeof createClient>>;

interface OrgCountsRow {
  active_students: number;
  new_students_this_month: number;
  new_students_last_month: number;
  total_classes: number;
}

interface PaymentSummaryRow {
  total_paid: number;
  total_pending: number;
  total_overdue: number;
  revenue_this_month: number;
  revenue_last_month: number;
}

function monthStart(offsetMonths = 0) {
  const d = new Date();
  d.setDate(1);
  d.setMonth(d.getMonth() + offsetMonths);
  d.setHours(0, 0, 0, 0);
  return d;
}

function pctChange(current: number, previous: number): number {
  if (previous === 0) return current > 0 ? 100 : 0;
  return Math.round(((current - previous) / previous) * 100);
}

export async function getStaffDashboardData(supabase: SupabaseServer, orgId: string) {
  const today = new Date();
  const todayStr = today.toISOString().slice(0, 10);
  const monthAgo = new Date(today.getTime() - 30 * 86400000).toISOString().slice(0, 10);
  const prevMonthAgo = new Date(today.getTime() - 60 * 86400000).toISOString().slice(0, 10);

  const [counts, payments, attendanceNow, attendancePrev, perfNow, perfPrev, declining, missing, needsReview] = await Promise.all([
    supabase.rpc("get_org_dashboard_counts", { p_org_id: orgId }).maybeSingle() as unknown as Promise<{ data: OrgCountsRow | null }>,
    supabase.rpc("get_payment_summary", { p_org_id: orgId }).maybeSingle() as unknown as Promise<{ data: PaymentSummaryRow | null }>,
    supabase.rpc("get_attendance_rate", { p_org_id: orgId, p_from: monthAgo, p_to: todayStr }),
    supabase.rpc("get_attendance_rate", { p_org_id: orgId, p_from: prevMonthAgo, p_to: monthAgo }),
    supabase.rpc("get_performance_average", { p_org_id: orgId, p_from: monthAgo, p_to: todayStr }),
    supabase.rpc("get_performance_average", { p_org_id: orgId, p_from: prevMonthAgo, p_to: monthAgo }),
    supabase.rpc("get_declining_students", { p_org_id: orgId, p_limit: 5 }),
    supabase.rpc("get_missing_submissions", { p_org_id: orgId, p_limit: 5 }),
    supabase.rpc("get_classes_needing_review", { p_org_id: orgId, p_limit: 5 }),
  ]);

  const activeStudents = Number(counts.data?.active_students ?? 0);
  const newThisMonth = Number(counts.data?.new_students_this_month ?? 0);
  const newLastMonth = Number(counts.data?.new_students_last_month ?? 0);

  const attendanceRate = Number(attendanceNow.data ?? 0);
  const attendanceRatePrev = Number(attendancePrev.data ?? 0);

  const performance = Number(perfNow.data ?? 0);
  const performancePrev = Number(perfPrev.data ?? 0);

  const revenueThisMonth = Number(payments.data?.revenue_this_month ?? 0);
  const revenueLastMonth = Number(payments.data?.revenue_last_month ?? 0);

  return {
    stats: {
      activeStudents,
      studentTrend: newThisMonth - newLastMonth,
      totalClasses: Number(counts.data?.total_classes ?? 0),
      attendanceRate,
      attendanceTrendPct: pctChange(attendanceRate, attendanceRatePrev),
      performance,
      performanceTrendPct: pctChange(performance, performancePrev),
      revenue: {
        paid: Number(payments.data?.total_paid ?? 0),
        pending: Number(payments.data?.total_pending ?? 0),
        overdue: Number(payments.data?.total_overdue ?? 0),
        thisMonth: revenueThisMonth,
        trendPct: pctChange(revenueThisMonth, revenueLastMonth),
      },
    },
    insights: {
      decliningStudents: declining.data ?? [],
      missingSubmissions: missing.data ?? [],
      classesNeedingReview: needsReview.data ?? [],
    },
  };
}

export async function getMyLinkedStudentIds(supabase: SupabaseServer, userId: string): Promise<string[]> {
  const [own, guarded] = await Promise.all([
    supabase.from("students").select("id").eq("profile_id", userId),
    supabase.from("guardians").select("student_id").eq("parent_user_id", userId),
  ]);
  const ids = new Set<string>();
  (own.data ?? []).forEach((s) => ids.add(s.id));
  (guarded.data ?? []).forEach((g) => ids.add(g.student_id));
  return Array.from(ids);
}

export async function getPersonalDashboardData(supabase: SupabaseServer, studentIds: string[]) {
  if (studentIds.length === 0) {
    return { students: [], upcomingAssignments: [], recentGrades: [], attendanceSummary: null };
  }

  const [students, submissions, grades, attendance] = await Promise.all([
    supabase.from("students").select("id, full_name, student_code, class:classes(id, name, subject)").in("id", studentIds),
    supabase
      .from("assignments")
      .select("id, title, deadline, class:classes(name)")
      .in(
        "class_id",
        (await supabase.from("students").select("class_id").in("id", studentIds)).data?.map((s) => s.class_id).filter(Boolean) ?? []
      )
      .gt("deadline", new Date().toISOString())
      .order("deadline", { ascending: true })
      .limit(5),
    supabase
      .from("grades")
      .select("id, score, exam:exams(title, total_score, date)")
      .in("student_id", studentIds)
      .order("created_at", { ascending: false })
      .limit(5),
    supabase.from("attendance").select("status").in("student_id", studentIds).gte("date", new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 10)),
  ]);

  const attendanceRows = attendance.data ?? [];
  const presentCount = attendanceRows.filter((a) => a.status === "present").length;
  const attendanceSummary = attendanceRows.length > 0 ? Math.round((presentCount / attendanceRows.length) * 100) : null;

  return {
    students: students.data ?? [],
    upcomingAssignments: submissions.data ?? [],
    recentGrades: grades.data ?? [],
    attendanceSummary,
  };
}
