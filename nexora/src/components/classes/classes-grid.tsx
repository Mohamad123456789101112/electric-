"use client";

import { useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { motion } from "framer-motion";
import { GraduationCap, Users, MoreVertical, Pencil, Archive, Plus } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Avatar } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { EmptyState } from "@/components/shared/empty-state";
import { ClassFormDialog } from "./class-form-dialog";
import { archiveClassAction } from "@/app/(app)/classes/actions";
import type { ClassRow } from "@/types/database";

export function ClassesGrid({
  classes,
  teachers,
  canManage,
}: {
  classes: ClassRow[];
  teachers: Array<{ id: string; name: string }>;
  canManage: boolean;
}) {
  const [createOpen, setCreateOpen] = useState(false);
  const [editingClass, setEditingClass] = useState<ClassRow | null>(null);

  function archive(id: string) {
    toast.promise(archiveClassAction(id).then((r) => { if (!r.ok) throw new Error(r.error); }), {
      loading: "جارٍ الأرشفة...",
      success: "تم أرشفة الفصل",
      error: (e) => e.message,
    });
  }

  return (
    <div className="space-y-4">
      {canManage && (
        <div className="flex justify-end">
          <Button variant="accent" size="sm" onClick={() => setCreateOpen(true)}>
            <Plus className="h-3.5 w-3.5" />
            فصل جديد
          </Button>
        </div>
      )}

      {classes.length === 0 ? (
        <Card>
          <EmptyState icon={GraduationCap} title="لا توجد فصول بعد" description="أنشئ أول فصل دراسي لتبدأ في تنظيم الطلاب والمعلمين." />
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {classes.map((c, i) => (
            <motion.div key={c.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, delay: i * 0.04 }}>
              <Card className="group relative p-5 transition-all hover:-translate-y-0.5 hover:shadow-[var(--shadow-elevation-2)]">
                <div className="flex items-start justify-between">
                  <Link href={`/classes/${c.id}`} className="min-w-0 flex-1">
                    <h3 className="truncate font-semibold text-ink">{c.name}</h3>
                    <p className="text-xs text-ink-muted">{c.subject} · {c.academic_year}</p>
                  </Link>
                  {canManage && (
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <button className="flex h-7 w-7 items-center justify-center rounded-[var(--radius-sm)] text-ink-muted hover:bg-surface" aria-label="إجراءات">
                          <MoreVertical className="h-4 w-4" />
                        </button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onSelect={() => setEditingClass(c)}>
                          <Pencil className="h-3.5 w-3.5" />
                          تعديل
                        </DropdownMenuItem>
                        <DropdownMenuItem onSelect={() => archive(c.id)} className="text-danger focus:bg-danger-soft">
                          <Archive className="h-3.5 w-3.5" />
                          أرشفة
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  )}
                </div>

                <div className="mt-4 flex items-center justify-between">
                  <div className="flex items-center gap-1.5 text-xs text-ink-muted">
                    <Users className="h-3.5 w-3.5" />
                    {c.student_count ?? 0} طالب
                  </div>
                  {c.teacher ? (
                    <div className="flex items-center gap-1.5">
                      <Avatar name={c.teacher.full_name} size="sm" />
                      <span className="text-xs text-ink-soft">{c.teacher.full_name}</span>
                    </div>
                  ) : (
                    <span className="text-xs text-ink-muted">بدون معلم</span>
                  )}
                </div>
              </Card>
            </motion.div>
          ))}
        </div>
      )}

      <ClassFormDialog teachers={teachers} open={createOpen} onOpenChange={setCreateOpen} />
      <ClassFormDialog teachers={teachers} classItem={editingClass} open={!!editingClass} onOpenChange={(o) => !o && setEditingClass(null)} />
    </div>
  );
}
