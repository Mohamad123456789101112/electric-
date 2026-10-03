-- =============================================================================
-- NEXORA — 0001: Extensions & Enumerated Types
-- =============================================================================
-- This migration enables required extensions and defines every enum type used
-- across the schema. Enums give us cheap, indexable, constrained values instead
-- of free-text columns (defense in depth against invalid/garbage state).
-- =============================================================================

create extension if not exists "pgcrypto";      -- gen_random_uuid()
create extension if not exists "citext";        -- case-insensitive text (emails/slugs)

-- ---------------------------------------------------------------------------
-- Enums
-- ---------------------------------------------------------------------------

do $$ begin
  create type public.org_role as enum ('owner', 'admin', 'teacher', 'accountant', 'student', 'parent');
exception when duplicate_object then null; end $$;

do $$ begin
  create type public.member_status as enum ('invited', 'active', 'suspended');
exception when duplicate_object then null; end $$;

do $$ begin
  create type public.organization_type as enum ('school', 'academy', 'tutoring_center', 'individual_tutor', 'other');
exception when duplicate_object then null; end $$;

do $$ begin
  create type public.student_status as enum ('active', 'inactive', 'graduated', 'archived');
exception when duplicate_object then null; end $$;

do $$ begin
  create type public.attendance_status as enum ('present', 'absent', 'late', 'excused');
exception when duplicate_object then null; end $$;

do $$ begin
  create type public.submission_status as enum ('not_submitted', 'submitted', 'late', 'graded', 'missing');
exception when duplicate_object then null; end $$;

do $$ begin
  create type public.payment_status as enum ('pending', 'paid', 'overdue', 'cancelled', 'refunded');
exception when duplicate_object then null; end $$;

do $$ begin
  create type public.payment_method as enum ('cash', 'bank_transfer', 'card', 'wallet', 'other');
exception when duplicate_object then null; end $$;

do $$ begin
  create type public.notification_type as enum (
    'info', 'assignment', 'grade', 'payment', 'attendance', 'message', 'security', 'system'
  );
exception when duplicate_object then null; end $$;

do $$ begin
  create type public.conversation_type as enum ('direct', 'group');
exception when duplicate_object then null; end $$;

do $$ begin
  create type public.subscription_status as enum ('trialing', 'active', 'past_due', 'canceled');
exception when duplicate_object then null; end $$;
