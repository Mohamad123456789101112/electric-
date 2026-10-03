import { z } from "zod";

export const emailSchema = z
  .string()
  .trim()
  .min(1, "البريد الإلكتروني مطلوب")
  .email("صيغة البريد الإلكتروني غير صحيحة");

export const passwordSchema = z
  .string()
  .min(8, "يجب ألا تقل كلمة المرور عن 8 أحرف")
  .regex(/[A-Za-z]/, "يجب أن تحتوي كلمة المرور على حرف واحد على الأقل")
  .regex(/[0-9]/, "يجب أن تحتوي كلمة المرور على رقم واحد على الأقل");

export const loginSchema = z.object({
  email: emailSchema,
  password: z.string().min(1, "كلمة المرور مطلوبة"),
});

export const registerSchema = z
  .object({
    fullName: z.string().trim().min(2, "الاسم الكامل مطلوب").max(150),
    email: emailSchema,
    password: passwordSchema,
    confirmPassword: z.string(),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: "كلمتا المرور غير متطابقتين",
    path: ["confirmPassword"],
  });

export const forgotPasswordSchema = z.object({ email: emailSchema });

export const resetPasswordSchema = z
  .object({
    password: passwordSchema,
    confirmPassword: z.string(),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: "كلمتا المرور غير متطابقتين",
    path: ["confirmPassword"],
  });

export type LoginInput = z.infer<typeof loginSchema>;
export type RegisterInput = z.infer<typeof registerSchema>;
