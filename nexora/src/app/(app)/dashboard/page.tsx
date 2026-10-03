import { Users, CalendarCheck, TrendingUp, Wallet, GraduationCap, FileCheck2 } from "lucide-react";
import { requireActiveOrg, STAFF_ROLES, FINANCE_ROLES } from "@/lib/auth/session";
import { getStaffDashboardData, getMyLinkedStudentIds, getPersonalDashboardData } from "@/lib/data/dashboard";
import { StatCard } from "@/components/dashboard/stat-card";
import { AiInsights } from "@/components/dashboard/ai-insights";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { EmptyState } from "@/components/shared/empty-state";
import { Badge } from "@/components/ui/badge";
import { getArabicGreeting } from "@/lib/greeting";
import { formatDate, formatDateTime } from "@/lib/utils";
import Link from "next/link";

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  const { supabase, organization, membership, profile } = await requireActiveOrg();
  const firstName = (profile?.full_name || "").split(" ")[0] || "صديقنا";
  const greeting = getArabicGreeting();

  const isStaff = STAFF_ROLES.includes(membership.role) || membership.role === "accountant";

  return (
    <div className="space-y-6">
      <div className="animate-fade-in">
        <h1 className="text-2xl font-bold text-ink sm:text-[28px]">
          {greeting}، {firstName} 👋
        </h1>
        <p className="mt-1 text-sm text-ink-muted">
          إليك ملخص {organization.name} اليوم — {formatDate(new Date())}
        </p>
      </div>

      {isStaff ? <StaffDashboard orgId={organization.id} role={membership.role} supabase={supabase} /> : <PersonalDashboard userId={(await supabase.auth.getUser()).data.user!.id} supabase={supabase} />}
    </div>
  );
}

async function StaffDashboard({
  orgId,
  role,
  supabase,
}: {
  orgId: string;
  role: string;
  supabase: Awaited<ReturnType<typeof requireActiveOrg>>["supabase"];
}) {
  const { stats, insights } = await getStaffDashboardData(supabase, orgId);
  const canSeeRevenue = FINANCE_ROLES.includes(role as (typeof FINANCE_ROLES)[number]);

  return (
    <>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="الطلاب النشطون"
          value={stats.activeStudents}
          icon={Users}
          index={0}
          trend={{
            value: stats.studentTrend,
            label: stats.studentTrend === 0 ? "بدون تغيير هذا الشهر" : `${stats.studentTrend > 0 ? "+" : ""}${stats.studentTrend} هذا الشهر`,
          }}
        />
        <StatCard
          label="نسبة الحضور (30 يوم)"
          value={stats.attendanceRate}
          icon={CalendarCheck}
          format="percent"
          index={1}
          trend={{ value: stats.attendanceTrendPct, label: `${stats.attendanceTrendPct > 0 ? "+" : ""}${stats.attendanceTrendPct}٪ عن الشهر الماضي` }}
        />
        <StatCard
          label="متوسط الأداء"
          value={stats.performance}
          icon={TrendingUp}
          format="percent"
          index={2}
          trend={{ value: stats.performanceTrendPct, label: `${stats.performanceTrendPct > 0 ? "+" : ""}${stats.performanceTrendPct}٪ عن الشهر الماضي` }}
        />
        {canSeeRevenue ? (
          <StatCard
            label="الإيرادات هذا الشهر"
            value={stats.revenue.thisMonth}
            icon={Wallet}
            format="currency"
            index={3}
            trend={{ value: stats.revenue.trendPct, label: `${stats.revenue.trendPct > 0 ? "+" : ""}${stats.revenue.trendPct}٪ عن الشهر الماضي` }}
          />
        ) : (
          <StatCard label="عدد الفصول" value={stats.totalClasses} icon={GraduationCap} index={3} />
        )}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <AiInsights
            decliningStudents={insights.decliningStudents}
            missingSubmissions={insights.missingSubmissions}
            classesNeedingReview={insights.classesNeedingReview}
          />
        </div>
        <Card>
          <CardHeader>
            <CardTitle>روابط سريعة</CardTitle>
            <CardDescription>مهام شائعة لتوفير وقتك</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            <QuickLink href="/students" label="إضافة طالب جديد" />
            <QuickLink href="/attendance" label="تسجيل الحضور اليومي" />
            <QuickLink href="/assignments" label="إنشاء واجب جديد" />
            {canSeeRevenue && <QuickLink href="/payments" label="تسجيل دفعة" />}
          </CardContent>
        </Card>
      </div>
    </>
  );
}

function QuickLink({ href, label }: { href: string; label: string }) {
  return (
    <Link
      href={href}
      className="flex items-center justify-between rounded-[var(--radius-md)] border border-border px-3.5 py-3 text-sm font-medium text-ink-soft transition-colors hover:border-accent hover:bg-accent-soft hover:text-accent"
    >
      {label}
      <span aria-hidden>←</span>
    </Link>
  );
}

async function PersonalDashboard({
  userId,
  supabase,
}: {
  userId: string;
  supabase: Awaited<ReturnType<typeof requireActiveOrg>>["supabase"];
}) {
  const studentIds = await getMyLinkedStudentIds(supabase, userId);
  const { students, upcomingAssignments, recentGrades, attendanceSummary } = await getPersonalDashboardData(supabase, studentIds);

  if (students.length === 0) {
    return (
      <Card>
        <CardContent className="p-0">
          <EmptyState
            icon={GraduationCap}
            title="لا يوجد طالب مرتبط بحسابك بعد"
            description="تواصل مع إدارة المؤسسة لربط حسابك بسجل الطالب الخاص بك أو بطفلك."
          />
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard label="نسبة الحضور (30 يوم)" value={attendanceSummary ?? 0} icon={CalendarCheck} format="percent" index={0} />
        <StatCard label="الواجبات القادمة" value={upcomingAssignments.length} icon={FileCheck2} index={1} />
        <StatCard label="الطلاب المرتبطون" value={students.length} icon={Users} index={2} />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>الواجبات القادمة</CardTitle>
          </CardHeader>
          <CardContent>
            {upcomingAssignments.length === 0 ? (
              <EmptyState title="لا توجد واجبات قادمة" />
            ) : (
              <ul className="space-y-2">
                {upcomingAssignments.map((a) => (
                  <li key={a.id} className="flex items-center justify-between rounded-[var(--radius-md)] border border-border p-3 text-sm">
                    <div>
                      <p className="font-medium text-ink">{a.title}</p>
                      <p className="text-xs text-ink-muted">{(a as { class?: { name?: string } }).class?.name}</p>
                    </div>
                    <Badge variant="warning">{formatDateTime(a.deadline)}</Badge>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>آخر الدرجات</CardTitle>
          </CardHeader>
          <CardContent>
            {recentGrades.length === 0 ? (
              <EmptyState title="لا توجد درجات مسجلة بعد" />
            ) : (
              <ul className="space-y-2">
                {recentGrades.map((g) => {
                  const exam = (g as { exam?: { title?: string; total_score?: number; date?: string } }).exam;
                  return (
                    <li key={g.id} className="flex items-center justify-between rounded-[var(--radius-md)] border border-border p-3 text-sm">
                      <div>
                        <p className="font-medium text-ink">{exam?.title}</p>
                        <p className="text-xs text-ink-muted">{exam?.date && formatDate(exam.date)}</p>
                      </div>
                      <Badge variant="accent">
                        {g.score} / {exam?.total_score}
                      </Badge>
                    </li>
                  );
                })}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
