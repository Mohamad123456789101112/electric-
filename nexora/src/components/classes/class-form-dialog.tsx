"use client";

import { useEffect, useTransition } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Plus, Pencil } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { classSchema, type ClassFormValues } from "@/lib/validations/academics";
import type { Resolver } from "react-hook-form";
import { createClassAction, updateClassAction } from "@/app/(app)/classes/actions";
import type { ClassRow } from "@/types/database";

const currentYear = new Date().getFullYear();
const defaultYear = `${currentYear}-${currentYear + 1}`;

export function ClassFormDialog({
  teachers,
  classItem,
  open,
  onOpenChange,
}: {
  teachers: Array<{ id: string; name: string }>;
  classItem?: ClassRow | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [isPending, startTransition] = useTransition();
  const isEdit = !!classItem;

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors },
  } = useForm<ClassFormValues>({ resolver: zodResolver(classSchema) as unknown as Resolver<ClassFormValues>, defaultValues: { academicYear: defaultYear } });

  useEffect(() => {
    if (!open) return;
    reset(
      classItem
        ? {
            name: classItem.name,
            subject: classItem.subject,
            teacherId: classItem.teacher_id ?? "",
            academicYear: classItem.academic_year,
            capacity: classItem.capacity ?? undefined,
          }
        : { academicYear: defaultYear, name: "", subject: "", teacherId: "" }
    );
  }, [open, classItem, reset]);

  const onSubmit = (values: ClassFormValues) => {
    const formData = new FormData();
    Object.entries(values).forEach(([key, value]) => {
      if (value !== undefined && value !== null) formData.set(key, String(value));
    });

    startTransition(async () => {
      const result = isEdit ? await updateClassAction(classItem!.id, formData) : await createClassAction(formData);
      if (!result.ok) {
        toast.error(result.error);
        return;
      }
      toast.success(isEdit ? "تم تحديث الفصل" : "تم إنشاء الفصل بنجاح");
      onOpenChange(false);
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{isEdit ? "تعديل الفصل" : "فصل جديد"}</DialogTitle>
          <DialogDescription>حدد تفاصيل الفصل الدراسي والمعلم المسؤول عنه.</DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <div>
            <Label htmlFor="name">اسم الفصل *</Label>
            <Input id="name" aria-invalid={!!errors.name} {...register("name")} />
            {errors.name && <p className="mt-1 text-xs text-danger">{errors.name.message}</p>}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="subject">المادة *</Label>
              <Input id="subject" aria-invalid={!!errors.subject} {...register("subject")} />
              {errors.subject && <p className="mt-1 text-xs text-danger">{errors.subject.message}</p>}
            </div>
            <div>
              <Label htmlFor="academicYear">العام الدراسي *</Label>
              <Input id="academicYear" placeholder="2025-2026" aria-invalid={!!errors.academicYear} {...register("academicYear")} />
              {errors.academicYear && <p className="mt-1 text-xs text-danger">{errors.academicYear.message}</p>}
            </div>
          </div>

          <div>
            <Label htmlFor="teacherId">المعلم المسؤول</Label>
            <Select value={watch("teacherId") ?? ""} onValueChange={(v) => setValue("teacherId", v)}>
              <SelectTrigger id="teacherId">
                <SelectValue placeholder="بدون معلم محدد" />
              </SelectTrigger>
              <SelectContent>
                {teachers.map((t) => (
                  <SelectItem key={t.id} value={t.id}>
                    {t.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {teachers.length === 0 && <p className="mt-1 text-xs text-ink-muted">لا يوجد معلمون مضافون للمؤسسة بعد.</p>}
          </div>

          <div>
            <Label htmlFor="capacity">السعة القصوى (اختياري)</Label>
            <Input id="capacity" type="number" min={1} {...register("capacity")} />
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              إلغاء
            </Button>
            <Button type="submit" variant="accent" loading={isPending}>
              {isEdit ? <Pencil className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
              {isEdit ? "حفظ التغييرات" : "إنشاء الفصل"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
