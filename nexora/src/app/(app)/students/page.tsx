import type { Metadata } from "next";
import { requireRole } from "@/lib/auth/session";
import { listStudents, listClassesForSelect } from "@/lib/data/students";
import { Card } from "@/components/ui/card";
import { StudentsFilters } from "@/components/students/students-filters";
import { StudentsTable } from "@/components/students/students-table";
import { StudentsToolbar } from "@/components/students/students-toolbar";
import { Pagination } from "@/components/shared/pagination";
import type { StudentStatus } from "@/types/database";

export const metadata: Metadata = { title: "الطلاب" };
export const dynamic = "force-dynamic";

const PAGE_SIZE = 20;

export default async function StudentsPage({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  const sp = await searchParams;
  const { supabase, organization } = await requireRole(["owner", "admin", "teacher", "accountant"]);

  const page = Math.max(1, Number(sp.page) || 1);
  const q = typeof sp.q === "string" ? sp.q : "";
  const status = (typeof sp.status === "string" ? sp.status : "all") as StudentStatus | "all";
  const classId = typeof sp.classId === "string" ? sp.classId : "all";

  const [{ data: students, count }, classes] = await Promise.all([
    listStudents(supabase, { orgId: organization.id, page, pageSize: PAGE_SIZE, q, status, classId }),
    listClassesForSelect(supabase, organization.id),
  ]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-bold text-ink sm:text-2xl">الطلاب</h1>
          <p className="mt-1 text-sm text-ink-muted">إدارة بيانات الطلاب والفصول والحالة التسجيلية.</p>
        </div>
        <StudentsToolbar classes={classes} />
      </div>

      <Card>
        <div className="border-b border-border p-4">
          <StudentsFilters initialQuery={q} classes={classes} />
        </div>
        <StudentsTable students={students} classes={classes} />
        <Pagination page={page} pageSize={PAGE_SIZE} total={count} />
      </Card>
    </div>
  );
}
