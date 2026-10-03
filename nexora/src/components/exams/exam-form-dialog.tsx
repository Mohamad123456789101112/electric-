"use client";

import { useTransition } from "react";
import { useForm, type Resolver } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Plus } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { examSchema, type ExamFormValues } from "@/lib/validations/academics";
import { createExamAction } from "@/app/(app)/exams/actions";

export function ExamFormDialog({
  classes,
  open,
  onOpenChange,
}: {
  classes: Array<{ id: string; name: string; subject: string }>;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [isPending, startTransition] = useTransition();

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors },
  } = useForm<ExamFormValues>({
    resolver: zodResolver(examSchema) as unknown as Resolver<ExamFormValues>,
    defaultValues: { totalScore: 100 },
  });

  const onSubmit = (values: ExamFormValues) => {
    const formData = new FormData();
    formData.set("classId", values.classId);
    formData.set("title", values.title);
    formData.set("date", values.date);
    formData.set("totalScore", String(values.totalScore));

    startTransition(async () => {
      const result = await createExamAction(formData);
      if (!result.ok) {
        toast.error(result.error);
        return;
      }
      toast.success("تم إنشاء الاختبار بنجاح");
      reset();
      onOpenChange(false);
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>اختبار جديد</DialogTitle>
          <DialogDescription>أنشئ اختباراً وحدد الفصل والتاريخ.</DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <div>
            <Label htmlFor="classId">الفصل *</Label>
            <Select value={watch("classId")} onValueChange={(v) => setValue("classId", v)}>
              <SelectTrigger id="classId">
                <SelectValue placeholder="اختر فصلاً" />
              </SelectTrigger>
              <SelectContent>
                {classes.map((c) => (
                  <SelectItem key={c.id} value={c.id}>
                    {c.name} — {c.subject}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {errors.classId && <p className="mt-1 text-xs text-danger">{errors.classId.message}</p>}
          </div>

          <div>
            <Label htmlFor="title">عنوان الاختبار *</Label>
            <Input id="title" aria-invalid={!!errors.title} {...register("title")} />
            {errors.title && <p className="mt-1 text-xs text-danger">{errors.title.message}</p>}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="date">التاريخ *</Label>
              <Input id="date" type="date" aria-invalid={!!errors.date} {...register("date")} />
              {errors.date && <p className="mt-1 text-xs text-danger">{errors.date.message}</p>}
            </div>
            <div>
              <Label htmlFor="totalScore">الدرجة الكلية</Label>
              <Input id="totalScore" type="number" min={1} {...register("totalScore")} />
            </div>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              إلغاء
            </Button>
            <Button type="submit" variant="accent" loading={isPending}>
              <Plus className="h-4 w-4" />
              إنشاء الاختبار
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
