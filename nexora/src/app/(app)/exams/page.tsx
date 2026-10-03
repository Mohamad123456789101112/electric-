import type { Metadata } from "next";
import { requireActiveOrg, STAFF_ROLES } from "@/lib/auth/session";
import { listExams } from "@/lib/data/exams";
import { listClassesForAttendance } from "@/lib/data/attendance";
import { ExamsList } from "@/components/exams/exams-list";

export const metadata: Metadata = { title: "الاختبارات والدرجات" };
export const dynamic = "force-dynamic";

export default async function ExamsPage({ searchParams }: { searchParams: Promise<{ classId?: string }> }) {
  const sp = await searchParams;
  const { supabase, organization, membership, user } = await requireActiveOrg();
  const canCreate = STAFF_ROLES.includes(membership.role);

  const [exams, classes] = await Promise.all([
    listExams(supabase, organization.id, { classId: sp.classId, role: membership.role, userId: user.id }),
    canCreate ? listClassesForAttendance(supabase, organization.id, membership.role, user.id) : Promise.resolve([]),
  ]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-ink sm:text-2xl">الاختبارات والدرجات</h1>
        <p className="mt-1 text-sm text-ink-muted">إنشاء الاختبارات ورصد الدرجات ومتابعة الأداء.</p>
      </div>
      <ExamsList exams={exams} classes={classes} canCreate={canCreate} />
    </div>
  );
}
