"use client";

import { useState } from "react";
import { Pencil } from "lucide-react";
import { Avatar } from "@/components/ui/avatar";
import { SubmissionStatusBadge } from "@/components/shared/status-badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/shared/empty-state";
import { FileDownloadLink } from "@/components/shared/file-download-link";
import { GradeDialog } from "./grade-dialog";
import { formatDateTime } from "@/lib/utils";
import { Users } from "lucide-react";

export interface RosterSubmissionRow {
  studentId: string;
  studentName: string;
  studentCode: string;
  status: string;
  score: number | null;
  feedback: string | null;
  submittedAt: string | null;
  filePath: string | null;
}

export function SubmissionsManager({ assignmentId, rows, maxScore }: { assignmentId: string; rows: RosterSubmissionRow[]; maxScore: number }) {
  const [grading, setGrading] = useState<RosterSubmissionRow | null>(null);

  if (rows.length === 0) {
    return <EmptyState icon={Users} title="لا يوجد طلاب في هذا الفصل بعد" />;
  }

  return (
    <>
      <ul className="divide-y divide-border">
        {rows.map((s) => (
          <li key={s.studentId} className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-2.5">
              <Avatar name={s.studentName} size="sm" />
              <div>
                <p className="text-sm font-medium text-ink">{s.studentName}</p>
                <p className="font-mono text-xs text-ink-muted">{s.studentCode}</p>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              {s.submittedAt && <span className="text-xs text-ink-muted">{formatDateTime(s.submittedAt)}</span>}
              {s.filePath && <FileDownloadLink bucket="submission-files" path={s.filePath} label="عرض الملف" />}
              {s.score !== null && (
                <span className="text-sm font-semibold text-ink">
                  {s.score}/{maxScore}
                </span>
              )}
              <SubmissionStatusBadge status={s.status} />
              <Button variant="outline" size="sm" onClick={() => setGrading(s)}>
                <Pencil className="h-3.5 w-3.5" />
                تصحيح
              </Button>
            </div>
          </li>
        ))}
      </ul>

      {grading && (
        <GradeDialog
          assignmentId={assignmentId}
          studentId={grading.studentId}
          studentName={grading.studentName}
          maxScore={maxScore}
          currentScore={grading.score}
          currentFeedback={grading.feedback}
          open={!!grading}
          onOpenChange={(o) => !o && setGrading(null)}
        />
      )}
    </>
  );
}
