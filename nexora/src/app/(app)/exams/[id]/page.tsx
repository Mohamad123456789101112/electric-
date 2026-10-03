import { notFound } from "next/navigation";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { requireActiveOrg, STAFF_ROLES } from "@/lib/auth/session";
import { getExamById, listGradesForExam } from "@/lib/data/exams";
import { listClassRoster } from "@/lib/data/classes";
import { Card, CardContent } from "@/components/ui/card";
import { GradeBoard } from "@/components/exams/grade-board";
import { formatDate } from "@/lib/utils";

export const dynamic = "force-dynamic";

export default async function ExamDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const { supabase, organization, membership, user } = await requireActiveOrg();

  const exam = await getExamById(supabase, organization.id, id);
  if (!exam) notFound();

  const isStaff = STAFF_ROLES.includes(membership.role);

  return (
    <div className="space-y-6">
      <Link href="/exams" className="inline-flex items-center gap-1 text-sm text-ink-muted hover:text-ink">
        <ArrowRight className="h-3.5 w-3.5" />
        العودة إلى الاختبارات
      </Link>

      <Card>
        <CardContent className="p-5 sm:p-6">
          <h1 className="text-xl font-bold text-ink">{exam.title}</h1>
          <p className="mt-1 text-sm text-ink-muted">
            {exam.class?.name} · {formatDate(exam.date)} · الدرجة الكلية {exam.total_score}
          </p>
        </CardContent>
      </Card>

      {isStaff ? (
        <StaffGrades examId={id} classId={exam.class_id} totalScore={exam.total_score} />
      ) : (
        <StudentGrade orgId={organization.id} examId={id} userId={user.id} totalScore={exam.total_score} />
      )}
    </div>
  );
}

async function StaffGrades({ examId, classId, totalScore }: { examId: string; classId: string; totalScore: number }) {
  const { supabase } = await requireActiveOrg();
  const [roster, grades] = await Promise.all([listClassRoster(supabase, classId), listGradesForExam(supabase, examId)]);

  type StudentInfo = { id: string; full_name: string; student_code: string; status: string };
  const gradeByStudent = new Map(grades.map((g) => [g.student_id, g]));

  const activeStudents: StudentInfo[] = (roster as unknown as Array<{ student: StudentInfo | StudentInfo[] | null }>)
    .map((r) => (Array.isArray(r.student) ? r.student[0] ?? null : r.student))
    .filter((s): s is StudentInfo => !!s && s.status === "active");

  const rows = activeStudents.map((s) => {
    const g = gradeByStudent.get(s.id);
    return { studentId: s.id, studentName: s.full_name, studentCode: s.student_code, score: g?.score ?? null, feedback: g?.feedback ?? null };
  });

  return <GradeBoard examId={examId} totalScore={totalScore} initialRows={rows} />;
}

async function StudentGrade({ orgId, examId, userId, totalScore }: { orgId: string; examId: string; userId: string; totalScore: number }) {
  const { supabase } = await requireActiveOrg();
  const { data: student } = await supabase.from("students").select("id").eq("organization_id", orgId).eq("profile_id", userId).maybeSingle();

  if (!student) {
    return (
      <Card>
        <CardContent className="p-6 text-sm text-ink-muted">حسابك غير مرتبط بسجل طالب في هذه المؤسسة بعد.</CardContent>
      </Card>
    );
  }

  const { data: grade } = await supabase.from("grades").select("score, feedback").eq("exam_id", examId).eq("student_id", student.id).maybeSingle();

  return (
    <Card>
      <CardContent className="p-6">
        {grade ? (
          <div>
            <p className="text-2xl font-bold text-ink">
              {grade.score} <span className="text-base font-normal text-ink-muted">/ {totalScore}</span>
            </p>
            {grade.feedback && <p className="mt-2 text-sm text-ink-soft">{grade.feedback}</p>}
          </div>
        ) : (
          <p className="text-sm text-ink-muted">لم تُرصد درجتك بعد لهذا الاختبار.</p>
        )}
      </CardContent>
    </Card>
  );
}
