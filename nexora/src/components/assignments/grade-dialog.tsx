"use client";

import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { gradeSubmissionAction } from "@/app/(app)/assignments/actions";

export function GradeDialog({
  assignmentId,
  studentId,
  studentName,
  maxScore,
  currentScore,
  currentFeedback,
  open,
  onOpenChange,
}: {
  assignmentId: string;
  studentId: string;
  studentName: string;
  maxScore: number;
  currentScore: number | null;
  currentFeedback: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [score, setScore] = useState(currentScore?.toString() ?? "");
  const [feedback, setFeedback] = useState(currentFeedback ?? "");
  const [isPending, startTransition] = useTransition();

  function save() {
    const formData = new FormData();
    formData.set("score", score);
    formData.set("feedback", feedback);
    startTransition(async () => {
      const result = await gradeSubmissionAction(assignmentId, studentId, formData);
      if (!result.ok) {
        toast.error(result.error);
        return;
      }
      toast.success("تم حفظ الدرجة");
      onOpenChange(false);
    });
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>تصحيح واجب — {studentName}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div>
            <Label htmlFor="score">الدرجة (من {maxScore})</Label>
            <Input id="score" type="number" min={0} max={maxScore} value={score} onChange={(e) => setScore(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="feedback">ملاحظات</Label>
            <Textarea id="feedback" rows={3} value={feedback} onChange={(e) => setFeedback(e.target.value)} />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            إلغاء
          </Button>
          <Button variant="accent" onClick={save} loading={isPending} disabled={!score}>
            حفظ الدرجة
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
