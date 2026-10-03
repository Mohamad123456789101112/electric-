import { notFound } from "next/navigation";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { requireActiveOrg, STAFF_ROLES } from "@/lib/auth/session";
import { getAssignmentById, listSubmissionsForAssignment, getMyStudentRecordInOrg } from "@/lib/data/assignments";
import { listClassRoster } from "@/lib/data/classes";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FileDownloadLink } from "@/components/shared/file-download-link";
import { SubmissionsManager, type RosterSubmissionRow } from "@/components/assignments/submissions-manager";
import { StudentSubmissionForm } from "@/components/assignments/student-submission-form";
import { formatDateTime } from "@/lib/utils";

export const dynamic = "force-dynamic";

export default async function AssignmentDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const { supabase, organization, membership, user } = await requireActiveOrg();

  const assignment = await getAssignmentById(supabase, organization.id, id);
  if (!assignment) notFound();

  const isStaff = STAFF_ROLES.includes(membership.role);

  return (
    <div className="space-y-6">
      <Link href="/assignments" className="inline-flex items-center gap-1 text-sm text-ink-muted hover:text-ink">
        <ArrowRight className="h-3.5 w-3.5" />
        العودة إلى الواجبات
      </Link>

      <Card>
        <CardContent className="p-5 sm:p-6">
          <h1 className="text-xl font-bold text-ink">{assignment.title}</h1>
          <p className="mt-1 text-sm text-ink-muted">
            {assignment.class?.name} · الموعد النهائي {formatDateTime(assignment.deadline)} · الدرجة الكاملة {assignment.max_score}
          </p>
          {assignment.description && <p className="mt-3 text-sm leading-relaxed text-ink-soft">{assignment.description}</p>}
          {assignment.attachment_path && (
            <div className="mt-3">
              <FileDownloadLink bucket="assignment-files" path={assignment.attachment_path} label="تحميل المرفق" />
            </div>
          )}
        </CardContent>
      </Card>

      {isStaff ? (
        <StaffView assignmentId={id} classId={assignment.class_id} maxScore={assignment.max_score} />
      ) : (
        <StudentView orgId={organization.id} assignmentId={id} userId={user.id} maxScore={assignment.max_score} isPastDeadline={new Date(assignment.deadline).getTime() < Date.now()} />
      )}
    </div>
  );
}

async function StaffView({ assignmentId, classId, maxScore }: { assignmentId: string; classId: string; maxScore: number }) {
  const { supabase } = await requireActiveOrg();
  const [roster, submissions] = await Promise.all([listClassRoster(supabase, classId), listSubmissionsForAssignment(supabase, assignmentId)]);

  const submissionByStudent = new Map(submissions.map((s) => [s.student_id, s]));

  type StudentInfo = { id: string; full_name: string; student_code: string; status: string };
  type RosterRow = { student: StudentInfo | StudentInfo[] | null };

  const activeStudents: StudentInfo[] = (roster as unknown as RosterRow[])
    .map((r): StudentInfo | null => (Array.isArray(r.student) ? r.student[0] ?? null : r.student))
    .filter((s): s is StudentInfo => !!s && s.status === "active");

  const rows: RosterSubmissionRow[] = activeStudents.map((student) => {
      const s = submissionByStudent.get(student.id);
      return {
        studentId: student.id,
        studentName: student.full_name,
        studentCode: student.student_code,
        status: s?.status ?? "not_submitted",
        score: s?.score ?? null,
        feedback: s?.feedback ?? null,
        submittedAt: s?.submitted_at ?? null,
        filePath: s?.file_path ?? null,
      };
    });

  return (
    <Card>
      <CardHeader>
        <CardTitle>التسليمات ({rows.length})</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <SubmissionsManager assignmentId={assignmentId} rows={rows} maxScore={maxScore} />
      </CardContent>
    </Card>
  );
}

async function StudentView({
  orgId,
  assignmentId,
  userId,
  maxScore,
  isPastDeadline,
}: {
  orgId: string;
  assignmentId: string;
  userId: string;
  maxScore: number;
  isPastDeadline: boolean;
}) {
  const { supabase } = await requireActiveOrg();
  const student = await getMyStudentRecordInOrg(supabase, orgId, userId);

  if (!student) {
    return (
      <Card>
        <CardContent className="p-6 text-sm text-ink-muted">حسابك غير مرتبط بسجل طالب في هذه المؤسسة بعد.</CardContent>
      </Card>
    );
  }

  const { data: existing } = await supabase
    .from("submissions")
    .select("status, score, feedback, file_path, content")
    .eq("assignment_id", assignmentId)
    .eq("student_id", student.id)
    .maybeSingle();

  return (
    <StudentSubmissionForm
      orgId={orgId}
      assignmentId={assignmentId}
      studentId={student.id}
      existing={
        existing
          ? {
              status: existing.status,
              score: existing.score,
              feedback: existing.feedback,
              filePath: existing.file_path,
              content: existing.content,
            }
          : null
      }
      maxScore={maxScore}
      isPastDeadline={isPastDeadline}
    />
  );
}
