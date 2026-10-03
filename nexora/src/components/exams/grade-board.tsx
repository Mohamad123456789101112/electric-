"use client";

import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Save, Award } from "lucide-react";
import { Avatar } from "@/components/ui/avatar";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/shared/empty-state";
import { saveGradesAction } from "@/app/(app)/exams/actions";

interface RosterGrade {
  studentId: string;
  studentName: string;
  studentCode: string;
  score: number | null;
  feedback: string | null;
}

export function GradeBoard({ examId, totalScore, initialRows }: { examId: string; totalScore: number; initialRows: RosterGrade[] }) {
  const [rows, setRows] = useState(initialRows);
  const [isPending, startTransition] = useTransition();

  function updateScore(studentId: string, value: string) {
    setRows((prev) => prev.map((r) => (r.studentId === studentId ? { ...r, score: value === "" ? null : Number(value) } : r)));
  }

  function updateFeedback(studentId: string, value: string) {
    setRows((prev) => prev.map((r) => (r.studentId === studentId ? { ...r, feedback: value } : r)));
  }

  function save() {
    const invalid = rows.some((r) => r.score !== null && (r.score < 0 || r.score > totalScore));
    if (invalid) {
      toast.error(`الدرجات يجب أن تكون بين 0 و ${totalScore}`);
      return;
    }

    startTransition(async () => {
      const result = await saveGradesAction({
        examId,
        records: rows.map((r) => ({ studentId: r.studentId, score: r.score, feedback: r.feedback ?? undefined })),
      });
      if (!result.ok) {
        toast.error(result.error);
        return;
      }
      toast.success("تم حفظ الدرجات بنجاح");
    });
  }

  if (rows.length === 0) {
    return (
      <Card>
        <CardContent className="p-6">
          <EmptyState icon={Award} title="لا يوجد طلاب في هذا الفصل بعد" />
        </CardContent>
      </Card>
    );
  }

  const gradedCount = rows.filter((r) => r.score !== null).length;

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle>رصد الدرجات</CardTitle>
        <span className="text-xs text-ink-muted">
          {gradedCount} / {rows.length} تم رصدها
        </span>
      </CardHeader>
      <CardContent className="space-y-1 p-0">
        <ul className="divide-y divide-border">
          {rows.map((r) => (
            <li key={r.studentId} className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-2.5">
                <Avatar name={r.studentName} size="sm" />
                <div>
                  <p className="text-sm font-medium text-ink">{r.studentName}</p>
                  <p className="font-mono text-xs text-ink-muted">{r.studentCode}</p>
                </div>
              </div>
              <div className="flex items-center gap-2 sm:w-96">
                <Input
                  type="number"
                  min={0}
                  max={totalScore}
                  placeholder={`من ${totalScore}`}
                  value={r.score ?? ""}
                  onChange={(e) => updateScore(r.studentId, e.target.value)}
                  className="w-24"
                />
                <Input
                  placeholder="ملاحظات (اختياري)"
                  value={r.feedback ?? ""}
                  onChange={(e) => updateFeedback(r.studentId, e.target.value)}
                  className="flex-1"
                />
              </div>
            </li>
          ))}
        </ul>
        <div className="flex justify-end border-t border-border p-4">
          <Button variant="accent" onClick={save} loading={isPending}>
            <Save className="h-4 w-4" />
            حفظ الدرجات
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
