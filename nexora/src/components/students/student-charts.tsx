"use client";

import { useMemo } from "react";
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/shared/empty-state";
import { formatDate } from "@/lib/utils";

const ACCENT = "#4338ca";
const SUCCESS = "#15803d";
const DANGER = "#b42318";
const WARNING = "#926500";

interface GradeRow {
  id: string;
  score: number;
  exam: { title: string; date: string; total_score: number } | null;
}
interface AttendanceRow {
  id: string;
  date: string;
  status: string;
}
interface SubmissionRow {
  id: string;
  status: string;
}

export function PerformanceTrendChart({ grades }: { grades: GradeRow[] }) {
  const data = useMemo(
    () =>
      [...grades]
        .filter((g) => g.exam)
        .sort((a, b) => new Date(a.exam!.date).getTime() - new Date(b.exam!.date).getTime())
        .map((g) => ({
          name: g.exam!.title.length > 12 ? g.exam!.title.slice(0, 12) + "…" : g.exam!.title,
          date: formatDate(g.exam!.date, { month: "short", day: "numeric", year: undefined }),
          pct: Math.round((g.score / (g.exam!.total_score || 1)) * 100),
        })),
    [grades]
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle>اتجاه الأداء</CardTitle>
      </CardHeader>
      <CardContent>
        {data.length === 0 ? (
          <EmptyState title="لا توجد درجات مسجلة بعد" />
        ) : (
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={data} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e5eb" vertical={false} />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#8a8b96" }} axisLine={false} tickLine={false} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: "#8a8b96" }} axisLine={false} tickLine={false} />
              <Tooltip
                formatter={(value) => [`${value}٪`, "النسبة"]}
                contentStyle={{ borderRadius: 10, border: "1px solid #e5e5eb", fontSize: 12, fontFamily: "var(--font-cairo)" }}
              />
              <Line type="monotone" dataKey="pct" stroke={ACCENT} strokeWidth={2.5} dot={{ r: 3, fill: ACCENT }} isAnimationActive />
            </LineChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}

export function AttendanceTrendChart({ attendance }: { attendance: AttendanceRow[] }) {
  const data = useMemo(() => {
    const byWeek = new Map<string, { present: number; total: number }>();
    [...attendance]
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
      .forEach((a) => {
        const d = new Date(a.date);
        const weekStart = new Date(d);
        weekStart.setDate(d.getDate() - d.getDay());
        const key = weekStart.toISOString().slice(0, 10);
        const entry = byWeek.get(key) ?? { present: 0, total: 0 };
        entry.total += 1;
        if (a.status === "present") entry.present += 1;
        byWeek.set(key, entry);
      });
    return Array.from(byWeek.entries())
      .slice(-8)
      .map(([key, v]) => ({
        week: formatDate(key, { month: "short", day: "numeric", year: undefined }),
        rate: Math.round((v.present / v.total) * 100),
      }));
  }, [attendance]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>اتجاه الحضور الأسبوعي</CardTitle>
      </CardHeader>
      <CardContent>
        {data.length === 0 ? (
          <EmptyState title="لا توجد بيانات حضور بعد" />
        ) : (
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={data} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e5eb" vertical={false} />
              <XAxis dataKey="week" tick={{ fontSize: 11, fill: "#8a8b96" }} axisLine={false} tickLine={false} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: "#8a8b96" }} axisLine={false} tickLine={false} />
              <Tooltip
                formatter={(value) => [`${value}٪`, "نسبة الحضور"]}
                contentStyle={{ borderRadius: 10, border: "1px solid #e5e5eb", fontSize: 12, fontFamily: "var(--font-cairo)" }}
              />
              <Bar dataKey="rate" radius={[6, 6, 0, 0]}>
                {data.map((d, i) => (
                  <Cell key={i} fill={d.rate >= 80 ? SUCCESS : d.rate >= 60 ? WARNING : DANGER} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}

export function HomeworkCompletionChart({ submissions }: { submissions: SubmissionRow[] }) {
  const counts = useMemo(() => {
    const graded = submissions.filter((s) => s.status === "graded").length;
    const submitted = submissions.filter((s) => s.status === "submitted").length;
    const late = submissions.filter((s) => s.status === "late").length;
    const missing = submissions.filter((s) => s.status === "missing" || s.status === "not_submitted").length;
    return [
      { name: "مصحّح", value: graded, color: SUCCESS },
      { name: "مُسلَّم", value: submitted, color: ACCENT },
      { name: "متأخر", value: late, color: WARNING },
      { name: "مفقود", value: missing, color: DANGER },
    ];
  }, [submissions]);

  const total = counts.reduce((a, c) => a + c.value, 0);

  return (
    <Card>
      <CardHeader>
        <CardTitle>إنجاز الواجبات</CardTitle>
      </CardHeader>
      <CardContent>
        {total === 0 ? (
          <EmptyState title="لا توجد واجبات مسندة بعد" />
        ) : (
          <div className="space-y-3">
            <div className="flex h-3 overflow-hidden rounded-full bg-surface">
              {counts.map(
                (c) => c.value > 0 && <div key={c.name} style={{ width: `${(c.value / total) * 100}%`, backgroundColor: c.color }} />
              )}
            </div>
            <ul className="grid grid-cols-2 gap-2 text-xs">
              {counts.map((c) => (
                <li key={c.name} className="flex items-center gap-1.5 text-ink-soft">
                  <span className="h-2 w-2 rounded-full" style={{ backgroundColor: c.color }} />
                  {c.name} ({c.value})
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
