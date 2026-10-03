import { z } from "zod";

export const paymentSchema = z.object({
  studentId: z.string().uuid("اختر طالباً"),
  amount: z.coerce.number().positive("القيمة يجب أن تكون أكبر من صفر"),
  currency: z.string().length(3).default("EGP"),
  dueDate: z.string().optional().or(z.literal("")),
  status: z.enum(["pending", "paid", "overdue", "cancelled", "refunded"]).default("pending"),
  paymentMethod: z.enum(["cash", "bank_transfer", "card", "wallet", "other"]).optional(),
  invoiceNumber: z.string().max(60).optional().or(z.literal("")),
  notes: z.string().max(2000).optional().or(z.literal("")),
});

export type PaymentInput = z.infer<typeof paymentSchema>;
