"use client";

import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Paperclip, Send, CheckCircle2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { FileDownloadLink } from "@/components/shared/file-download-link";
import { SubmissionStatusBadge } from "@/components/shared/status-badge";
import { useSecureUpload } from "@/hooks/use-secure-upload";
import { SUBMISSION_FILE_CONFIG } from "@/lib/storage-config";
import { submitAssignmentAction } from "@/app/(app)/assignments/actions";

export function StudentSubmissionForm({
  orgId,
  assignmentId,
  studentId,
  existing,
  maxScore,
  isPastDeadline,
}: {
  orgId: string;
  assignmentId: string;
  studentId: string;
  existing: { status: string; score: number | null; feedback: string | null; filePath: string | null; content: string | null } | null;
  maxScore: number;
  isPastDeadline: boolean;
}) {
  const [content, setContent] = useState(existing?.content ?? "");
  const [file, setFile] = useState<File | null>(null);
  const [isPending, startTransition] = useTransition();
  const { upload, uploading, error: uploadError } = useSecureUpload(SUBMISSION_FILE_CONFIG);

  const alreadyGraded = existing?.status === "graded";
  const canEdit = !alreadyGraded;

  function submit() {
    startTransition(async () => {
      let filePath: string | undefined;
      if (file) {
        const uploaded = await upload(file, `${orgId}/${assignmentId}/${studentId}`);
        if (!uploaded) return;
        filePath = uploaded.path;
      }

      const result = await submitAssignmentAction({ assignmentId, studentId, filePath, content: content || undefined });
      if (!result.ok) {
        toast.error(result.error);
        return;
      }
      toast.success("تم تسليم الواجب بنجاح");
      setFile(null);
    });
  }

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle>تسليمك</CardTitle>
        {existing && <SubmissionStatusBadge status={existing.status} />}
      </CardHeader>
      <CardContent className="space-y-4">
        {alreadyGraded ? (
          <div className="flex items-start gap-3 rounded-[var(--radius-md)] bg-success-soft p-4">
            <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-success" />
            <div>
              <p className="text-sm font-medium text-ink">
                تم تصحيح واجبك: {existing?.score}/{maxScore}
              </p>
              {existing?.feedback && <p className="mt-1 text-sm text-ink-soft">{existing.feedback}</p>}
            </div>
          </div>
        ) : (
          <>
            {isPastDeadline && (
              <p className="rounded-[var(--radius-md)] bg-warning-soft px-3 py-2 text-xs text-warning">
                انتهى الموعد النهائي لهذا الواجب، لكن لا يزال بإمكانك التسليم كتسليم متأخر.
              </p>
            )}
            <Textarea
              placeholder="اكتب إجابتك هنا (اختياري إذا أرفقت ملفاً)..."
              rows={4}
              value={content}
              onChange={(e) => setContent(e.target.value)}
              disabled={!canEdit}
            />
            <label className="flex cursor-pointer items-center gap-2 rounded-[var(--radius-md)] border border-dashed border-border px-3 py-2.5 text-sm text-ink-muted transition-colors hover:border-accent">
              <Paperclip className="h-4 w-4" />
              {file ? file.name : "إرفاق ملف (اختياري)"}
              <input type="file" className="hidden" onChange={(e) => setFile(e.target.files?.[0] ?? null)} disabled={!canEdit} />
            </label>
            {uploadError && <p className="text-xs text-danger">{uploadError}</p>}
            {existing?.filePath && <FileDownloadLink bucket="submission-files" path={existing.filePath} label="عرض الملف الحالي" />}

            <Button variant="accent" onClick={submit} loading={isPending || uploading} disabled={!canEdit || (!content && !file)}>
              <Send className="h-4 w-4" />
              {existing ? "تحديث التسليم" : "تسليم الواجب"}
            </Button>
          </>
        )}
      </CardContent>
    </Card>
  );
}
