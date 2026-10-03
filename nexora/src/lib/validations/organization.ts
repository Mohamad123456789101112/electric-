import { z } from "zod";

export const organizationTypeOptions = [
  { value: "school", label: "مدرسة" },
  { value: "academy", label: "أكاديمية تعليمية" },
  { value: "tutoring_center", label: "مركز دروس خصوصية" },
  { value: "individual_tutor", label: "معلم مستقل" },
  { value: "other", label: "أخرى" },
] as const;

export const onboardingSchema = z.object({
  name: z.string().trim().min(2, "اسم المؤسسة مطلوب").max(120),
  orgType: z.enum(["school", "academy", "tutoring_center", "individual_tutor", "other"]),
  subjects: z.array(z.string()).max(20).default([]),
  studentCountEstimate: z.coerce.number().int().min(0).max(1_000_000).optional(),
});

export type OnboardingInput = z.infer<typeof onboardingSchema>;
