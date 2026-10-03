-- =============================================================================
-- NEXORA — 0011: Dashboard summary functions (SECURITY INVOKER — RLS applies)
-- =============================================================================

create or replace function public.get_payment_summary(p_org_id uuid)
returns table (
  total_paid numeric,
  total_pending numeric,
  total_overdue numeric,
  revenue_this_month numeric,
  revenue_last_month numeric
)
language sql
stable
as $$
  select
    coalesce(sum(amount) filter (where status = 'paid'), 0),
    coalesce(sum(amount) filter (where status = 'pending'), 0),
    coalesce(sum(amount) filter (where status = 'overdue'), 0),
    coalesce(sum(amount) filter (where status = 'paid' and date_trunc('month', paid_at) = date_trunc('month', now())), 0),
    coalesce(sum(amount) filter (where status = 'paid' and date_trunc('month', paid_at) = date_trunc('month', now() - interval '1 month')), 0)
  from public.payments
  where organization_id = p_org_id;
$$;

create or replace function public.get_attendance_rate(p_org_id uuid, p_from date, p_to date)
returns numeric
language sql
stable
as $$
  select round(avg((status = 'present')::int) * 100, 1)
  from public.attendance
  where organization_id = p_org_id and date between p_from and p_to;
$$;

create or replace function public.get_performance_average(p_org_id uuid, p_from date, p_to date)
returns numeric
language sql
stable
as $$
  select round(avg(g.score / nullif(e.total_score, 0) * 100), 1)
  from public.grades g
  join public.exams e on e.id = g.exam_id
  where e.organization_id = p_org_id and e.date between p_from and p_to;
$$;

create or replace function public.get_org_dashboard_counts(p_org_id uuid)
returns table (
  active_students bigint,
  new_students_this_month bigint,
  new_students_last_month bigint,
  total_classes bigint
)
language sql
stable
as $$
  select
    count(*) filter (where status = 'active' and deleted_at is null),
    count(*) filter (where date_trunc('month', created_at) = date_trunc('month', now())),
    count(*) filter (where date_trunc('month', created_at) = date_trunc('month', now() - interval '1 month')),
    (select count(*) from public.classes where organization_id = p_org_id and deleted_at is null)
  from public.students
  where organization_id = p_org_id;
$$;

grant execute on function
  public.get_payment_summary(uuid),
  public.get_attendance_rate(uuid, date, date),
  public.get_performance_average(uuid, date, date),
  public.get_org_dashboard_counts(uuid)
to authenticated;
