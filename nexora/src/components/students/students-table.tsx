"use client";

import { useState, useTransition } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { MoreVertical, Pencil, Archive, RotateCcw, Eye, Users } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar } from "@/components/ui/avatar";
import { StudentStatusBadge } from "@/components/shared/status-badge";
import { EmptyState } from "@/components/shared/empty-state";
import { StudentFormDialog } from "./student-form-dialog";
import { setStudentStatusAction } from "@/app/(app)/students/actions";
import { formatDate } from "@/lib/utils";
import type { Student } from "@/types/database";

export function StudentsTable({
  students,
  classes,
}: {
  students: Student[];
  classes: Array<{ id: string; name: string; subject: string }>;
}) {
  const [isPending, startTransition] = useTransition();
  const [editingStudent, setEditingStudent] = useState<Student | null>(null);

  function toggleArchive(student: Student) {
    const nextStatus = student.status === "archived" ? "active" : "archived";
    startTransition(async () => {
      const result = await setStudentStatusAction(student.id, nextStatus);
      if (!result.ok) {
        toast.error(result.error);
        return;
      }
      toast.success(nextStatus === "archived" ? "تم أرشفة الطالب" : "تمت إعادة تفعيل الطالب");
    });
  }

  if (students.length === 0) {
    return (
      <EmptyState
        icon={Users}
        title="لا يوجد طلاب مطابقون"
        description="جرّب تغيير معايير البحث أو الفلاتر، أو أضف طالباً جديداً."
      />
    );
  }

  return (
    <>
      {/* Desktop table */}
      <div className="hidden overflow-x-auto md:block">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-start text-xs text-ink-muted">
              <th className="px-4 py-3 text-start font-medium">الطالب</th>
              <th className="px-4 py-3 text-start font-medium">الكود</th>
              <th className="px-4 py-3 text-start font-medium">الفصل</th>
              <th className="px-4 py-3 text-start font-medium">الحالة</th>
              <th className="px-4 py-3 text-start font-medium">تاريخ الإضافة</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody>
            {students.map((s) => (
              <tr key={s.id} className="border-b border-border last:border-0 transition-colors hover:bg-surface">
                <td className="px-4 py-3">
                  <Link href={`/students/${s.id}`} className="flex items-center gap-2.5">
                    <Avatar name={s.full_name} size="sm" />
                    <div className="min-w-0">
                      <p className="truncate font-medium text-ink">{s.full_name}</p>
                      {s.email && <p className="truncate text-xs text-ink-muted">{s.email}</p>}
                    </div>
                  </Link>
                </td>
                <td className="px-4 py-3 font-mono text-xs text-ink-soft">{s.student_code}</td>
                <td className="px-4 py-3 text-ink-soft">{s.class?.name ?? "—"}</td>
                <td className="px-4 py-3">
                  <StudentStatusBadge status={s.status} />
                </td>
                <td className="px-4 py-3 text-ink-muted">{formatDate(s.created_at)}</td>
                <td className="px-4 py-3">
                  <RowActions student={s} onEdit={() => setEditingStudent(s)} onToggleArchive={toggleArchive} disabled={isPending} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile cards */}
      <ul className="divide-y divide-border md:hidden">
        {students.map((s) => (
          <li key={s.id} className="flex items-center gap-3 p-4">
            <Link href={`/students/${s.id}`} className="flex flex-1 items-center gap-3 min-w-0">
              <Avatar name={s.full_name} />
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium text-ink">{s.full_name}</p>
                <p className="truncate text-xs text-ink-muted">
                  {s.student_code} {s.class?.name ? `· ${s.class.name}` : ""}
                </p>
              </div>
            </Link>
            <StudentStatusBadge status={s.status} />
            <RowActions student={s} onEdit={() => setEditingStudent(s)} onToggleArchive={toggleArchive} disabled={isPending} />
          </li>
        ))}
      </ul>

      <StudentFormDialog
        classes={classes}
        student={editingStudent}
        open={!!editingStudent}
        onOpenChange={(open) => !open && setEditingStudent(null)}
      />
    </>
  );
}

function RowActions({
  student,
  onEdit,
  onToggleArchive,
  disabled,
}: {
  student: Student;
  onEdit: () => void;
  onToggleArchive: (s: Student) => void;
  disabled: boolean;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          className="flex h-8 w-8 items-center justify-center rounded-[var(--radius-sm)] text-ink-muted transition-colors hover:bg-surface-strong"
          aria-label="إجراءات"
          disabled={disabled}
        >
          <MoreVertical className="h-4 w-4" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem asChild>
          <Link href={`/students/${student.id}`}>
            <Eye className="h-3.5 w-3.5" />
            عرض الملف
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={onEdit}>
          <Pencil className="h-3.5 w-3.5" />
          تعديل
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => onToggleArchive(student)} className={student.status === "archived" ? "" : "text-danger focus:bg-danger-soft"}>
          {student.status === "archived" ? <RotateCcw className="h-3.5 w-3.5" /> : <Archive className="h-3.5 w-3.5" />}
          {student.status === "archived" ? "إعادة تفعيل" : "أرشفة"}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
