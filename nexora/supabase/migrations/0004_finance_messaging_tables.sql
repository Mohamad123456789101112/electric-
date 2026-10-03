-- =============================================================================
-- NEXORA — 0004: Finance, messaging, notifications, audit, files, billing
-- =============================================================================

-- ---------------------------------------------------------------------------
-- payments
-- ---------------------------------------------------------------------------
create table if not exists public.payments (
  id               uuid primary key default gen_random_uuid(),
  organization_id  uuid not null references public.organizations (id) on delete cascade,
  student_id       uuid not null references public.students (id) on delete cascade,
  amount           numeric(10, 2) not null check (amount > 0),
  currency         text not null default 'EGP' check (char_length(currency) = 3),
  due_date         date,
  paid_at          timestamptz,
  status           public.payment_status not null default 'pending',
  payment_method   public.payment_method,
  invoice_number   text,
  notes            text,
  created_by       uuid references auth.users (id) on delete set null,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now(),
  constraint payments_paid_consistency check (
    (status = 'paid' and paid_at is not null) or (status <> 'paid')
  )
);

create index if not exists idx_payments_org on public.payments (organization_id);
create index if not exists idx_payments_student on public.payments (student_id);
create index if not exists idx_payments_status on public.payments (organization_id, status);
create index if not exists idx_payments_due on public.payments (organization_id, due_date);

-- ---------------------------------------------------------------------------
-- conversations + participants + messages
-- ---------------------------------------------------------------------------
create table if not exists public.conversations (
  id               uuid primary key default gen_random_uuid(),
  organization_id  uuid not null references public.organizations (id) on delete cascade,
  type             public.conversation_type not null default 'direct',
  title            text,
  created_by       uuid references auth.users (id) on delete set null,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);

create index if not exists idx_conversations_org on public.conversations (organization_id);

create table if not exists public.conversation_participants (
  id               uuid primary key default gen_random_uuid(),
  conversation_id  uuid not null references public.conversations (id) on delete cascade,
  user_id          uuid not null references auth.users (id) on delete cascade,
  last_read_at     timestamptz,
  created_at       timestamptz not null default now(),
  constraint conversation_participants_unique unique (conversation_id, user_id)
);

create index if not exists idx_conv_participants_user on public.conversation_participants (user_id);
create index if not exists idx_conv_participants_conv on public.conversation_participants (conversation_id);

create table if not exists public.messages (
  id               uuid primary key default gen_random_uuid(),
  organization_id  uuid not null references public.organizations (id) on delete cascade,
  conversation_id  uuid not null references public.conversations (id) on delete cascade,
  sender_id        uuid not null references auth.users (id) on delete cascade,
  receiver_id      uuid references auth.users (id) on delete set null,
  content          text not null check (char_length(content) between 1 and 5000),
  attachment_path  text,
  read_at          timestamptz,
  created_at       timestamptz not null default now()
);

create index if not exists idx_messages_conversation on public.messages (conversation_id, created_at);
create index if not exists idx_messages_org on public.messages (organization_id);
create index if not exists idx_messages_receiver_unread on public.messages (receiver_id) where read_at is null;

-- ---------------------------------------------------------------------------
-- notifications
-- ---------------------------------------------------------------------------
create table if not exists public.notifications (
  id               uuid primary key default gen_random_uuid(),
  organization_id  uuid not null references public.organizations (id) on delete cascade,
  user_id          uuid not null references auth.users (id) on delete cascade,
  type             public.notification_type not null default 'info',
  title            text not null check (char_length(title) <= 200),
  body             text,
  data             jsonb not null default '{}'::jsonb,
  read_at          timestamptz,
  created_at       timestamptz not null default now()
);

create index if not exists idx_notifications_user on public.notifications (user_id, created_at desc);
create index if not exists idx_notifications_unread on public.notifications (user_id) where read_at is null;

-- ---------------------------------------------------------------------------
-- files (metadata catalog over Supabase Storage objects)
-- ---------------------------------------------------------------------------
create table if not exists public.files (
  id               uuid primary key default gen_random_uuid(),
  organization_id  uuid not null references public.organizations (id) on delete cascade,
  owner_id         uuid references auth.users (id) on delete set null,
  bucket_id        text not null,
  object_path      text not null,
  filename         text not null,
  mime_type        text not null,
  size_bytes       bigint not null check (size_bytes >= 0 and size_bytes <= 26214400), -- 25MB hard ceiling
  entity_type      text check (entity_type in ('avatar', 'org_logo', 'assignment', 'submission', 'other')),
  entity_id        uuid,
  created_at       timestamptz not null default now(),
  deleted_at       timestamptz,
  constraint files_unique_object unique (bucket_id, object_path)
);

create index if not exists idx_files_org on public.files (organization_id);
create index if not exists idx_files_entity on public.files (entity_type, entity_id);

-- ---------------------------------------------------------------------------
-- audit_logs — append-only security/action trail
-- ---------------------------------------------------------------------------
create table if not exists public.audit_logs (
  id               uuid primary key default gen_random_uuid(),
  organization_id  uuid references public.organizations (id) on delete cascade,
  user_id          uuid references auth.users (id) on delete set null,
  action           text not null check (char_length(action) <= 100),
  entity_type      text check (entity_type is null or char_length(entity_type) <= 60),
  entity_id        uuid,
  metadata         jsonb not null default '{}'::jsonb,
  ip_address       inet,
  user_agent       text,
  created_at       timestamptz not null default now()
);

create index if not exists idx_audit_org_created on public.audit_logs (organization_id, created_at desc);
create index if not exists idx_audit_user on public.audit_logs (user_id, created_at desc);
create index if not exists idx_audit_action on public.audit_logs (action);

-- ---------------------------------------------------------------------------
-- billing architecture (plans catalog is global; subscriptions are per-org)
-- No payment gateway is wired up — this only models the SaaS plan structure.
-- ---------------------------------------------------------------------------
create table if not exists public.plans (
  id               uuid primary key default gen_random_uuid(),
  code             text not null unique check (code in ('starter', 'pro', 'business')),
  name             text not null,
  description      text,
  price_monthly    numeric(10, 2) not null default 0,
  currency         text not null default 'USD',
  max_students     int, -- null = unlimited
  max_teachers     int,
  features         jsonb not null default '[]'::jsonb,
  is_active        boolean not null default true,
  created_at       timestamptz not null default now()
);

create table if not exists public.organization_subscriptions (
  id                  uuid primary key default gen_random_uuid(),
  organization_id     uuid not null references public.organizations (id) on delete cascade,
  plan_id             uuid not null references public.plans (id),
  status              public.subscription_status not null default 'trialing',
  current_period_end  timestamptz,
  provider            text, -- e.g. 'stripe' once wired up; null today
  provider_ref        text,
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now(),
  constraint org_subscriptions_unique_org unique (organization_id)
);

create index if not exists idx_org_subscriptions_org on public.organization_subscriptions (organization_id);
