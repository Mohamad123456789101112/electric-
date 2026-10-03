-- =============================================================================
-- NEXORA — 0003: Education domain tables
-- =============================================================================

-- ---------------------------------------------------------------------------
-- students
-- ---------------------------------------------------------------------------
create table if not exists public.students (
  id               uuid primary key default gen_random_uuid(),
  organization_id  uuid not null references public.organizations (id) on delete cascade,
  profile_id       uuid references auth.users (id) on delete set null, -- optional student portal login
  student_code     text not null check (char_length(student_code) between 2 and 30),
  full_name        text not null check (char_length(trim(full_name)) between 2 and 150),
  email            citext,
  phone            text check (phone is null or phone ~ '^\+?[0-9\s\-()]{6,20}$'),
  date_of_birth    date check (date_of_birth is null or date_of_birth <= current_date),
  gender           text check (gender is null or gender in ('male', 'female')),
  class_id         uuid, -- FK added below after classes table exists
  guardian_name    text,
  guardian_phone   text,
  status           public.student_status not null default 'active',
  notes            text,
  created_by       uuid references auth.users (id) on delete set null,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now(),
  deleted_at       timestamptz,
  constraint students_unique_code unique (organization_id, student_code)
);

create index if not exists idx_students_org on public.students (organization_id) where deleted_at is null;
create index if not exists idx_students_class on public.students (class_id);
create index if not exists idx_students_profile on public.students (profile_id);
create index if not exists idx_students_status on public.students (organization_id, status);
create index if not exists idx_students_search on public.students using gin (
  to_tsvector('simple', coalesce(full_name, '') || ' ' || coalesce(student_code, ''))
);

alter table public.guardians
  add constraint guardians_student_fk foreign key (student_id) references public.students (id) on delete cascade;

-- ---------------------------------------------------------------------------
-- classes
-- ---------------------------------------------------------------------------
create table if not exists public.classes (
  id               uuid primary key default gen_random_uuid(),
  organization_id  uuid not null references public.organizations (id) on delete cascade,
  name             text not null check (char_length(trim(name)) between 1 and 120),
  subject          text not null check (char_length(trim(subject)) between 1 and 80),
  teacher_id       uuid references auth.users (id) on delete set null,
  academic_year    text not null check (academic_year ~ '^[0-9]{4}(-[0-9]{4})?$'),
  schedule         jsonb not null default '[]'::jsonb,
  capacity         int check (capacity is null or capacity > 0),
  created_by       uuid references auth.users (id) on delete set null,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now(),
  deleted_at       timestamptz
);

create index if not exists idx_classes_org on public.classes (organization_id) where deleted_at is null;
create index if not exists idx_classes_teacher on public.classes (teacher_id);

alter table public.students
  add constraint students_class_fk foreign key (class_id) references public.classes (id) on delete set null;

-- ---------------------------------------------------------------------------
-- class_members (roster)
-- ---------------------------------------------------------------------------
create table if not exists public.class_members (
  id               uuid primary key default gen_random_uuid(),
  organization_id  uuid not null references public.organizations (id) on delete cascade,
  class_id         uuid not null references public.classes (id) on delete cascade,
  student_id       uuid not null references public.students (id) on delete cascade,
  created_at       timestamptz not null default now(),
  constraint class_members_unique unique (class_id, student_id)
);

create index if not exists idx_class_members_class on public.class_members (class_id);
create index if not exists idx_class_members_student on public.class_members (student_id);

-- ---------------------------------------------------------------------------
-- attendance
-- ---------------------------------------------------------------------------
create table if not exists public.attendance (
  id               uuid primary key default gen_random_uuid(),
  organization_id  uuid not null references public.organizations (id) on delete cascade,
  student_id       uuid not null references public.students (id) on delete cascade,
  class_id         uuid not null references public.classes (id) on delete cascade,
  date             date not null,
  status           public.attendance_status not null,
  notes            text,
  recorded_by      uuid references auth.users (id) on delete set null,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now(),
  constraint attendance_unique_per_day unique (student_id, class_id, date)
);

create index if not exists idx_attendance_org_date on public.attendance (organization_id, date);
create index if not exists idx_attendance_class_date on public.attendance (class_id, date);
create index if not exists idx_attendance_student on public.attendance (student_id, date);

-- ---------------------------------------------------------------------------
-- assignments
-- ---------------------------------------------------------------------------
create table if not exists public.assignments (
  id               uuid primary key default gen_random_uuid(),
  organization_id  uuid not null references public.organizations (id) on delete cascade,
  class_id         uuid not null references public.classes (id) on delete cascade,
  title            text not null check (char_length(trim(title)) between 2 and 200),
  description      text,
  max_score        numeric(6, 2) not null default 100 check (max_score > 0),
  deadline          timestamptz not null,
  attachment_path  text,
  created_by       uuid references auth.users (id) on delete set null,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now(),
  deleted_at       timestamptz
);

create index if not exists idx_assignments_class on public.assignments (class_id) where deleted_at is null;
create index if not exists idx_assignments_org on public.assignments (organization_id);
create index if not exists idx_assignments_deadline on public.assignments (deadline);

-- ---------------------------------------------------------------------------
-- submissions
-- ---------------------------------------------------------------------------
create table if not exists public.submissions (
  id               uuid primary key default gen_random_uuid(),
  organization_id  uuid not null references public.organizations (id) on delete cascade,
  assignment_id    uuid not null references public.assignments (id) on delete cascade,
  student_id       uuid not null references public.students (id) on delete cascade,
  file_path        text,
  content          text,
  submitted_at     timestamptz,
  score            numeric(6, 2) check (score is null or score >= 0),
  feedback         text,
  status           public.submission_status not null default 'not_submitted',
  graded_by        uuid references auth.users (id) on delete set null,
  graded_at        timestamptz,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now(),
  constraint submissions_unique unique (assignment_id, student_id)
);

create index if not exists idx_submissions_assignment on public.submissions (assignment_id);
create index if not exists idx_submissions_student on public.submissions (student_id);
create index if not exists idx_submissions_status on public.submissions (organization_id, status);

-- ---------------------------------------------------------------------------
-- exams
-- ---------------------------------------------------------------------------
create table if not exists public.exams (
  id               uuid primary key default gen_random_uuid(),
  organization_id  uuid not null references public.organizations (id) on delete cascade,
  class_id         uuid not null references public.classes (id) on delete cascade,
  title            text not null check (char_length(trim(title)) between 2 and 200),
  date             date not null,
  total_score      numeric(6, 2) not null default 100 check (total_score > 0),
  created_by       uuid references auth.users (id) on delete set null,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now(),
  deleted_at       timestamptz
);

create index if not exists idx_exams_class on public.exams (class_id) where deleted_at is null;
create index if not exists idx_exams_org_date on public.exams (organization_id, date);

-- ---------------------------------------------------------------------------
-- grades
-- ---------------------------------------------------------------------------
create table if not exists public.grades (
  id               uuid primary key default gen_random_uuid(),
  organization_id  uuid not null references public.organizations (id) on delete cascade,
  exam_id          uuid not null references public.exams (id) on delete cascade,
  student_id       uuid not null references public.students (id) on delete cascade,
  score            numeric(6, 2) not null check (score >= 0),
  feedback         text,
  graded_by        uuid references auth.users (id) on delete set null,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now(),
  constraint grades_unique unique (exam_id, student_id)
);

create index if not exists idx_grades_exam on public.grades (exam_id);
create index if not exists idx_grades_student on public.grades (student_id);
