import type { Metadata } from "next";
import { requireActiveOrg, STAFF_ROLES } from "@/lib/auth/session";
import { listAssignments } from "@/lib/data/assignments";
import { listClassesForAttendance } from "@/lib/data/attendance";
import { AssignmentsList } from "@/components/assignments/assignments-list";

export const metadata: Metadata = { title: "الواجبات" };
export const dynamic = "force-dynamic";

export default async function AssignmentsPage({ searchParams }: { searchParams: Promise<{ classId?: string }> }) {
  const sp = await searchParams;
  const { supabase, organization, membership, user } = await requireActiveOrg();
  const canCreate = STAFF_ROLES.includes(membership.role);

  const [assignments, classes] = await Promise.all([
    listAssignments(supabase, organization.id, { classId: sp.classId, role: membership.role, userId: user.id }),
    canCreate ? listClassesForAttendance(supabase, organization.id, membership.role, user.id) : Promise.resolve([]),
  ]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-ink sm:text-2xl">الواجبات</h1>
        <p className="mt-1 text-sm text-ink-muted">متابعة الواجبات والتسليمات والدرجات.</p>
      </div>
      <AssignmentsList assignments={assignments} classes={classes} orgId={organization.id} canCreate={canCreate} />
    </div>
  );
}
