"use client";

import { useState, useTransition } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { MoreVertical, Pencil, CheckCircle2, Trash2, Wallet } from "lucide-react";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { PaymentStatusBadge } from "@/components/shared/status-badge";
import { EmptyState } from "@/components/shared/empty-state";
import { PaymentFormDialog } from "./payment-form-dialog";
import { markPaymentStatusAction, deletePaymentAction } from "@/app/(app)/payments/actions";
import { formatCurrency, formatDate } from "@/lib/utils";
import type { Payment } from "@/types/database";

export function PaymentsTable({
  payments,
  students,
  canManage,
}: {
  payments: Payment[];
  students: Array<{ id: string; full_name: string; student_code: string }>;
  canManage: boolean;
}) {
  const [isPending, startTransition] = useTransition();
  const [editingPayment, setEditingPayment] = useState<Payment | null>(null);

  function markPaid(payment: Payment) {
    startTransition(async () => {
      const result = await markPaymentStatusAction(payment.id, "paid");
      if (!result.ok) {
        toast.error(result.error);
        return;
      }
      toast.success("تم تحديث الدفعة إلى مدفوعة");
    });
  }

  function remove(payment: Payment) {
    if (!confirm("هل تريد حذف هذه الدفعة نهائياً؟")) return;
    startTransition(async () => {
      const result = await deletePaymentAction(payment.id);
      if (!result.ok) {
        toast.error(result.error);
        return;
      }
      toast.success("تم حذف الدفعة");
    });
  }

  if (payments.length === 0) {
    return <EmptyState icon={Wallet} title="لا توجد دفعات مطابقة" description="جرّب تغيير الفلاتر أو أضف دفعة جديدة." />;
  }

  return (
    <>
      {/* Desktop table */}
      <div className="hidden overflow-x-auto md:block">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-start text-xs text-ink-muted">
              <th className="px-4 py-3 text-start font-medium">الطالب</th>
              <th className="px-4 py-3 text-start font-medium">القيمة</th>
              <th className="px-4 py-3 text-start font-medium">الاستحقاق</th>
              <th className="px-4 py-3 text-start font-medium">الحالة</th>
              <th className="px-4 py-3 text-start font-medium">الفاتورة</th>
              {canManage && <th className="px-4 py-3" />}
            </tr>
          </thead>
          <tbody>
            {payments.map((p) => (
              <tr key={p.id} className="border-b border-border last:border-0 hover:bg-surface-subtle">
                <td className="px-4 py-3">
                  {p.student ? (
                    <Link href={`/students/${p.student.id}`} className="font-medium text-ink hover:text-accent">
                      {p.student.full_name}
                    </Link>
                  ) : (
                    <span className="text-ink-muted">—</span>
                  )}
                </td>
                <td className="px-4 py-3 font-medium text-ink">{formatCurrency(p.amount, p.currency)}</td>
                <td className="px-4 py-3 text-ink-soft">{p.due_date ? formatDate(p.due_date) : "—"}</td>
                <td className="px-4 py-3">
                  <PaymentStatusBadge status={p.status} />
                </td>
                <td className="px-4 py-3 font-mono text-xs text-ink-muted">{p.invoice_number ?? "—"}</td>
                {canManage && (
                  <td className="px-4 py-3 text-end">
                    <DropdownMenu>
                      <DropdownMenuTrigger className="rounded-md p-1.5 text-ink-muted hover:bg-surface-muted hover:text-ink">
                        <MoreVertical className="h-4 w-4" />
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => setEditingPayment(p)}>
                          <Pencil className="h-3.5 w-3.5" /> تعديل
                        </DropdownMenuItem>
                        {p.status !== "paid" && (
                          <DropdownMenuItem onClick={() => markPaid(p)} disabled={isPending}>
                            <CheckCircle2 className="h-3.5 w-3.5" /> تحديد كمدفوعة
                          </DropdownMenuItem>
                        )}
                        <DropdownMenuItem onClick={() => remove(p)} disabled={isPending} className="text-danger">
                          <Trash2 className="h-3.5 w-3.5" /> حذف
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile cards */}
      <ul className="divide-y divide-border md:hidden">
        {payments.map((p) => (
          <li key={p.id} className="space-y-2 p-4">
            <div className="flex items-center justify-between">
              {p.student ? (
                <Link href={`/students/${p.student.id}`} className="font-medium text-ink">
                  {p.student.full_name}
                </Link>
              ) : (
                <span className="text-ink-muted">—</span>
              )}
              <PaymentStatusBadge status={p.status} />
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="font-semibold text-ink">{formatCurrency(p.amount, p.currency)}</span>
              <span className="text-ink-muted">{p.due_date ? formatDate(p.due_date) : "—"}</span>
            </div>
            {canManage && (
              <div className="flex gap-2 pt-1">
                <button onClick={() => setEditingPayment(p)} className="text-xs font-medium text-accent">
                  تعديل
                </button>
                {p.status !== "paid" && (
                  <button onClick={() => markPaid(p)} className="text-xs font-medium text-success">
                    تحديد كمدفوعة
                  </button>
                )}
                <button onClick={() => remove(p)} className="text-xs font-medium text-danger">
                  حذف
                </button>
              </div>
            )}
          </li>
        ))}
      </ul>

      {editingPayment && (
        <PaymentFormDialog students={students} editingPayment={editingPayment} open={!!editingPayment} onOpenChange={(o) => !o && setEditingPayment(null)} />
      )}
    </>
  );
}
