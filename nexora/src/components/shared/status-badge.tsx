import { Badge } from "@/components/ui/badge";

const STUDENT_STATUS: Record<string, { label: string; variant: "success" | "neutral" | "info" | "danger" }> = {
  active: { label: "نشط", variant: "success" },
  inactive: { label: "غير نشط", variant: "neutral" },
  graduated: { label: "متخرج", variant: "info" },
  archived: { label: "مؤرشف", variant: "danger" },
};

const PAYMENT_STATUS: Record<string, { label: string; variant: "success" | "warning" | "danger" | "neutral" }> = {
  paid: { label: "مدفوع", variant: "success" },
  pending: { label: "معلّق", variant: "warning" },
  overdue: { label: "متأخر", variant: "danger" },
  cancelled: { label: "ملغي", variant: "neutral" },
  refunded: { label: "مسترد", variant: "neutral" },
};

const ATTENDANCE_STATUS: Record<string, { label: string; variant: "success" | "danger" | "warning" | "info" }> = {
  present: { label: "حاضر", variant: "success" },
  absent: { label: "غائب", variant: "danger" },
  late: { label: "متأخر", variant: "warning" },
  excused: { label: "بعذر", variant: "info" },
};

const SUBMISSION_STATUS: Record<string, { label: string; variant: "success" | "warning" | "danger" | "neutral" | "info" }> = {
  not_submitted: { label: "لم يسلَّم", variant: "neutral" },
  submitted: { label: "تم التسليم", variant: "info" },
  late: { label: "تسليم متأخر", variant: "warning" },
  graded: { label: "تم التصحيح", variant: "success" },
  missing: { label: "مفقود", variant: "danger" },
};

export function StudentStatusBadge({ status }: { status: string }) {
  const s = STUDENT_STATUS[status] ?? { label: status, variant: "neutral" as const };
  return <Badge variant={s.variant}>{s.label}</Badge>;
}

export function PaymentStatusBadge({ status }: { status: string }) {
  const s = PAYMENT_STATUS[status] ?? { label: status, variant: "neutral" as const };
  return <Badge variant={s.variant}>{s.label}</Badge>;
}

export function AttendanceStatusBadge({ status }: { status: string }) {
  const s = ATTENDANCE_STATUS[status] ?? { label: status, variant: "neutral" as const };
  return <Badge variant={s.variant}>{s.label}</Badge>;
}

export function SubmissionStatusBadge({ status }: { status: string }) {
  const s = SUBMISSION_STATUS[status] ?? { label: status, variant: "neutral" as const };
  return <Badge variant={s.variant}>{s.label}</Badge>;
}
