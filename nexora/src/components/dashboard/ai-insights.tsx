"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { Sparkles, TrendingDown, FileWarning, AlertOctagon, ArrowLeft } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { EmptyState } from "@/components/shared/empty-state";

interface DecliningStudent {
  student_id: string;
  full_name: string;
  class_name: string | null;
  previous_avg: number;
  recent_avg: number;
  change_pct: number;
}
interface MissingSubmission {
  assignment_id: string;
  assignment_title: string;
  class_name: string;
  missing_count: number;
}
interface ClassNeedsReview {
  class_id: string;
  class_name: string;
  avg_score: number | null;
  attendance_rate: number | null;
}

export function AiInsights({
  decliningStudents,
  missingSubmissions,
  classesNeedingReview,
}: {
  decliningStudents: DecliningStudent[];
  missingSubmissions: MissingSubmission[];
  classesNeedingReview: ClassNeedsReview[];
}) {
  const insights = [
    ...decliningStudents.map((s) => ({
      key: `decline-${s.student_id}`,
      icon: TrendingDown,
      tone: "danger" as const,
      text: `الطالب ${s.full_name} أظهر انخفاضاً في الأداء من ${s.previous_avg}٪ إلى ${s.recent_avg}٪${s.class_name ? ` في فصل ${s.class_name}` : ""}.`,
      href: `/students/${s.student_id}`,
    })),
    ...missingSubmissions.map((m) => ({
      key: `missing-${m.assignment_id}`,
      icon: FileWarning,
      tone: "warning" as const,
      text: `${m.missing_count} طالباً لم يسلّموا واجب "${m.assignment_title}" في فصل ${m.class_name}.`,
      href: `/assignments/${m.assignment_id}`,
    })),
    ...classesNeedingReview.map((c) => ({
      key: `review-${c.class_id}`,
      icon: AlertOctagon,
      tone: "warning" as const,
      text: `فصل ${c.class_name} يحتاج إلى مراجعة${c.avg_score !== null ? ` — متوسط الأداء ${c.avg_score}٪` : ""}${c.attendance_rate !== null ? `، نسبة الحضور ${c.attendance_rate}٪` : ""}.`,
      href: `/classes/${c.class_id}`,
    })),
  ];

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <div>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-accent" />
            NEXORA Intelligence
          </CardTitle>
          <CardDescription>ملاحظات مبنية على بيانات مؤسستك الفعلية</CardDescription>
        </div>
      </CardHeader>
      <CardContent>
        {insights.length === 0 ? (
          <EmptyState
            icon={Sparkles}
            title="لا توجد ملاحظات حرجة الآن"
            description="عندما تظهر أنماط تستحق الانتباه في أداء الطلاب أو الفصول، ستجدها هنا فوراً."
          />
        ) : (
          <ul className="space-y-2">
            {insights.slice(0, 6).map((insight, i) => (
              <motion.li
                key={insight.key}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, delay: i * 0.05 }}
                className="flex items-start justify-between gap-3 rounded-[var(--radius-md)] border border-border p-3.5 transition-colors hover:border-border-strong"
              >
                <div className="flex items-start gap-3">
                  <div
                    className={
                      "mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full " +
                      (insight.tone === "danger" ? "bg-danger-soft text-danger" : "bg-warning-soft text-warning")
                    }
                  >
                    <insight.icon className="h-3.5 w-3.5" />
                  </div>
                  <p className="text-sm leading-relaxed text-ink-soft">{insight.text}</p>
                </div>
                <Link
                  href={insight.href}
                  className="flex shrink-0 items-center gap-1 whitespace-nowrap text-xs font-medium text-accent hover:underline"
                >
                  عرض التفاصيل
                  <ArrowLeft className="h-3 w-3" />
                </Link>
              </motion.li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
