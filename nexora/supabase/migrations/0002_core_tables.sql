-- =============================================================================
-- NEXORA — 0002: Core multi-tenant tables (organizations, profiles, membership)
-- =============================================================================

-- ---------------------------------------------------------------------------
-- profiles: 1:1 extension of auth.users. Created automatically by a trigger
-- (see 0003_functions_triggers.sql) the moment a user signs up.
-- ---------------------------------------------------------------------------
create table if not exists public.profiles (
  id          uuid primary key references auth.users (id) on delete cascade,
  full_name   text not null default '' check (char_length(full_name) <= 150),
  avatar_url  text,
  phone       text check (phone is null or phone ~ '^\+?[0-9\s\-()]{6,20}$'),
  locale      text not null default 'ar' check (locale in ('ar', 'en')),
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

comment on table public.profiles is 'Public profile data mirrored from auth.users. One row per authenticated user.';

-- ---------------------------------------------------------------------------
-- organizations: the tenant boundary. Every piece of operational data hangs
-- off organization_id.
-- ---------------------------------------------------------------------------
create table if not exists public.organizations (
  id            uuid primary key default gen_random_uuid(),
  name          text not null check (char_length(trim(name)) between 2 and 120),
  slug          citext not null unique check (slug ~ '^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$'),
  logo_url      text,
  org_type      public.organization_type not null default 'other',
  subjects      text[] not null default '{}',
  student_count_estimate int check (student_count_estimate is null or student_count_estimate >= 0),
  settings      jsonb not null default '{}'::jsonb,
  created_by    uuid references auth.users (id) on delete set null,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  deleted_at    timestamptz
);

create index if not exists idx_organizations_deleted_at on public.organizations (deleted_at);

comment on table public.organizations is 'Tenant root. All org-owned tables reference organizations.id.';

-- ---------------------------------------------------------------------------
-- organization_members: membership + role-based access control anchor.
-- ---------------------------------------------------------------------------
create table if not exists public.organization_members (
  id              uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations (id) on delete cascade,
  user_id         uuid references auth.users (id) on delete cascade,
  role            public.org_role not null,
  status          public.member_status not null default 'invited',
  invited_email   citext,
  invited_by      uuid references auth.users (id) on delete set null,
  joined_at       timestamptz,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  constraint organization_members_identity check (user_id is not null or invited_email is not null),
  constraint organization_members_unique_user unique (organization_id, user_id)
);

create unique index if not exists idx_org_members_unique_invite
  on public.organization_members (organization_id, invited_email)
  where invited_email is not null and user_id is null;

create index if not exists idx_org_members_org on public.organization_members (organization_id);
create index if not exists idx_org_members_user on public.organization_members (user_id);
create index if not exists idx_org_members_role on public.organization_members (organization_id, role);

comment on table public.organization_members is 'Links a user to an organization with exactly one role. Unique(org, user).';

-- ---------------------------------------------------------------------------
-- guardians: links parent accounts to the students they are responsible for.
-- Required to correctly scope "parent" role visibility (not in the original
-- minimal table list, but necessary for the Parent role to work securely).
-- ---------------------------------------------------------------------------
create table if not exists public.guardians (
  id              uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations (id) on delete cascade,
  student_id      uuid not null, -- FK added in 0003 after students table exists
  parent_user_id  uuid not null references auth.users (id) on delete cascade,
  relationship    text not null default 'parent' check (char_length(relationship) <= 40),
  created_at      timestamptz not null default now(),
  constraint guardians_unique unique (student_id, parent_user_id)
);

create index if not exists idx_guardians_org on public.guardians (organization_id);
create index if not exists idx_guardians_parent on public.guardians (parent_user_id);
