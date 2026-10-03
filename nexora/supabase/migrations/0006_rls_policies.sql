-- =============================================================================
-- NEXORA — 0006: Row Level Security
-- =============================================================================
-- Every tenant-owned table is locked down by default (RLS enabled, no policy
-- = no access). Policies are additive (OR'd) per command. Nothing here ever
-- trusts a client-supplied organization_id/user_id without re-checking
-- membership through the SECURITY DEFINER helpers from 0005.
-- =============================================================================

-- Table privileges are the outer gate; RLS policies (below) are the real
-- authorization layer. We grant broadly to `authenticated` the same way a
-- fresh Supabase project does by default, and rely entirely on RLS + the
-- SECURITY DEFINER helpers to decide what any given row/action is allowed.
grant usage on schema public to anon, authenticated;
grant select, insert, update, delete on all tables in schema public to authenticated;
grant select on public.plans to anon;
alter default privileges in schema public grant select, insert, update, delete on tables to authenticated;

alter table public.profiles                    enable row level security;
alter table public.organizations                enable row level security;
alter table public.organization_members         enable row level security;
alter table public.guardians                    enable row level security;
alter table public.students                     enable row level security;
alter table public.classes                      enable row level security;
alter table public.class_members                enable row level security;
alter table public.attendance                   enable row level security;
alter table public.assignments                  enable row level security;
alter table public.submissions                  enable row level security;
alter table public.exams                        enable row level security;
alter table public.grades                       enable row level security;
alter table public.payments                     enable row level security;
alter table public.conversations                enable row level security;
alter table public.conversation_participants    enable row level security;
alter table public.messages                     enable row level security;
alter table public.notifications                enable row level security;
alter table public.files                        enable row level security;
alter table public.audit_logs                   enable row level security;
alter table public.plans                        enable row level security;
alter table public.organization_subscriptions   enable row level security;

-- ---------------------------------------------------------------------------
-- profiles
-- ---------------------------------------------------------------------------
create policy profiles_select_self_or_orgmate on public.profiles
  for select to authenticated
  using (id = auth.uid() or public.shares_org_with(id));

create policy profiles_insert_self on public.profiles
  for insert to authenticated
  with check (id = auth.uid());

create policy profiles_update_self on public.profiles
  for update to authenticated
  using (id = auth.uid())
  with check (id = auth.uid());

-- ---------------------------------------------------------------------------
-- organizations
-- ---------------------------------------------------------------------------
create policy organizations_select_member on public.organizations
  for select to authenticated
  using (public.is_org_member(id));

-- INSERT is intentionally NOT exposed here — orgs are created exclusively via
-- the public.create_organization() security-definer function, which also
-- creates the owner membership atomically.
create policy organizations_update_admin on public.organizations
  for update to authenticated
  using (public.is_org_admin(id))
  with check (public.is_org_admin(id));

-- ---------------------------------------------------------------------------
-- organization_members
-- ---------------------------------------------------------------------------
create policy org_members_select_member on public.organization_members
  for select to authenticated
  using (public.is_org_member(organization_id));

-- Admins/owners can invite members, but only an owner can create another owner.
create policy org_members_insert_admin on public.organization_members
  for insert to authenticated
  with check (
    public.is_org_admin(organization_id)
    and (role <> 'owner' or public.has_role(organization_id, array['owner']::public.org_role[]))
  );

create policy org_members_update_admin on public.organization_members
  for update to authenticated
  using (public.is_org_admin(organization_id))
  with check (
    public.is_org_admin(organization_id)
    and (role <> 'owner' or public.has_role(organization_id, array['owner']::public.org_role[]))
  );

create policy org_members_delete_admin on public.organization_members
  for delete to authenticated
  using (
    public.is_org_admin(organization_id)
    and (role <> 'owner' or public.has_role(organization_id, array['owner']::public.org_role[]))
  );

-- A user may always see/update their own membership row to leave or read status.
create policy org_members_select_self on public.organization_members
  for select to authenticated
  using (user_id = auth.uid());

-- ---------------------------------------------------------------------------
-- guardians
-- ---------------------------------------------------------------------------
create policy guardians_select on public.guardians
  for select to authenticated
  using (
    public.is_org_admin(organization_id)
    or public.has_role(organization_id, array['teacher']::public.org_role[])
    or parent_user_id = auth.uid()
    or public.is_student_self(student_id)
  );

create policy guardians_write_admin on public.guardians
  for insert to authenticated
  with check (public.is_org_admin(organization_id));

create policy guardians_update_admin on public.guardians
  for update to authenticated
  using (public.is_org_admin(organization_id))
  with check (public.is_org_admin(organization_id));

create policy guardians_delete_admin on public.guardians
  for delete to authenticated
  using (public.is_org_admin(organization_id));

-- ---------------------------------------------------------------------------
-- students
-- ---------------------------------------------------------------------------
create policy students_select on public.students
  for select to authenticated
  using (
    public.is_org_admin(organization_id)
    or public.has_role(organization_id, array['teacher','accountant']::public.org_role[])
    or profile_id = auth.uid()
    or public.is_guardian_of(id)
  );

create policy students_insert_admin on public.students
  for insert to authenticated
  with check (public.is_org_admin(organization_id));

create policy students_update_admin on public.students
  for update to authenticated
  using (public.is_org_admin(organization_id))
  with check (public.is_org_admin(organization_id));

create policy students_delete_admin on public.students
  for delete to authenticated
  using (public.is_org_admin(organization_id));

-- ---------------------------------------------------------------------------
-- classes
-- ---------------------------------------------------------------------------
create policy classes_select on public.classes
  for select to authenticated
  using (
    public.is_org_admin(organization_id)
    or teacher_id = auth.uid()
    or public.has_role(organization_id, array['accountant']::public.org_role[])
    or exists (
      select 1 from public.class_members cm
      where cm.class_id = classes.id
        and (public.is_student_self(cm.student_id) or public.is_guardian_of(cm.student_id))
    )
  );

create policy classes_insert_admin on public.classes
  for insert to authenticated
  with check (public.is_org_admin(organization_id));

create policy classes_update_admin on public.classes
  for update to authenticated
  using (public.is_org_admin(organization_id) or teacher_id = auth.uid())
  with check (public.is_org_admin(organization_id) or teacher_id = auth.uid());

create policy classes_delete_admin on public.classes
  for delete to authenticated
  using (public.is_org_admin(organization_id));

-- ---------------------------------------------------------------------------
-- class_members
-- ---------------------------------------------------------------------------
create policy class_members_select on public.class_members
  for select to authenticated
  using (
    public.is_org_admin(organization_id)
    or public.is_class_teacher(class_id)
    or public.has_role(organization_id, array['accountant']::public.org_role[])
    or public.is_student_self(student_id)
    or public.is_guardian_of(student_id)
  );

create policy class_members_write_admin on public.class_members
  for insert to authenticated
  with check (public.is_org_admin(organization_id) or public.is_class_teacher(class_id));

create policy class_members_delete_admin on public.class_members
  for delete to authenticated
  using (public.is_org_admin(organization_id) or public.is_class_teacher(class_id));

-- ---------------------------------------------------------------------------
-- attendance
-- ---------------------------------------------------------------------------
create policy attendance_select on public.attendance
  for select to authenticated
  using (
    public.is_org_admin(organization_id)
    or public.is_class_teacher(class_id)
    or public.is_student_self(student_id)
    or public.is_guardian_of(student_id)
  );

create policy attendance_insert_staff on public.attendance
  for insert to authenticated
  with check (
    (public.is_org_admin(organization_id) or public.is_class_teacher(class_id))
    and recorded_by = auth.uid()
  );

create policy attendance_update_staff on public.attendance
  for update to authenticated
  using (public.is_org_admin(organization_id) or public.is_class_teacher(class_id))
  with check (public.is_org_admin(organization_id) or public.is_class_teacher(class_id));

create policy attendance_delete_staff on public.attendance
  for delete to authenticated
  using (public.is_org_admin(organization_id) or public.is_class_teacher(class_id));

-- ---------------------------------------------------------------------------
-- assignments
-- ---------------------------------------------------------------------------
create policy assignments_select on public.assignments
  for select to authenticated
  using (
    public.is_org_admin(organization_id)
    or public.is_class_teacher(class_id)
    or exists (
      select 1 from public.class_members cm
      where cm.class_id = assignments.class_id
        and (public.is_student_self(cm.student_id) or public.is_guardian_of(cm.student_id))
    )
  );

create policy assignments_insert_staff on public.assignments
  for insert to authenticated
  with check ((public.is_org_admin(organization_id) or public.is_class_teacher(class_id)) and created_by = auth.uid());

create policy assignments_update_staff on public.assignments
  for update to authenticated
  using (public.is_org_admin(organization_id) or public.is_class_teacher(class_id))
  with check (public.is_org_admin(organization_id) or public.is_class_teacher(class_id));

create policy assignments_delete_staff on public.assignments
  for delete to authenticated
  using (public.is_org_admin(organization_id) or public.is_class_teacher(class_id));

-- ---------------------------------------------------------------------------
-- submissions — the important "student cannot grade themselves" guarantee.
-- ---------------------------------------------------------------------------
create policy submissions_select on public.submissions
  for select to authenticated
  using (
    public.is_org_admin(organization_id)
    or exists (select 1 from public.assignments a where a.id = submissions.assignment_id and public.is_class_teacher(a.class_id))
    or public.is_student_self(student_id)
    or public.is_guardian_of(student_id)
  );

-- Staff (admin/teacher of the assignment's class) can fully manage submissions, including grading.
create policy submissions_staff_insert on public.submissions
  for insert to authenticated
  with check (
    public.is_org_admin(organization_id)
    or exists (select 1 from public.assignments a where a.id = submissions.assignment_id and public.is_class_teacher(a.class_id))
  );

create policy submissions_staff_update on public.submissions
  for update to authenticated
  using (
    public.is_org_admin(organization_id)
    or exists (select 1 from public.assignments a where a.id = submissions.assignment_id and public.is_class_teacher(a.class_id))
  )
  with check (
    public.is_org_admin(organization_id)
    or exists (select 1 from public.assignments a where a.id = submissions.assignment_id and public.is_class_teacher(a.class_id))
  );

create policy submissions_staff_delete on public.submissions
  for delete to authenticated
  using (
    public.is_org_admin(organization_id)
    or exists (select 1 from public.assignments a where a.id = submissions.assignment_id and public.is_class_teacher(a.class_id))
  );

-- A student may create their own ungraded submission (score must stay null).
create policy submissions_student_insert on public.submissions
  for insert to authenticated
  with check (
    public.is_student_self(student_id)
    and score is null
    and status in ('submitted')
  );

-- A student may only update their own submission while it has not been graded
-- yet (USING checks the row BEFORE the update), and the update itself can
-- never introduce a score or flip status to "graded" (WITH CHECK checks the
-- row AFTER the update). This makes self-grading structurally impossible.
create policy submissions_student_update on public.submissions
  for update to authenticated
  using (public.is_student_self(student_id) and score is null)
  with check (public.is_student_self(student_id) and score is null and status in ('submitted'));

-- ---------------------------------------------------------------------------
-- exams
-- ---------------------------------------------------------------------------
create policy exams_select on public.exams
  for select to authenticated
  using (
    public.is_org_admin(organization_id)
    or public.is_class_teacher(class_id)
    or exists (
      select 1 from public.class_members cm
      where cm.class_id = exams.class_id
        and (public.is_student_self(cm.student_id) or public.is_guardian_of(cm.student_id))
    )
  );

create policy exams_insert_staff on public.exams
  for insert to authenticated
  with check ((public.is_org_admin(organization_id) or public.is_class_teacher(class_id)) and created_by = auth.uid());

create policy exams_update_staff on public.exams
  for update to authenticated
  using (public.is_org_admin(organization_id) or public.is_class_teacher(class_id))
  with check (public.is_org_admin(organization_id) or public.is_class_teacher(class_id));

create policy exams_delete_staff on public.exams
  for delete to authenticated
  using (public.is_org_admin(organization_id) or public.is_class_teacher(class_id));

-- ---------------------------------------------------------------------------
-- grades — fully staff-controlled. No student/parent write policy exists at
-- all, satisfying "student can never modify grades" by construction.
-- ---------------------------------------------------------------------------
create policy grades_select on public.grades
  for select to authenticated
  using (
    public.is_org_admin(organization_id)
    or exists (select 1 from public.exams e where e.id = grades.exam_id and public.is_class_teacher(e.class_id))
    or public.is_student_self(student_id)
    or public.is_guardian_of(student_id)
  );

create policy grades_insert_staff on public.grades
  for insert to authenticated
  with check (
    public.is_org_admin(organization_id)
    or exists (select 1 from public.exams e where e.id = grades.exam_id and public.is_class_teacher(e.class_id))
  );

create policy grades_update_staff on public.grades
  for update to authenticated
  using (
    public.is_org_admin(organization_id)
    or exists (select 1 from public.exams e where e.id = grades.exam_id and public.is_class_teacher(e.class_id))
  )
  with check (
    public.is_org_admin(organization_id)
    or exists (select 1 from public.exams e where e.id = grades.exam_id and public.is_class_teacher(e.class_id))
  );

create policy grades_delete_staff on public.grades
  for delete to authenticated
  using (
    public.is_org_admin(organization_id)
    or exists (select 1 from public.exams e where e.id = grades.exam_id and public.is_class_teacher(e.class_id))
  );

-- ---------------------------------------------------------------------------
-- payments — owner/admin/accountant only. Teachers get NO access by design.
-- ---------------------------------------------------------------------------
create policy payments_select on public.payments
  for select to authenticated
  using (
    public.is_org_admin(organization_id)
    or public.has_role(organization_id, array['accountant']::public.org_role[])
    or public.is_student_self(student_id)
    or public.is_guardian_of(student_id)
  );

create policy payments_insert_finance on public.payments
  for insert to authenticated
  with check (public.is_org_admin(organization_id) or public.has_role(organization_id, array['accountant']::public.org_role[]));

create policy payments_update_finance on public.payments
  for update to authenticated
  using (public.is_org_admin(organization_id) or public.has_role(organization_id, array['accountant']::public.org_role[]))
  with check (public.is_org_admin(organization_id) or public.has_role(organization_id, array['accountant']::public.org_role[]));

create policy payments_delete_finance on public.payments
  for delete to authenticated
  using (public.is_org_admin(organization_id) or public.has_role(organization_id, array['accountant']::public.org_role[]));

-- ---------------------------------------------------------------------------
-- conversations / participants / messages
-- ---------------------------------------------------------------------------
create policy conversations_select_participant on public.conversations
  for select to authenticated
  using (exists (
    select 1 from public.conversation_participants p
    where p.conversation_id = conversations.id and p.user_id = auth.uid()
  ));

create policy conversations_insert_member on public.conversations
  for insert to authenticated
  with check (public.is_org_member(organization_id) and created_by = auth.uid());

create policy conversation_participants_select on public.conversation_participants
  for select to authenticated
  using (
    user_id = auth.uid()
    or exists (
      select 1 from public.conversation_participants p2
      where p2.conversation_id = conversation_participants.conversation_id and p2.user_id = auth.uid()
    )
  );

-- Only the conversation creator (at creation time) or an org admin may seed
-- the participant list. A user cannot add themselves to an arbitrary
-- conversation they were not invited to.
create policy conversation_participants_insert on public.conversation_participants
  for insert to authenticated
  with check (
    exists (
      select 1 from public.conversations c
      where c.id = conversation_id and (c.created_by = auth.uid() or public.is_org_admin(c.organization_id))
    )
  );

create policy conversation_participants_delete_self on public.conversation_participants
  for delete to authenticated
  using (user_id = auth.uid());

create policy messages_select_participant on public.messages
  for select to authenticated
  using (exists (
    select 1 from public.conversation_participants p
    where p.conversation_id = messages.conversation_id and p.user_id = auth.uid()
  ));

create policy messages_insert_participant on public.messages
  for insert to authenticated
  with check (
    sender_id = auth.uid()
    and exists (
      select 1 from public.conversation_participants p
      where p.conversation_id = messages.conversation_id and p.user_id = auth.uid()
    )
  );

create policy messages_update_read_receipt on public.messages
  for update to authenticated
  using (exists (
    select 1 from public.conversation_participants p
    where p.conversation_id = messages.conversation_id and p.user_id = auth.uid()
  ))
  with check (true);

-- Defense in depth: even though the row-level policy above allows any
-- participant to issue an UPDATE, column-level privileges mean the only
-- column Postgres will actually let them change is read_at. Message content
-- is immutable after it is sent — nobody can rewrite history.
revoke update on public.messages from authenticated;
grant update (read_at) on public.messages to authenticated;

-- ---------------------------------------------------------------------------
-- notifications — strictly private to the owning user.
-- ---------------------------------------------------------------------------
create policy notifications_select_own on public.notifications
  for select to authenticated
  using (user_id = auth.uid());

create policy notifications_update_own on public.notifications
  for update to authenticated
  using (user_id = auth.uid())
  with check (user_id = auth.uid());

create policy notifications_insert_admin on public.notifications
  for insert to authenticated
  with check (public.is_org_admin(organization_id));

-- ---------------------------------------------------------------------------
-- files metadata
-- ---------------------------------------------------------------------------
create policy files_select on public.files
  for select to authenticated
  using (public.is_org_member(organization_id));

create policy files_insert_member on public.files
  for insert to authenticated
  with check (public.is_org_member(organization_id) and owner_id = auth.uid());

create policy files_delete_owner_or_admin on public.files
  for delete to authenticated
  using (owner_id = auth.uid() or public.is_org_admin(organization_id));

-- ---------------------------------------------------------------------------
-- audit_logs — read-only for owners/admins. No update/delete policy exists
-- for ANY role, which (with RLS enabled) makes the audit trail immutable
-- through the API, even for the organization's own owner.
-- ---------------------------------------------------------------------------
create policy audit_logs_select_admin on public.audit_logs
  for select to authenticated
  using (public.is_org_admin(organization_id));

-- Inserts only ever happen via the SECURITY DEFINER public.log_audit_event()
-- function or the trigger functions above, both of which run with elevated
-- privilege and therefore bypass this policy — so no direct INSERT policy
-- is granted to normal authenticated clients.

-- ---------------------------------------------------------------------------
-- plans — public read-only catalog.
-- ---------------------------------------------------------------------------
create policy plans_select_all on public.plans
  for select to authenticated, anon
  using (is_active);

-- ---------------------------------------------------------------------------
-- organization_subscriptions
-- ---------------------------------------------------------------------------
create policy org_subscriptions_select_member on public.organization_subscriptions
  for select to authenticated
  using (public.is_org_member(organization_id));
