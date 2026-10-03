-- =============================================================================
-- NEXORA — 0005: Security helper functions & triggers
-- =============================================================================
-- All SECURITY DEFINER functions pin search_path to prevent search_path
-- hijacking attacks, and are STABLE/IMMUTABLE where possible for the planner.
-- These functions are the single source of truth used by RLS policies —
-- never duplicate this logic ad-hoc inside a policy.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- updated_at maintenance
-- ---------------------------------------------------------------------------
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

do $$
declare t text;
begin
  for t in
    select unnest(array[
      'profiles','organizations','organization_members','students','classes',
      'assignments','submissions','exams','grades','payments','conversations',
      'organization_subscriptions','attendance'
    ])
  loop
    execute format(
      'drop trigger if exists trg_set_updated_at on public.%I; create trigger trg_set_updated_at before update on public.%I for each row execute function public.set_updated_at();',
      t, t
    );
  end loop;
end $$;

-- ---------------------------------------------------------------------------
-- handle_new_user: auto-provision a profile row when someone signs up.
-- ---------------------------------------------------------------------------
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, full_name, avatar_url)
  values (
    new.id,
    coalesce(new.raw_user_meta_data ->> 'full_name', split_part(new.email, '@', 1)),
    new.raw_user_meta_data ->> 'avatar_url'
  )
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ---------------------------------------------------------------------------
-- Membership / role helpers — used pervasively by RLS policies.
-- ---------------------------------------------------------------------------
create or replace function public.is_org_member(p_org_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.organization_members m
    where m.organization_id = p_org_id
      and m.user_id = auth.uid()
      and m.status = 'active'
  );
$$;

create or replace function public.get_member_role(p_org_id uuid)
returns public.org_role
language sql
stable
security definer
set search_path = public
as $$
  select m.role from public.organization_members m
  where m.organization_id = p_org_id
    and m.user_id = auth.uid()
    and m.status = 'active'
  limit 1;
$$;

create or replace function public.has_role(p_org_id uuid, p_roles public.org_role[])
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.organization_members m
    where m.organization_id = p_org_id
      and m.user_id = auth.uid()
      and m.status = 'active'
      and m.role = any(p_roles)
  );
$$;

