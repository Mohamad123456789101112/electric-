import { notFound } from "next/navigation";
import Link from "next/link";
import { ArrowRight, Sparkles, Mail, Phone, Calendar, GraduationCap } from "lucide-react";
import { requireRole } from "@/lib/auth/session";
import { getStudentById } from "@/lib/data/students";
import { getStudentProfileBundle } from "@/lib/data/student-profile";
import { buildStudentInsights } from "@/lib/data/student-insights";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Avatar } from "@/components/ui/avatar";
import { StudentStatusBadge, PaymentStatusBadge, AttendanceStatusBadge, SubmissionStatusBadge } from "@/components/shared/status-badge";
import { EmptyState } from "@/components/shared/empty-state";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PerformanceTrendChart, AttendanceTrendChart, HomeworkCompletionChart } from "@/components/students/student-charts";
import { formatCurrency, formatDate, formatDateTime } from "@/lib/utils";

export const dynamic = "force-dynamic";

export default async function StudentProfilePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const { supabase, organization, membership } = await requireRole(["owner", "admin", "teacher", "accountant"]);
  const canSeePayments = (["owner", "admin", "accountant"] as const).includes(membership.role as "owner" | "admin" | "accountant");

  const student = await getStudentById(supabase, organization.id, id);
  if (!student) notFound();

  const bundle = await getStudentProfileBundle(supabase, organization.id, id);
  const insights = buildStudentInsights(bundle);

  return (
    <div className="space-y-6">
      <Link href="/students" className="inline-flex items-center gap-1 text-sm text-ink-muted hover:text-ink">
        <ArrowRight className="h-3.5 w-3.5" />
        العودة إلى الطلاب
      </Link>

      <Card>
        <CardContent className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between sm:p-6">
          <div className="flex items-center gap-4">
            <Avatar name={student.full_name} size="lg" />
            <div>
              <h1 className="text-xl font-bold text-ink">{student.full_name}</h1>
              <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-ink-muted">
                <span className="font-mono text-xs">{student.student_code}</span>
                {student.class && (
                  <span className="flex items-center gap-1">
                    <GraduationCap className="h-3.5 w-3.5" /> {student.class.name}
                  </span>
                )}
                {student.email && (
                  <span className="flex items-center gap-1">
                    <Mail className="h-3.5 w-3.5" /> {student.email}
                  </span>
                )}
                {student.phone && (
                  <span className="flex items-center gap-1">
                    <Phone className="h-3.5 w-3.5" /> {student.phone}
                  </span>
                )}
                {student.date_of_birth && (
                  <span className="flex items-center gap-1">
                    <Calendar className="h-3.5 w-3.5" /> {formatDate(student.date_of_birth)}
                  </span>
                )}
              </div>
            </div>
          </div>
          <StudentStatusBadge status={student.status} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-accent" />
            تحليل الأداء
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="space-y-2">
            {insights.map((insight, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-ink-soft">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                {insight}
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <PerformanceTrendChart grades={bundle.grades} />
        <AttendanceTrendChart attendance={bundle.attendance} />
        <HomeworkCompletionChart submissions={bundle.submissions} />
      </div>

      <Tabs defaultValue="attendance">
        <TabsList>
          <TabsTrigger value="attendance">الحضور</TabsTrigger>
          <TabsTrigger value="assignments">الواجبات</TabsTrigger>
          <TabsTrigger value="exams">الاختبارات</TabsTrigger>
          {canSeePayments && <TabsTrigger value="payments">المدفوعات</TabsTrigger>}
        </TabsList>

        <TabsContent value="attendance">
          <Card>
            <CardContent className="p-0">
              {bundle.attendance.length === 0 ? (
                <EmptyState title="لا يوجد سجل حضور بعد" />
              ) : (
                <ul className="divide-y divide-border">
                  {bundle.attendance.map((a) => (
                    <li key={a.id} className="flex items-center justify-between px-5 py-3 text-sm">
                      <span className="text-ink-soft">{formatDate(a.date)}</span>
                      <AttendanceStatusBadge status={a.status} />
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="assignments">
          <Card>
            <CardContent className="p-0">
              {bundle.submissions.length === 0 ? (
                <EmptyState title="لا توجد واجبات مسندة بعد" />
              ) : (
                <ul className="divide-y divide-border">
                  {bundle.submissions.map((s) => {
                    const assignment = s.assignment;
                    return (
                      <li key={s.id} className="flex items-center justify-between px-5 py-3 text-sm">
                        <div>
                          <p className="font-medium text-ink">{assignment?.title ?? "—"}</p>
                          <p className="text-xs text-ink-muted">{assignment?.deadline && formatDateTime(assignment.deadline)}</p>
                        </div>
                        <div className="flex items-center gap-2">
                          {s.score !== null && (
                            <span className="text-xs text-ink-muted">
                              {s.score}/{assignment?.max_score}
                            </span>
                          )}
                          <SubmissionStatusBadge status={s.status} />
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="exams">
          <Card>
            <CardContent className="p-0">
              {bundle.grades.length === 0 ? (
                <EmptyState title="لا توجد درجات مسجلة بعد" />
              ) : (
                <ul className="divide-y divide-border">
                  {bundle.grades.map((g) => {
                    const exam = g.exam;
                    return (
                      <li key={g.id} className="flex items-center justify-between px-5 py-3 text-sm">
                        <div>
                          <p className="font-medium text-ink">{exam?.title ?? "—"}</p>
                          <p className="text-xs text-ink-muted">{exam?.date && formatDate(exam.date)}</p>
                        </div>
                        <span className="font-semibold text-ink">
                          {g.score}/{exam?.total_score}
                        </span>
                      </li>
                    );
                  })}
                </ul>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {canSeePayments && (
          <TabsContent value="payments">
            <Card>
              <CardContent className="p-0">
                {bundle.payments.length === 0 ? (
                  <EmptyState title="لا توجد مدفوعات مسجلة بعد" />
                ) : (
                  <ul className="divide-y divide-border">
                    {bundle.payments.map((p) => (
                      <li key={p.id} className="flex items-center justify-between px-5 py-3 text-sm">
                        <div>
                          <p className="font-medium text-ink">{formatCurrency(p.amount, p.currency)}</p>
                          <p className="text-xs text-ink-muted">{p.due_date && `يستحق في ${formatDate(p.due_date)}`}</p>
                        </div>
                        <PaymentStatusBadge status={p.status} />
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        )}
      </Tabs>
    </div>
  );
}
