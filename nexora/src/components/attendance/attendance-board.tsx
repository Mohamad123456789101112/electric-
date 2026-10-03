"use client";

import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { CalendarCheck, CheckCircle2, XCircle, Clock, FileQuestion, Save } from "lucide-react";
import { createClient } from "@/lib/supabase/client";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Avatar } from "@/components/ui/avatar";
import { EmptyState } from "@/components/shared/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { saveAttendanceAction } from "@/app/(app)/attendance/actions";
import type { AttendanceStatus } from "@/types/database";

const STATUS_CONFIG: Record<AttendanceStatus, { label: string; icon: typeof CheckCircle2; activeClass: string }> = {
  present: { label: "حاضر", icon: CheckCircle2, activeClass: "bg-success text-white border-success" },
  absent: { label: "غائب", icon: XCircle, activeClass: "bg-danger text-white border-danger" },
  late: { label: "متأخر", icon: Clock, activeClass: "bg-warning text-white border-warning" },
  excused: { label: "بعذر", icon: FileQuestion, activeClass: "bg-info text-white border-info" },
};

interface RosterStudent {
  id: string;
  full_name: string;
  student_code: string;
}

export function AttendanceBoard({ classes, initialClassId }: { classes: Array<{ id: string; name: string; subject: string }>; initialClassId?: string }) {
  const [classId, setClassId] = useState<string>(initialClassId && classes.some((c) => c.id === initialClassId) ? initialClassId : classes[0]?.id ?? "");
  const [date, setDate] = useState<string>(new Date().toISOString().slice(0, 10));
  const [roster, setRoster] = useState<RosterStudent[]>([]);
  const [statuses, setStatuses] = useState<Record<string, AttendanceStatus>>({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  const supabase = useMemo(() => createClient(), []);

  useEffect(() => {
    if (!classId || !date) return;
    let active = true;
    setLoading(true);

    async function load() {
      const [rosterRes, attendanceRes] = await Promise.all([
        supabase.from("class_members").select("student:students(id, full_name, student_code, status)").eq("class_id", classId),
        supabase.from("attendance").select("student_id, status").eq("class_id", classId).eq("date", date),
      ]);

      if (!active) return;

      const students = (rosterRes.data ?? [])
        .map((r) => (Array.isArray(r.student) ? r.student[0] : r.student))
        .filter((s): s is RosterStudent & { status: string } => !!s && s.status === "active")
        .map((s) => ({ id: s.id, full_name: s.full_name, student_code: s.student_code }));

      const existing = new Map((attendanceRes.data ?? []).map((a) => [a.student_id, a.status as AttendanceStatus]));
      const initialStatuses: Record<string, AttendanceStatus> = {};
      students.forEach((s) => {
        initialStatuses[s.id] = existing.get(s.id) ?? "present";
      });

      setRoster(students);
      setStatuses(initialStatuses);
      setLoading(false);
    }

    load();
    return () => {
      active = false;
    };
  }, [classId, date, supabase]);

  function setAll(status: AttendanceStatus) {
    setStatuses((prev) => {
      const next = { ...prev };
      roster.forEach((s) => (next[s.id] = status));
      return next;
    });
  }

  async function save() {
    if (!classId || roster.length === 0) return;
    setSaving(true);
    const records = roster.map((s) => ({ studentId: s.id, status: statuses[s.id] ?? "present" }));
    const result = await saveAttendanceAction({ classId, date, records });
    setSaving(false);
    if (!result.ok) {
      toast.error(result.error);
      return;
    }
    toast.success("تم حفظ سجل الحضور بنجاح");
  }

  const summary = useMemo(() => {
    const counts: Record<AttendanceStatus, number> = { present: 0, absent: 0, late: 0, excused: 0 };
    Object.values(statuses).forEach((s) => counts[s]++);
    return counts;
  }, [statuses]);

  if (classes.length === 0) {
    return (
      <Card>
        <EmptyState icon={CalendarCheck} title="لا توجد فصول متاحة" description="لا يوجد فصل مسند إليك لتسجيل الحضور فيه بعد." />
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <Card className="p-4 sm:p-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <Select value={classId} onValueChange={setClassId}>
            <SelectTrigger className="sm:w-64">
              <SelectValue placeholder="اختر فصلاً" />
            </SelectTrigger>
            <SelectContent>
              {classes.map((c) => (
                <SelectItem key={c.id} value={c.id}>
                  {c.name} — {c.subject}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="sm:w-48" max={new Date().toISOString().slice(0, 10)} />
          <div className="flex-1" />
          <Button variant="outline" size="sm" onClick={() => setAll("present")}>
            <CheckCircle2 className="h-3.5 w-3.5" />
            تحديد الكل حاضر
          </Button>
          <Button variant="accent" size="sm" onClick={save} loading={saving} disabled={roster.length === 0}>
            <Save className="h-3.5 w-3.5" />
            حفظ
          </Button>
        </div>
        {roster.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-3 text-xs text-ink-muted">
            {(Object.keys(STATUS_CONFIG) as AttendanceStatus[]).map((key) => (
              <span key={key} className="flex items-center gap-1">
                <span className={cn("h-2 w-2 rounded-full", STATUS_CONFIG[key].activeClass.split(" ")[0])} />
                {STATUS_CONFIG[key].label}: {summary[key]}
              </span>
            ))}
          </div>
        )}
      </Card>

      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="space-y-3 p-4">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : roster.length === 0 ? (
            <EmptyState icon={CalendarCheck} title="لا يوجد طلاب في هذا الفصل" />
          ) : (
            <ul className="divide-y divide-border">
              {roster.map((s) => (
                <li key={s.id} className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex items-center gap-2.5">
                    <Avatar name={s.full_name} size="sm" />
                    <div>
                      <p className="text-sm font-medium text-ink">{s.full_name}</p>
                      <p className="font-mono text-xs text-ink-muted">{s.student_code}</p>
                    </div>
                  </div>
                  <div className="flex gap-1.5">
                    {(Object.keys(STATUS_CONFIG) as AttendanceStatus[]).map((key) => {
                      const config = STATUS_CONFIG[key];
                      const active = statuses[s.id] === key;
                      return (
                        <button
                          key={key}
                          type="button"
                          onClick={() => setStatuses((prev) => ({ ...prev, [s.id]: key }))}
                          className={cn(
                            "flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-all",
                            active ? config.activeClass : "border-border text-ink-muted hover:border-border-strong"
                          )}
                          aria-pressed={active}
                        >
                          <config.icon className="h-3.5 w-3.5" />
                          {config.label}
                        </button>
                      );
                    })}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
