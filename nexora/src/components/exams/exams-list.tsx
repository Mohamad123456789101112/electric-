"use client";

import { useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { FileSpreadsheet, Plus, BarChart3 } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/shared/empty-state";
import { ExamFormDialog } from "./exam-form-dialog";
import { formatDate } from "@/lib/utils";
import type { ExamRow } from "@/lib/data/exams";

export function ExamsList({
  exams,
  classes,
  canCreate,
}: {
  exams: ExamRow[];
  classes: Array<{ id: string; name: string; subject: string }>;
  canCreate: boolean;
}) {
  const [createOpen, setCreateOpen] = useState(false);

  return (
    <div className="space-y-4">
      {canCreate && (
        <div className="flex justify-end">
          <Button variant="accent" size="sm" onClick={() => setCreateOpen(true)} disabled={classes.length === 0}>
            <Plus className="h-3.5 w-3.5" />
            اختبار جديد
          </Button>
        </div>
      )}

      {exams.length === 0 ? (
        <Card>
          <EmptyState icon={FileSpreadsheet} title="لا توجد اختبارات بعد" description="أنشئ أول اختبار لتسجيل الدرجات ومتابعة الأداء." />
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {exams.map((e, i) => (
            <motion.div key={e.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, delay: i * 0.04 }}>
              <Link href={`/exams/${e.id}`}>
                <Card className="p-5 transition-all hover:-translate-y-0.5 hover:shadow-[var(--shadow-elevation-2)]">
                  <h3 className="font-semibold text-ink">{e.title}</h3>
                  <p className="mt-1 text-xs text-ink-muted">
                    {e.class?.name} · {formatDate(e.date)}
                  </p>
                  <div className="mt-4 flex items-center justify-between text-xs text-ink-soft">
                    <span>الدرجة الكلية {e.total_score}</span>
                    {e.statistics && e.statistics.graded_count > 0 ? (
                      <span className="flex items-center gap-1">
                        <BarChart3 className="h-3.5 w-3.5" />
                        متوسط {e.statistics.average}
                      </span>
                    ) : (
                      <span className="text-ink-muted">لم تُرصد الدرجات بعد</span>
                    )}
                  </div>
                </Card>
              </Link>
            </motion.div>
          ))}
        </div>
      )}

      <ExamFormDialog classes={classes} open={createOpen} onOpenChange={setCreateOpen} />
    </div>
  );
}
