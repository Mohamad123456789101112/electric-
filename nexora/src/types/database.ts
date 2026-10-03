// =============================================================================
// Hand-authored database types mirroring supabase/migrations/*.sql.
// Keep in sync with the schema. If you have the Supabase CLI connected to a
// live project, you can regenerate/augment this with:
//   supabase gen types typescript --project-id <ref> > src/types/database.ts
// =============================================================================

export type OrgRole = "owner" | "admin" | "teacher" | "accountant" | "student" | "parent";
export type MemberStatus = "invited" | "active" | "suspended";
export type OrganizationType = "school" | "academy" | "tutoring_center" | "individual_tutor" | "other";
export type StudentStatus = "active" | "inactive" | "graduated" | "archived";
export type AttendanceStatus = "present" | "absent" | "late" | "excused";
export type SubmissionStatus = "not_submitted" | "submitted" | "late" | "graded" | "missing";
export type PaymentStatus = "pending" | "paid" | "overdue" | "cancelled" | "refunded";
export type PaymentMethod = "cash" | "bank_transfer" | "card" | "wallet" | "other";
export type NotificationType =
  | "info"
  | "assignment"
  | "grade"
  | "payment"
  | "attendance"
  | "message"
  | "security"
  | "system";
export type ConversationType = "direct" | "group";
export type SubscriptionStatus = "trialing" | "active" | "past_due" | "canceled";

export interface Profile {
  id: string;
  full_name: string;
  avatar_url: string | null;
  phone: string | null;
  locale: "ar" | "en";
  created_at: string;
  updated_at: string;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  logo_url: string | null;
  org_type: OrganizationType;
  subjects: string[];
  student_count_estimate: number | null;
  settings: Record<string, unknown>;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
}

export interface OrganizationMember {
  id: string;
  organization_id: string;
  user_id: string | null;
  role: OrgRole;
  status: MemberStatus;
  invited_email: string | null;
  invited_by: string | null;
  joined_at: string | null;
  created_at: string;
  updated_at: string;
  // joined client-side
  profile?: Profile | null;
}

export interface Student {
  id: string;
  organization_id: string;
  profile_id: string | null;
  student_code: string;
  full_name: string;
  email: string | null;
  phone: string | null;
  date_of_birth: string | null;
  gender: "male" | "female" | null;
  class_id: string | null;
  guardian_name: string | null;
  guardian_phone: string | null;
  status: StudentStatus;
  notes: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  class?: Pick<ClassRow, "id" | "name" | "subject"> | null;
}

export interface ClassRow {
  id: string;
  organization_id: string;
  name: string;
  subject: string;
  teacher_id: string | null;
  academic_year: string;
  schedule: unknown[];
  capacity: number | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  teacher?: Pick<Profile, "id" | "full_name" | "avatar_url"> | null;
  student_count?: number;
}

export interface ClassMember {
  id: string;
  organization_id: string;
  class_id: string;
  student_id: string;
  created_at: string;
}

export interface Attendance {
  id: string;
  organization_id: string;
  student_id: string;
  class_id: string;
  date: string;
  status: AttendanceStatus;
  notes: string | null;
  recorded_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface Assignment {
  id: string;
  organization_id: string;
  class_id: string;
  title: string;
  description: string | null;
  max_score: number;
  deadline: string;
  attachment_path: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  class?: Pick<ClassRow, "id" | "name" | "subject" | "teacher_id"> | null;
  submission_count?: number;
  average_score?: number | null;
}

export interface Submission {
  id: string;
  organization_id: string;
  assignment_id: string;
  student_id: string;
  file_path: string | null;
  content: string | null;
  submitted_at: string | null;
  score: number | null;
  feedback: string | null;
  status: SubmissionStatus;
  graded_by: string | null;
  graded_at: string | null;
  created_at: string;
  updated_at: string;
  student?: Pick<Student, "id" | "full_name" | "student_code"> | null;
}

export interface Exam {
  id: string;
  organization_id: string;
  class_id: string;
  title: string;
  date: string;
  total_score: number;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  class?: Pick<ClassRow, "id" | "name" | "subject"> | null;
}

export interface Grade {
  id: string;
  organization_id: string;
  exam_id: string;
  student_id: string;
  score: number;
  feedback: string | null;
  graded_by: string | null;
  created_at: string;
  updated_at: string;
  student?: Pick<Student, "id" | "full_name" | "student_code"> | null;
}

export interface Payment {
  id: string;
  organization_id: string;
  student_id: string;
  amount: number;
  currency: string;
  due_date: string | null;
  paid_at: string | null;
  status: PaymentStatus;
  payment_method: PaymentMethod | null;
  invoice_number: string | null;
  notes: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  student?: Pick<Student, "id" | "full_name" | "student_code"> | null;
}

export interface Conversation {
  id: string;
  organization_id: string;
  type: ConversationType;
  title: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  participants?: Array<{ user_id: string; profile: Pick<Profile, "id" | "full_name" | "avatar_url"> | null }>;
  last_message?: Pick<Message, "content" | "created_at" | "sender_id"> | null;
  unread_count?: number;
}

export interface Message {
  id: string;
  organization_id: string;
  conversation_id: string;
  sender_id: string;
  receiver_id: string | null;
  content: string;
  attachment_path: string | null;
  read_at: string | null;
  created_at: string;
  sender?: Pick<Profile, "id" | "full_name" | "avatar_url"> | null;
}

export interface NotificationRow {
  id: string;
  organization_id: string;
  user_id: string;
  type: NotificationType;
  title: string;
  body: string | null;
  data: Record<string, unknown>;
  read_at: string | null;
  created_at: string;
}

export interface AuditLog {
  id: string;
  organization_id: string | null;
  user_id: string | null;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  metadata: Record<string, unknown>;
  ip_address: string | null;
  user_agent: string | null;
  created_at: string;
  actor?: Pick<Profile, "id" | "full_name" | "avatar_url"> | null;
}

export interface Plan {
  id: string;
  code: "starter" | "pro" | "business";
  name: string;
  description: string | null;
  price_monthly: number;
  currency: string;
  max_students: number | null;
  max_teachers: number | null;
  features: string[];
  is_active: boolean;
  created_at: string;
}

export interface OrganizationSubscription {
  id: string;
  organization_id: string;
  plan_id: string;
  status: SubscriptionStatus;
  current_period_end: string | null;
  provider: string | null;
  provider_ref: string | null;
  created_at: string;
  updated_at: string;
  plan?: Plan;
}

export interface FileRow {
  id: string;
  organization_id: string;
  owner_id: string | null;
  bucket_id: string;
  object_path: string;
  filename: string;
  mime_type: string;
  size_bytes: number;
  entity_type: "avatar" | "org_logo" | "assignment" | "submission" | "other" | null;
  entity_id: string | null;
  created_at: string;
  deleted_at: string | null;
}
