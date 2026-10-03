import { z } from "zod";

export const studentSchema = z.object({
  fullName: z.string().trim().min(2, "اسم الطالب مطلوب").max(150),
  studentCode: z
    .string()
    .trim()
    .min(2, "كود الطالب مطلوب")
    .max(30)
    .regex(/^[A-Za-z0-9-_]+$/, "يسمح بالحروف والأرقام والشرطة فقط"),
  email: z.string().trim().email("صيغة البريد غير صحيحة").optional().or(z.literal("")),
  phone: z
    .string()
    .trim()
    .regex(/^\+?[0-9\s\-()]{6,20}$/, "صيغة رقم الهاتف غير صحيحة")
    .optional()
    .or(z.literal("")),
  dateOfBirth: z.string().optional().or(z.literal("")),
  gender: z.enum(["male", "female"]).optional(),
  classId: z.string().uuid().optional().or(z.literal("")),
  guardianName: z.string().trim().max(150).optional().or(z.literal("")),
  guardianPhone: z
    .string()
    .trim()
    .regex(/^\+?[0-9\s\-()]{6,20}$/, "صيغة رقم الهاتف غير صحيحة")
    .optional()
    .or(z.literal("")),
  status: z.enum(["active", "inactive", "graduated", "archived"]),
  notes: z.string().max(2000).optional().or(z.literal("")),
});

export type StudentInput = z.infer<typeof studentSchema>;