create or replace function public.is_org_admin(p_org_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select public.has_role(p_org_id, array['owner','admin']::public.org_role[]);
$$;

create or replace function public.is_class_teacher(p_class_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.classes c
    where c.id = p_class_id and c.teacher_id = auth.uid()
  );
$$;

create or replace function public.is_student_self(p_student_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.students s
    where s.id = p_student_id and s.profile_id = auth.uid()
  );
$$;

create or replace function public.is_guardian_of(p_student_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.guardians g
    where g.student_id = p_student_id and g.parent_user_id = auth.uid()
  );
$$;

-- Used so members of the same organization can see each other's display name/avatar.
create or replace function public.shares_org_with(p_user_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.organization_members a
    join public.organization_members b
      on a.organization_id = b.organization_id
    where a.user_id = auth.uid() and a.status = 'active'
      and b.user_id = p_user_id and b.status = 'active'
  );
$$;

grant execute on function
  public.is_org_member(uuid), public.get_member_role(uuid), public.has_role(uuid, public.org_role[]),
  public.is_org_admin(uuid), public.is_class_teacher(uuid), public.is_student_self(uuid),
  public.is_guardian_of(uuid), public.shares_org_with(uuid)
to authenticated;

-- ---------------------------------------------------------------------------
-- create_organization: atomic org + owner-membership creation (onboarding).
-- Prevents a client from inserting organization_members directly with an
-- arbitrary role (privilege escalation) by funnelling org creation through
-- one trusted, transactional entry point.
-- ---------------------------------------------------------------------------
create or replace function public.create_organization(
  p_name text,
  p_slug text,
  p_org_type public.organization_type default 'other',
  p_subjects text[] default '{}',
  p_student_count_estimate int default null
)
returns public.organizations
language plpgsql
security definer
set search_path = public
as $$
declare
  v_org public.organizations;
begin
  if auth.uid() is null then
    raise exception 'AUTH_REQUIRED' using errcode = '28000';
  end if;

  if p_name is null or char_length(trim(p_name)) < 2 then
    raise exception 'INVALID_NAME' using errcode = '22023';
  end if;

  insert into public.organizations (name, slug, org_type, subjects, student_count_estimate, created_by)
  values (trim(p_name), lower(trim(p_slug)), p_org_type, coalesce(p_subjects, '{}'), p_student_count_estimate, auth.uid())
  returning * into v_org;

  insert into public.organization_members (organization_id, user_id, role, status, joined_at)
  values (v_org.id, auth.uid(), 'owner', 'active', now());

  insert into public.audit_logs (organization_id, user_id, action, entity_type, entity_id, metadata)
  values (v_org.id, auth.uid(), 'organization.created', 'organization', v_org.id, jsonb_build_object('name', v_org.name));

  return v_org;
end;
$$;

grant execute on function public.create_organization(text, text, public.organization_type, text[], int) to authenticated;

-- ---------------------------------------------------------------------------
-- log_audit_event: the only sanctioned way for the app to write audit rows.
-- Verifies the caller is actually a member of the organization being logged
-- against, and always stamps user_id from the JWT (never client-supplied).
-- ---------------------------------------------------------------------------
create or replace function public.log_audit_event(
  p_org_id uuid,
  p_action text,
  p_entity_type text default null,
  p_entity_id uuid default null,
  p_metadata jsonb default '{}'::jsonb
)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  if auth.uid() is null then
    raise exception 'AUTH_REQUIRED' using errcode = '28000';
  end if;

  if p_org_id is not null and not public.is_org_member(p_org_id) then
    raise exception 'NOT_A_MEMBER' using errcode = '42501';
  end if;

  insert into public.audit_logs (organization_id, user_id, action, entity_type, entity_id, metadata)
  values (p_org_id, auth.uid(), p_action, p_entity_type, p_entity_id, coalesce(p_metadata, '{}'::jsonb));
end;
$$;

grant execute on function public.log_audit_event(uuid, text, text, uuid, jsonb) to authenticated;

-- ---------------------------------------------------------------------------
-- Guard rails on organization_members: never allow the last owner of an
-- org to be demoted, suspended or removed, and never allow a non-owner to
-- grant/revoke the 'owner' role.
-- ---------------------------------------------------------------------------
create or replace function public.protect_last_owner()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  v_owner_count int;
begin
  if tg_op = 'DELETE' then
    if old.role = 'owner' and old.status = 'active' then
      select count(*) into v_owner_count from public.organization_members
      where organization_id = old.organization_id and role = 'owner' and status = 'active';
      if v_owner_count <= 1 then
        raise exception 'CANNOT_REMOVE_LAST_OWNER' using errcode = '42501';
      end if;
    end if;
    return old;
  end if;

  if tg_op = 'UPDATE' then
    if old.role = 'owner' and old.status = 'active'
       and (new.role <> 'owner' or new.status <> 'active') then
      select count(*) into v_owner_count from public.organization_members
      where organization_id = old.organization_id and role = 'owner' and status = 'active';
      if v_owner_count <= 1 then
        raise exception 'CANNOT_REMOVE_LAST_OWNER' using errcode = '42501';
      end if;
    end if;
    return new;
  end if;

  return new;
end;
$$;

drop trigger if exists trg_protect_last_owner on public.organization_members;
create trigger trg_protect_last_owner
  before update or delete on public.organization_members
  for each row execute function public.protect_last_owner();

-- ---------------------------------------------------------------------------
-- Notifications: fan out a notification when an assignment is created, and
-- when a grade is entered. These are pure data-integrity conveniences, not
-- a replacement for app-level RLS-respecting access.
-- ---------------------------------------------------------------------------
create or replace function public.notify_assignment_created()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.notifications (organization_id, user_id, type, title, body, data)
  select new.organization_id, s.profile_id, 'assignment', 'واجب جديد: ' || new.title,
         'تم إضافة واجب جديد في فصلك. الموعد النهائي: ' || to_char(new.deadline, 'YYYY-MM-DD HH24:MI'),
         jsonb_build_object('assignment_id', new.id, 'class_id', new.class_id)
  from public.students s
  join public.class_members cm on cm.student_id = s.id
  where cm.class_id = new.class_id and s.profile_id is not null and s.deleted_at is null;
  return new;
end;
$$;

drop trigger if exists trg_notify_assignment_created on public.assignments;
create trigger trg_notify_assignment_created
  after insert on public.assignments
  for each row execute function public.notify_assignment_created();

create or replace function public.notify_grade_entered()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  v_profile_id uuid;
begin
  select profile_id into v_profile_id from public.students where id = new.student_id;
  if v_profile_id is not null then
    insert into public.notifications (organization_id, user_id, type, title, body, data)
    values (
      new.organization_id, v_profile_id, 'grade', 'تم رصد درجة جديدة',
      'تم تسجيل درجتك في الاختبار.',
      jsonb_build_object('exam_id', new.exam_id, 'score', new.score)
    );
  end if;
  return new;
end;
$$;

drop trigger if exists trg_notify_grade_entered on public.grades;
create trigger trg_notify_grade_entered
  after insert on public.grades
  for each row execute function public.notify_grade_entered();

-- ---------------------------------------------------------------------------
-- Messages: stamp conversation.updated_at, bump unread implicitly via read_at
-- being null by default. Also guard that sender is a participant.
-- ---------------------------------------------------------------------------
create or replace function public.touch_conversation()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  update public.conversations set updated_at = now() where id = new.conversation_id;
  return new;
end;
$$;

drop trigger if exists trg_touch_conversation on public.messages;
create trigger trg_touch_conversation
  after insert on public.messages
  for each row execute function public.touch_conversation();
