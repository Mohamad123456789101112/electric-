import "server-only";
import type { createClient } from "@/lib/supabase/server";
import type { Payment, PaymentStatus } from "@/types/database";

type SupabaseServer = Awaited<ReturnType<typeof createClient>>;

export interface ListPaymentsParams {
  orgId: string;
  page: number;
  pageSize: number;
  q?: string;
  status?: PaymentStatus | "all";
  studentId?: string;
}

export async function listPayments(supabase: SupabaseServer, params: ListPaymentsParams) {
  const { orgId, page, pageSize, q, status = "all", studentId } = params;

  let query = supabase
    .from("payments")
    .select("*, student:students(id, full_name, student_code)", { count: "exact" })
    .eq("organization_id", orgId);

  if (status !== "all") query = query.eq("status", status);
  if (studentId) query = query.eq("student_id", studentId);

  const from = (page - 1) * pageSize;
  const to = from + pageSize - 1;

  const { data, error, count } = await query.order("created_at", { ascending: false }).range(from, to);
  if (error) throw error;

  let payments = (data ?? []) as Payment[];

  // Free-text search on joined student fields happens client-side of the
  // query builder here since PostgREST can't filter on embedded columns with
  // `.or()` reliably — acceptable at current scale, revisit with a view/RPC
  // if payment volume grows large.
  if (q && q.trim()) {
    const term = q.trim().toLowerCase();
    payments = payments.filter(
      (p) => p.student?.full_name?.toLowerCase().includes(term) || p.student?.student_code?.toLowerCase().includes(term) || p.invoice_number?.toLowerCase().includes(term)
    );
  }

  return { data: payments, count: count ?? 0 };
}

export async function getPaymentSummary(supabase: SupabaseServer, orgId: string) {
  const { data, error } = await supabase.from("payments").select("amount, status").eq("organization_id", orgId);
  if (error) throw error;

  const rows = data ?? [];
  const totalCollected = rows.filter((r) => r.status === "paid").reduce((sum, r) => sum + Number(r.amount), 0);
  const totalPending = rows.filter((r) => r.status === "pending").reduce((sum, r) => sum + Number(r.amount), 0);
  const totalOverdue = rows.filter((r) => r.status === "overdue").reduce((sum, r) => sum + Number(r.amount), 0);

  return { totalCollected, totalPending, totalOverdue };
}
