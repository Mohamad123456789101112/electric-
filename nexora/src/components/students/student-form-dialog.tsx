"use client";

import { useEffect, useTransition } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Plus, Pencil } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { studentSchema, type StudentInput } from "@/lib/validations/students";
import { createStudentAction, updateStudentAction } from "@/app/(app)/students/actions";
import type { Student } from "@/types/database";

const emptyDefaults: StudentInput = {
  fullName: "",
  studentCode: "",
  email: "",
  phone: "",
  dateOfBirth: "",
  classId: "",
  guardianName: "",
  guardianPhone: "",
  status: "active",
  notes: "",
};

export function StudentFormDialog({
  classes,
  student,
  open,
  onOpenChange,
}: {
  classes: Array<{ id: string; name: string; subject: string }>;
  student?: Student | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [isPending, startTransition] = useTransition();
  const isEdit = !!student;

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors },
  } = useForm<StudentInput>({ resolver: zodResolver(studentSchema), defaultValues: emptyDefaults });

  useEffect(() => {
    if (!open) return;
    reset(
      student
        ? {
            fullName: student.full_name,
            studentCode: student.student_code,
            email: student.email ?? "",
            phone: student.phone ?? "",
            dateOfBirth: student.date_of_birth ?? "",
            gender: student.gender ?? undefined,
            classId: student.class_id ?? "",
            guardianName: student.guardian_name ?? "",
            guardianPhone: student.guardian_phone ?? "",
            status: student.status,
            notes: student.notes ?? "",
          }
        : emptyDefaults
    );
  }, [open, student, reset]);

  const onSubmit = (values: StudentInput) => {
    const formData = new FormData();
    Object.entries(values).forEach(([key, value]) => {
      if (value !== undefined && value !== null) formData.set(key, String(value));
    });

    startTransition(async () => {
      const result = isEdit ? await updateStudentAction(student!.id, formData) : await createStudentAction(formData);
      if (!result.ok) {
        toast.error(result.error);
        return;
      }
      toast.success(isEdit ? "تم تحديث بيانات الطالب" : "تمت إضافة الطالب بنجاح");
      onOpenChange(false);
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>{isEdit ? "تعديل بيانات الطالب" : "إضافة طالب جديد"}</DialogTitle>
          <DialogDescription>{isEdit ? "حدّث بيانات الطالب ثم احفظ التغييرات." : "أدخل بيانات الطالب الأساسية."}</DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="grid grid-cols-1 gap-4 sm:grid-cols-2" noValidate>
          <div className="sm:col-span-2">
            <Label htmlFor="fullName">الاسم الكامل *</Label>
            <Input id="fullName" aria-invalid={!!errors.fullName} {...register("fullName")} />
            {errors.fullName && <p className="mt-1 text-xs text-danger">{errors.fullName.message}</p>}
          </div>

          <div>
            <Label htmlFor="studentCode">كود الطالب *</Label>
            <Input id="studentCode" aria-invalid={!!errors.studentCode} {...register("studentCode")} />
            {errors.studentCode && <p className="mt-1 text-xs text-danger">{errors.studentCode.message}</p>}
          </div>

          <div>
            <Label htmlFor="status">الحالة</Label>
            <Select value={watch("status")} onValueChange={(v) => setValue("status", v as StudentInput["status"])}>
              <SelectTrigger id="status">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="active">نشط</SelectItem>
                <SelectItem value="inactive">غير نشط</SelectItem>
                <SelectItem value="graduated">متخرج</SelectItem>
                <SelectItem value="archived">مؤرشف</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div>
            <Label htmlFor="email">البريد الإلكتروني</Label>
            <Input id="email" type="email" aria-invalid={!!errors.email} {...register("email")} />
            {errors.email && <p className="mt-1 text-xs text-danger">{errors.email.message}</p>}
          </div>
          <div>
            <Label htmlFor="phone">الهاتف</Label>
            <Input id="phone" aria-invalid={!!errors.phone} {...register("phone")} />
            {errors.phone && <p className="mt-1 text-xs text-danger">{errors.phone.message}</p>}
          </div>

          <div>
            <Label htmlFor="dateOfBirth">تاريخ الميلاد</Label>
            <Input id="dateOfBirth" type="date" {...register("dateOfBirth")} />
          </div>
          <div>
            <Label htmlFor="gender">الجنس</Label>
            <Select value={watch("gender") ?? ""} onValueChange={(v) => setValue("gender", v as StudentInput["gender"])}>
              <SelectTrigger id="gender">
                <SelectValue placeholder="اختر" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="male">ذكر</SelectItem>
                <SelectItem value="female">أنثى</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="sm:col-span-2">
            <Label htmlFor="classId">الفصل</Label>
            <Select value={watch("classId") ?? ""} onValueChange={(v) => setValue("classId", v)}>
              <SelectTrigger id="classId">
                <SelectValue placeholder="بدون فصل" />
              </SelectTrigger>
              <SelectContent>
                {classes.map((c) => (
                  <SelectItem key={c.id} value={c.id}>
                    {c.name} — {c.subject}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div>
            <Label htmlFor="guardianName">اسم ولي الأمر</Label>
            <Input id="guardianName" {...register("guardianName")} />
          </div>
          <div>
            <Label htmlFor="guardianPhone">هاتف ولي الأمر</Label>
            <Input id="guardianPhone" aria-invalid={!!errors.guardianPhone} {...register("guardianPhone")} />
            {errors.guardianPhone && <p className="mt-1 text-xs text-danger">{errors.guardianPhone.message}</p>}
          </div>

          <div className="sm:col-span-2">
            <Label htmlFor="notes">ملاحظات</Label>
            <Textarea id="notes" rows={3} {...register("notes")} />
          </div>

          <DialogFooter className="sm:col-span-2">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              إلغاء
            </Button>
            <Button type="submit" variant="accent" loading={isPending}>
              {isEdit ? <Pencil className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
              {isEdit ? "حفظ التغييرات" : "إضافة الطالب"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
