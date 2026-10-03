"use server";

import { revalidatePath } from "next/cache";
import { requireRole, FINANCE_ROLES } from "@/lib/auth/session";
import { paymentSchema } from "@/lib/validations/payments";
import { friendlyErrorMessage, logServerError } from "@/lib/errors";

export type ActionResult = { ok: true; id?: string } | { ok: false; error: string };

function parseForm(formData: FormData) {
  return paymentSchema.safeParse({
    studentId: formData.get("studentId"),
    amount: formData.get("amount"),
    currency: formData.get("currency") || "EGP",
    dueDate: formData.get("dueDate") ?? "",
    status: formData.get("status") || "pending",
    paymentMethod: formData.get("paymentMethod") || undefined,
    invoiceNumber: formData.get("invoiceNumber") ?? "",
    notes: formData.get("notes") ?? "",
  });
}

export async function createPaymentAction(formData: FormData): Promise<ActionResult> {
  const parsed = parseForm(formData);
  if (!parsed.success) return { ok: false, error: parsed.error.issues[0]?.message ?? "تحقق من البيانات" };

  const { supabase, organization, user } = await requireRole(FINANCE_ROLES);
  const v = parsed.data;

  const { data, error } = await supabase
    .from("payments")
    .insert({
      organization_id: organization.id,
      student_id: v.studentId,
      amount: v.amount,
      currency: v.currency,
      due_date: v.dueDate || null,
      status: v.status,
      paid_at: v.status === "paid" ? new Date().toISOString() : null,
      payment_method: v.paymentMethod || null,
      invoice_number: v.invoiceNumber || null,
      notes: v.notes || null,
      created_by: user.id,
    })
    .select("id")
    .single();

  if (error) {
    logServerError("payments.create", error);
    return { ok: false, error: friendlyErrorMessage(error) };
  }

  await supabase.rpc("log_audit_event", {
    p_org_id: organization.id,
    p_action: "payment.created",
    p_entity_type: "payment",
    p_entity_id: data.id,
    p_metadata: { amount: v.amount, status: v.status },
  });

  revalidatePath("/payments");
  return { ok: true, id: data.id };
}

export async function updatePaymentAction(paymentId: string, formData: FormData): Promise<ActionResult> {
  const parsed = parseForm(formData);
  if (!parsed.success) return { ok: false, error: parsed.error.issues[0]?.message ?? "تحقق من البيانات" };

  const { supabase, organization } = await requireRole(FINANCE_ROLES);
  const v = parsed.data;

  const { error } = await supabase
    .from("payments")
    .update({
      student_id: v.studentId,
      amount: v.amount,
      currency: v.currency,
      due_date: v.dueDate || null,
      status: v.status,
      paid_at: v.status === "paid" ? new Date().toISOString() : null,
      payment_method: v.paymentMethod || null,
      invoice_number: v.invoiceNumber || null,
      notes: v.notes || null,
    })
    .eq("id", paymentId)
    .eq("organization_id", organization.id);

  if (error) {
    logServerError("payments.update", error);
    return { ok: false, error: friendlyErrorMessage(error) };
  }

  revalidatePath("/payments");
  return { ok: true };
}

export async function markPaymentStatusAction(paymentId: string, status: "paid" | "pending" | "overdue" | "cancelled" | "refunded"): Promise<ActionResult> {
  const { supabase, organization, user } = await requireRole(FINANCE_ROLES);

  const { error } = await supabase
    .from("payments")
    .update({ status, paid_at: status === "paid" ? new Date().toISOString() : null })
    .eq("id", paymentId)
    .eq("organization_id", organization.id);

  if (error) {
    logServerError("payments.status", error);
    return { ok: false, error: friendlyErrorMessage(error) };
  }

  await supabase.rpc("log_audit_event", {
    p_org_id: organization.id,
    p_action: "payment.status_changed",
    p_entity_type: "payment",
    p_entity_id: paymentId,
    p_metadata: { status, changed_by: user.id },
  });

  revalidatePath("/payments");
  return { ok: true };
}

export async function deletePaymentAction(paymentId: string): Promise<ActionResult> {
  const { supabase, organization } = await requireRole(FINANCE_ROLES);

  const { error } = await supabase.from("payments").delete().eq("id", paymentId).eq("organization_id", organization.id);

  if (error) {
    logServerError("payments.delete", error);
    return { ok: false, error: friendlyErrorMessage(error) };
  }

  revalidatePath("/payments");
  return { ok: true };
}
