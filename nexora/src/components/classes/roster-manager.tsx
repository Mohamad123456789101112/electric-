"use client";

import { useState, useTransition } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { UserMinus, UserPlus } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Avatar } from "@/components/ui/avatar";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { EmptyState } from "@/components/shared/empty-state";
import { addStudentToClassAction, removeStudentFromClassAction } from "@/app/(app)/classes/actions";
import { Users } from "lucide-react";

interface RosterEntry {
  id: string;
  student: { id: string; full_name: string; student_code: string; status: string } | null;
}

export function RosterManager({
  classId,
  roster,
  availableStudents,
  canManage,
}: {
  classId: string;
  roster: RosterEntry[];
  availableStudents: Array<{ id: string; full_name: string; student_code: string }>;
  canManage: boolean;
}) {
  const [selected, setSelected] = useState<string>("");
  const [isPending, startTransition] = useTransition();

  function addStudent() {
    if (!selected) return;
    startTransition(async () => {
      const result = await addStudentToClassAction(classId, selected);
      if (!result.ok) {
        toast.error(result.error);
        return;
      }
      toast.success("تمت إضافة الطالب إلى الفصل");
      setSelected("");
    });
  }

  function removeStudent(memberId: string) {
    startTransition(async () => {
      const result = await removeStudentFromClassAction(classId, memberId);
      if (!result.ok) {
        toast.error(result.error);
        return;
      }
      toast.success("تمت إزالة الطالب من الفصل");
    });
  }

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle>طلاب الفصل ({roster.length})</CardTitle>
      </CardHeader>
      <CardContent>
        {canManage && (
          <div className="mb-4 flex gap-2">
            <Select value={selected} onValueChange={setSelected}>
              <SelectTrigger className="flex-1">
                <SelectValue placeholder="اختر طالباً لإضافته" />
              </SelectTrigger>
              <SelectContent>
                {availableStudents.length === 0 ? (
                  <div className="px-3 py-2 text-xs text-ink-muted">لا يوجد طلاب متاحون للإضافة</div>
                ) : (
                  availableStudents.map((s) => (
                    <SelectItem key={s.id} value={s.id}>
                      {s.full_name} ({s.student_code})
                    </SelectItem>
                  ))
                )}
              </SelectContent>
            </Select>
            <Button variant="accent" onClick={addStudent} disabled={!selected || isPending}>
              <UserPlus className="h-4 w-4" />
              إضافة
            </Button>
          </div>
        )}

        {roster.length === 0 ? (
          <EmptyState icon={Users} title="لا يوجد طلاب في هذا الفصل بعد" />
        ) : (
          <ul className="divide-y divide-border">
            {roster.map((r) =>
              r.student ? (
                <li key={r.id} className="flex items-center justify-between py-2.5">
                  <Link href={`/students/${r.student.id}`} className="flex items-center gap-2.5">
                    <Avatar name={r.student.full_name} size="sm" />
                    <div>
                      <p className="text-sm font-medium text-ink">{r.student.full_name}</p>
                      <p className="font-mono text-xs text-ink-muted">{r.student.student_code}</p>
                    </div>
                  </Link>
                  {canManage && (
                    <Button variant="ghost" size="sm" onClick={() => removeStudent(r.id)} disabled={isPending} aria-label="إزالة الطالب">
                      <UserMinus className="h-3.5 w-3.5 text-danger" />
                    </Button>
                  )}
                </li>
              ) : null
            )}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
