"use client";

import { useState, useTransition } from "react";
import { useForm, type Resolver } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Plus, Paperclip } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { assignmentSchema, type AssignmentFormValues } from "@/lib/validations/academics";
import { createAssignmentAction, setAssignmentAttachmentAction } from "@/app/(app)/assignments/actions";
import { useSecureUpload } from "@/hooks/use-secure-upload";
import { ASSIGNMENT_FILE_CONFIG } from "@/lib/storage-config";

export function AssignmentFormDialog({
  classes,
  orgId,
  open,
  onOpenChange,
}: {
  classes: Array<{ id: string; name: string; subject: string }>;
  orgId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [isPending, startTransition] = useTransition();
  const [file, setFile] = useState<File | null>(null);
  const { upload, uploading, error: uploadError } = useSecureUpload(ASSIGNMENT_FILE_CONFIG);

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors },
  } = useForm<AssignmentFormValues>({
    resolver: zodResolver(assignmentSchema) as unknown as Resolver<AssignmentFormValues>,
    defaultValues: { maxScore: 100 },
  });

  const onSubmit = (values: AssignmentFormValues) => {
    const formData = new FormData();
    formData.set("classId", values.classId);
    formData.set("title", values.title);
    formData.set("description", values.description ?? "");
    formData.set("maxScore", String(values.maxScore));
    formData.set("deadline", values.deadline);

    startTransition(async () => {
      const result = await createAssignmentAction(formData);
      if (!result.ok) {
        toast.error(result.error);
        return;
      }

      if (file && result.id) {
        const uploaded = await upload(file, `${orgId}/${result.id}`);
        if (uploaded) {
          await setAssignmentAttachmentAction(result.id, uploaded.path, uploaded.filename, uploaded.mimeType, uploaded.size);
        }
      }

      toast.success("تم إنشاء الواجب بنجاح");
      reset();
      setFile(null);
      onOpenChange(false);
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>واجب جديد</DialogTitle>
          <DialogDescription>أنشئ واجباً وحدد الفصل والموعد النهائي.</DialogDescription>
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
            <Label htmlFor="title">عنوان الواجب *</Label>
            <Input id="title" aria-invalid={!!errors.title} {...register("title")} />
            {errors.title && <p className="mt-1 text-xs text-danger">{errors.title.message}</p>}
          </div>

          <div>
            <Label htmlFor="description">الوصف</Label>
            <Textarea id="description" rows={3} {...register("description")} />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="deadline">الموعد النهائي *</Label>
              <Input id="deadline" type="datetime-local" aria-invalid={!!errors.deadline} {...register("deadline")} />
              {errors.deadline && <p className="mt-1 text-xs text-danger">{errors.deadline.message}</p>}
            </div>
            <div>
              <Label htmlFor="maxScore">الدرجة الكاملة</Label>
              <Input id="maxScore" type="number" min={1} {...register("maxScore")} />
            </div>
          </div>

          <div>
            <Label>مرفق (اختياري)</Label>
            <label className="flex cursor-pointer items-center gap-2 rounded-[var(--radius-md)] border border-dashed border-border px-3 py-2.5 text-sm text-ink-muted transition-colors hover:border-accent">
              <Paperclip className="h-4 w-4" />
              {file ? file.name : "اختر ملفاً (PDF, Word, صورة)"}
              <input type="file" className="hidden" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
            </label>
            {uploadError && <p className="mt-1 text-xs text-danger">{uploadError}</p>}
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              إلغاء
            </Button>
            <Button type="submit" variant="accent" loading={isPending || uploading}>
              <Plus className="h-4 w-4" />
              إنشاء الواجب
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
