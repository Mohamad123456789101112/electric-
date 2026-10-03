"use client";

import { useTransition } from "react";
import { useForm, type Resolver } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Plus, Save } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { paymentSchema } from "@/lib/validations/payments";
import { createPaymentAction, updatePaymentAction } from "@/app/(app)/payments/actions";
import type { Payment } from "@/types/database";

interface PaymentFormValues {
  studentId: string;
  amount: number | string;
  currency: string;
  dueDate?: string;
  status: "pending" | "paid" | "overdue" | "cancelled" | "refunded";
  paymentMethod?: "cash" | "bank_transfer" | "card" | "wallet" | "other";
  invoiceNumber?: string;
  notes?: string;
}

const STATUS_OPTIONS = [
  { value: "pending", label: "معلّق" },
  { value: "paid", label: "مدفوع" },
  { value: "overdue", label: "متأخر" },
  { value: "cancelled", label: "ملغي" },
  { value: "refunded", label: "مسترد" },
];

const METHOD_OPTIONS = [
  { value: "cash", label: "نقداً" },
  { value: "bank_transfer", label: "تحويل بنكي" },
  { value: "card", label: "بطاقة" },
  { value: "wallet", label: "محفظة إلكترونية" },
  { value: "other", label: "أخرى" },
];

export function PaymentFormDialog({
  students,
  editingPayment,
  open,
  onOpenChange,
}: {
  students: Array<{ id: string; full_name: string; student_code: string }>;
  editingPayment?: Payment | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [isPending, startTransition] = useTransition();
  const isEditing = !!editingPayment;

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    reset,
    formState: { errors },
  } = useForm<PaymentFormValues>({
    resolver: zodResolver(paymentSchema) as unknown as Resolver<PaymentFormValues>,
    defaultValues: editingPayment
      ? {
          studentId: editingPayment.student_id,
          amount: editingPayment.amount,
          currency: editingPayment.currency,
          dueDate: editingPayment.due_date ?? "",
          status: editingPayment.status,
          paymentMethod: editingPayment.payment_method ?? undefined,
          invoiceNumber: editingPayment.invoice_number ?? "",
          notes: editingPayment.notes ?? "",
        }
      : { currency: "EGP", status: "pending" },
  });

  const onSubmit = (values: PaymentFormValues) => {
    const formData = new FormData();
    formData.set("studentId", values.studentId);
    formData.set("amount", String(values.amount));
    formData.set("currency", values.currency || "EGP");
    formData.set("dueDate", values.dueDate ?? "");
    formData.set("status", values.status);
    if (values.paymentMethod) formData.set("paymentMethod", values.paymentMethod);
    formData.set("invoiceNumber", values.invoiceNumber ?? "");
    formData.set("notes", values.notes ?? "");

    startTransition(async () => {
      const result = isEditing ? await updatePaymentAction(editingPayment!.id, formData) : await createPaymentAction(formData);
      if (!result.ok) {
        toast.error(result.error);
        return;
      }
      toast.success(isEditing ? "تم تحديث الدفعة" : "تم إنشاء الدفعة بنجاح");
      reset();
      onOpenChange(false);
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{isEditing ? "تعديل الدفعة" : "دفعة جديدة"}</DialogTitle>
          <DialogDescription>سجّل دفعة مالية لأحد الطلاب وتتبّع حالتها.</DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <div>
            <Label htmlFor="studentId">الطالب *</Label>
            <Select value={watch("studentId")} onValueChange={(v) => setValue("studentId", v)}>
              <SelectTrigger id="studentId">
                <SelectValue placeholder="اختر طالباً" />
              </SelectTrigger>
              <SelectContent>
                {students.map((s) => (
                  <SelectItem key={s.id} value={s.id}>
                    {s.full_name} — {s.student_code}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {errors.studentId && <p className="mt-1 text-xs text-danger">{errors.studentId.message}</p>}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="amount">القيمة *</Label>
              <Input id="amount" type="number" step="0.01" min={0} aria-invalid={!!errors.amount} {...register("amount")} />
              {errors.amount && <p className="mt-1 text-xs text-danger">{errors.amount.message}</p>}
            </div>
            <div>
              <Label htmlFor="dueDate">تاريخ الاستحقاق</Label>
              <Input id="dueDate" type="date" {...register("dueDate")} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="status">الحالة</Label>
              <Select value={watch("status")} onValueChange={(v) => setValue("status", v as PaymentFormValues["status"])}>
                <SelectTrigger id="status">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {STATUS_OPTIONS.map((o) => (
                    <SelectItem key={o.value} value={o.value}>
                      {o.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label htmlFor="paymentMethod">طريقة الدفع</Label>
              <Select value={watch("paymentMethod")} onValueChange={(v) => setValue("paymentMethod", v as PaymentFormValues["paymentMethod"])}>
                <SelectTrigger id="paymentMethod">
                  <SelectValue placeholder="اختر" />
                </SelectTrigger>
                <SelectContent>
                  {METHOD_OPTIONS.map((o) => (
                    <SelectItem key={o.value} value={o.value}>
                      {o.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div>
            <Label htmlFor="invoiceNumber">رقم الفاتورة</Label>
            <Input id="invoiceNumber" {...register("invoiceNumber")} />
          </div>

          <div>
            <Label htmlFor="notes">ملاحظات</Label>
            <Textarea id="notes" rows={2} {...register("notes")} />
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              إلغاء
            </Button>
            <Button type="submit" variant="accent" loading={isPending}>
              {isEditing ? <Save className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
              {isEditing ? "حفظ التعديلات" : "إنشاء الدفعة"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
