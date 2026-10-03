import { z } from "zod";

export const classSchema = z.object({
  name: z.string().trim().min(1, "اسم الفصل مطلوب").max(120),
  subject: z.string().trim().min(1, "المادة مطلوبة").max(80),
  teacherId: z.string().uuid().optional().or(z.literal("")),
  academicYear: z
    .string()
    .trim()
    .regex(/^[0-9]{4}(-[0-9]{4})?$/, "صيغة العام الدراسي غير صحيحة، مثال 2025-2026"),
  capacity: z.coerce.number().int().positive().optional(),
});

/** Client-form-facing shape (before zod coercion) used for useForm<T> typing. */
export interface ClassFormValues {
  name: string;
  subject: string;
  teacherId?: string;
  academicYear: string;
  capacity?: number | string;
}

export const assignmentSchema = z.object({
  classId: z.string().uuid("اختر فصلاً"),
  title: z.string().trim().min(2, "عنوان الواجب مطلوب").max(200),
  description: z.string().max(5000).optional().or(z.literal("")),
  maxScore: z.coerce.number().positive().default(100),
  deadline: z.string().min(1, "الموعد النهائي مطلوب"),
});

/** Client-form-facing shape (before zod coercion) used for useForm<T> typing. */
export interface AssignmentFormValues {
  classId: string;
  title: string;
  description?: string;
  maxScore: number | string;
  deadline: string;
}

export const examSchema = z.object({
  classId: z.string().uuid("اختر فصلاً"),
  title: z.string().trim().min(2, "عنوان الاختبار مطلوب").max(200),
  date: z.string().min(1, "تاريخ الاختبار مطلوب"),
  totalScore: z.coerce.number().positive().default(100),
});

/** Client-form-facing shape (before zod coercion) used for useForm<T> typing. */
export interface ExamFormValues {
  classId: string;
  title: string;
  date: string;
  totalScore: number | string;
}

export const gradeEntrySchema = z.object({
  studentId: z.string().uuid(),
  score: z.coerce.number().min(0, "الدرجة يجب ألا تقل عن صفر"),
  feedback: z.string().max(2000).optional().or(z.literal("")),
});

export const attendanceStatusEnum = z.enum(["present", "absent", "late", "excused"]);

export type ClassInput = z.infer<typeof classSchema>;
export type AssignmentInput = z.infer<typeof assignmentSchema>;
export type ExamInput = z.infer<typeof examSchema>;
