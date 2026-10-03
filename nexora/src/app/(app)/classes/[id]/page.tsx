import { notFound } from "next/navigation";
import Link from "next/link";
import { ArrowRight, ClipboardList, FileSpreadsheet, CalendarCheck } from "lucide-react";
import { requireActiveOrg, ADMIN_ROLES } from "@/lib/auth/session";
import { getClassById, listClassRoster, listStudentsNotInClass } from "@/lib/data/classes";
import { RosterManager } from "@/components/classes/roster-manager";
import { Card, CardContent } from "@/components/ui/card";

export const dynamic = "force-dynamic";

export default async function ClassDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const { supabase, organization, membership } = await requireActiveOrg();
  const canManage = ADMIN_ROLES.includes(membership.role);

  const classItem = await getClassById(supabase, organization.id, id);
  if (!classItem) notFound();

  const [roster, availableStudents] = await Promise.all([
    listClassRoster(supabase, id),
    canManage ? listStudentsNotInClass(supabase, organization.id, id) : Promise.resolve([]),
  ]);

  return (
    <div className="space-y-6">
      <Link href="/classes" className="inline-flex items-center gap-1 text-sm text-ink-muted hover:text-ink">
        <ArrowRight className="h-3.5 w-3.5" />
        العودة إلى الفصول
      </Link>

      <Card>
        <CardContent className="p-5 sm:p-6">
          <h1 className="text-xl font-bold text-ink">{classItem.name}</h1>
          <p className="mt-1 text-sm text-ink-muted">
            {classItem.subject} · {classItem.academic_year} {classItem.teacher ? `· المعلم: ${classItem.teacher.full_name}` : ""}
          </p>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <QuickLink href={`/attendance?classId=${id}`} icon={CalendarCheck} label="تسجيل الحضور" />
        <QuickLink href={`/assignments?classId=${id}`} icon={ClipboardList} label="الواجبات" />
        <QuickLink href={`/exams?classId=${id}`} icon={FileSpreadsheet} label="الاختبارات والدرجات" />
      </div>

      <RosterManager classId={id} roster={roster as never} availableStudents={availableStudents} canManage={canManage} />
    </div>
  );
}

function QuickLink({ href, icon: Icon, label }: { href: string; icon: React.ComponentType<{ className?: string }>; label: string }) {
  return (
    <Link
      href={href}
      className="flex items-center gap-3 rounded-[var(--radius-lg)] border border-border bg-paper p-4 text-sm font-medium text-ink-soft transition-all hover:-translate-y-0.5 hover:border-accent hover:text-accent hover:shadow-[var(--shadow-elevation-1)]"
    >
      <Icon className="h-4 w-4" />
      {label}
    </Link>
  );
}
