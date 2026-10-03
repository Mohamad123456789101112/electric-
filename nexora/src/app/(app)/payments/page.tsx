import type { Metadata } from "next";
import { requireActiveOrg, FINANCE_ROLES } from "@/lib/auth/session";
import { listPayments, getPaymentSummary } from "@/lib/data/payments";
import { listStudentsForSelect } from "@/lib/data/students";
import { Card } from "@/components/ui/card";
import { PaymentsFilters } from "@/components/payments/payments-filters";
import { PaymentsTable } from "@/components/payments/payments-table";
import { PaymentsToolbar } from "@/components/payments/payments-toolbar";
import { PaymentsSummary } from "@/components/payments/payments-summary";
import { Pagination } from "@/components/shared/pagination";
import type { PaymentStatus } from "@/types/database";

export const metadata: Metadata = { title: "المدفوعات" };
export const dynamic = "force-dynamic";

const PAGE_SIZE = 20;

export default async function PaymentsPage({ searchParams }: { searchParams: Promise<{ [key: string]: string | string[] | undefined }> }) {
  const sp = await searchParams;
  const { supabase, organization, membership, user } = await requireActiveOrg();
  const canManage = FINANCE_ROLES.includes(membership.role);

  const page = Math.max(1, Number(sp.page) || 1);
  const q = typeof sp.q === "string" ? sp.q : "";
  const status = (typeof sp.status === "string" ? sp.status : "all") as PaymentStatus | "all";

  // Students / parents only ever see their own payments — RLS already
  // enforces this server-side, but we scope the query explicitly too so the
  // page never even requests rows it shouldn't.
  let studentId: string | undefined;
  if (membership.role === "student") {
    const { data } = await supabase.from("students").select("id").eq("organization_id", organization.id).eq("profile_id", user.id).maybeSingle();
    studentId = data?.id;
  }

  const [{ data: payments, count }, students, summary] = await Promise.all([
    listPayments(supabase, { orgId: organization.id, page, pageSize: PAGE_SIZE, q, status, studentId }),
    canManage ? listStudentsForSelect(supabase, organization.id) : Promise.resolve([]),
    canManage ? getPaymentSummary(supabase, organization.id) : Promise.resolve(null),
  ]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-bold text-ink sm:text-2xl">المدفوعات</h1>
          <p className="mt-1 text-sm text-ink-muted">متابعة الرسوم الدراسية وحالة السداد.</p>
        </div>
        {canManage && <PaymentsToolbar students={students} />}
      </div>

      {summary && <PaymentsSummary totalCollected={summary.totalCollected} totalPending={summary.totalPending} totalOverdue={summary.totalOverdue} />}

      <Card>
        <div className="border-b border-border p-4">
          <PaymentsFilters initialQuery={q} />
        </div>
        <PaymentsTable payments={payments} students={students} canManage={canManage} />
        <Pagination page={page} pageSize={PAGE_SIZE} total={count} />
      </Card>
    </div>
  );
}
