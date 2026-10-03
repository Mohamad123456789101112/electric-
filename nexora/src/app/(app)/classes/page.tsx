import type { Metadata } from "next";
import { requireActiveOrg, ADMIN_ROLES } from "@/lib/auth/session";
import { listClasses, listTeachersForSelect } from "@/lib/data/classes";
import { ClassesGrid } from "@/components/classes/classes-grid";

export const metadata: Metadata = { title: "الفصول" };
export const dynamic = "force-dynamic";

export default async function ClassesPage() {
  const { supabase, organization, membership } = await requireActiveOrg();
  const canManage = ADMIN_ROLES.includes(membership.role);

  const [classes, teachers] = await Promise.all([
    listClasses(supabase, organization.id),
    canManage ? listTeachersForSelect(supabase, organization.id) : Promise.resolve([]),
  ]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-ink sm:text-2xl">الفصول الدراسية</h1>
        <p className="mt-1 text-sm text-ink-muted">إدارة الفصول والمعلمين والطلاب المسجّلين في كل فصل.</p>
      </div>
      <ClassesGrid classes={classes} teachers={teachers} canManage={canManage} />
    </div>
  );
}
