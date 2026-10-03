import type { Metadata } from "next";
import { requireRole, STAFF_ROLES } from "@/lib/auth/session";
import { listClassesForAttendance } from "@/lib/data/attendance";
import { AttendanceBoard } from "@/components/attendance/attendance-board";

export const metadata: Metadata = { title: "الحضور" };
export const dynamic = "force-dynamic";

export default async function AttendancePage({ searchParams }: { searchParams: Promise<{ classId?: string }> }) {
  const sp = await searchParams;
  const { supabase, organization, membership } = await requireRole(STAFF_ROLES);
  const classes = await listClassesForAttendance(supabase, organization.id, membership.role, membership.user_id!);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-ink sm:text-2xl">الحضور</h1>
        <p className="mt-1 text-sm text-ink-muted">تسجيل سريع للحضور اليومي حسب الفصل والتاريخ.</p>
      </div>
      <AttendanceBoard classes={classes} initialClassId={sp.classId} />
    </div>
  );
}
