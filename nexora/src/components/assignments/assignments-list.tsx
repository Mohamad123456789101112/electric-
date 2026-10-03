"use client";

import { useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { ClipboardList, Plus, Users, TrendingUp } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/shared/empty-state";
import { AssignmentFormDialog } from "./assignment-form-dialog";
import { formatDateTime } from "@/lib/utils";
import type { Assignment } from "@/types/database";

export function AssignmentsList({
  assignments,
  classes,
  orgId,
  canCreate,
}: {
  assignments: Assignment[];
  classes: Array<{ id: string; name: string; subject: string }>;
  orgId: string;
  canCreate: boolean;
}) {
  const [createOpen, setCreateOpen] = useState(false);

  return (
    <div className="space-y-4">
      {canCreate && (
        <div className="flex justify-end">
          <Button variant="accent" size="sm" onClick={() => setCreateOpen(true)} disabled={classes.length === 0}>
            <Plus className="h-3.5 w-3.5" />
            واجب جديد
          </Button>
        </div>
      )}

      {assignments.length === 0 ? (
        <Card>
          <EmptyState icon={ClipboardList} title="لا توجد واجبات بعد" description="أنشئ أول واجب لمتابعة تسليمات الطلاب وتقييمهم." />
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {assignments.map((a, i) => {
            const overdue = new Date(a.deadline).getTime() < Date.now();
            return (
              <motion.div key={a.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, delay: i * 0.04 }}>
                <Link href={`/assignments/${a.id}`}>
                  <Card className="p-5 transition-all hover:-translate-y-0.5 hover:shadow-[var(--shadow-elevation-2)]">
                    <div className="flex items-start justify-between gap-2">
                      <h3 className="font-semibold text-ink">{a.title}</h3>
                      <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium ${overdue ? "bg-danger-soft text-danger" : "bg-info-soft text-info"}`}>
                        {overdue ? "منتهي" : "نشط"}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-ink-muted">{a.class?.name}</p>
                    <p className="mt-3 text-xs text-ink-muted">موعد التسليم: {formatDateTime(a.deadline)}</p>
                    <div className="mt-4 flex items-center justify-between text-xs text-ink-soft">
                      <span className="flex items-center gap-1">
                        <Users className="h-3.5 w-3.5" />
                        {a.submission_count ?? 0} تسليم
                      </span>
                      {a.average_score !== null && a.average_score !== undefined && (
                        <span className="flex items-center gap-1">
                          <TrendingUp className="h-3.5 w-3.5" />
                          متوسط {a.average_score}
                        </span>
                      )}
                    </div>
                  </Card>
                </Link>
              </motion.div>
            );
          })}
        </div>
      )}

      <AssignmentFormDialog classes={classes} orgId={orgId} open={createOpen} onOpenChange={setCreateOpen} />
    </div>
  );
}
