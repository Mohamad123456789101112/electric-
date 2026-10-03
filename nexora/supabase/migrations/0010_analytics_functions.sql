-- =============================================================================
-- NEXORA — 0010: Analytics helper functions (SECURITY INVOKER by default)
-- =============================================================================
-- Unlike the helpers in 0005, these run with the CALLER's privileges (default
-- Postgres behaviour — no `security definer`). That means every underlying
-- SELECT is still filtered by the normal RLS policies on students/grades/
-- attendance/etc. Passing someone else's organization_id here simply returns
-- an empty result set, because the caller has no visibility into those rows
-- — tenant isolation is enforced by the same RLS the rest of the app relies
-- on, not by extra logic in here.
-- =============================================================================

create or replace function public.get_declining_students(p_org_id uuid, p_limit int default 8)
returns table (
  student_id uuid,
  full_name text,
  student_code text,
  class_id uuid,
  class_name text,
  previous_avg numeric,
  recent_avg numeric,
  change_pct numeric
)
language sql
stable
as $$
  with scored as (
    select
      g.student_id,
      e.date,
      g.score / nullif(e.total_score, 0) * 100 as pct,
      row_number() over (partition by g.student_id order by e.date desc) as rn
    from public.grades g
    join public.exams e on e.id = g.exam_id
    where e.organization_id = p_org_id
  ),
  recent as (
    select student_id, avg(pct) as recent_avg from scored where rn <= 2 group by student_id
  ),
  previous as (
    select student_id, avg(pct) as previous_avg from scored where rn > 2 and rn <= 4 group by student_id
  )
  select
    s.id, s.full_name, s.student_code, s.class_id, c.name,
    round(previous.previous_avg, 1), round(recent.recent_avg, 1),
    round(recent.recent_avg - previous.previous_avg, 1) as change_pct
  from recent
  join previous using (student_id)
  join public.students s on s.id = recent.student_id
  left join public.classes c on c.id = s.class_id
  where recent.recent_avg < previous.previous_avg
    and s.deleted_at is null
  order by change_pct asc
  limit p_limit;
$$;

create or replace function public.get_missing_submissions(p_org_id uuid, p_limit int default 8)
returns table (
  assignment_id uuid,
  assignment_title text,
  class_id uuid,
  class_name text,
  deadline timestamptz,
  missing_count bigint
)
language sql
stable
as $$
  select
    a.id, a.title, a.class_id, c.name, a.deadline,
    count(cm.student_id) filter (
      where not exists (
        select 1 from public.submissions sub
        where sub.assignment_id = a.id and sub.student_id = cm.student_id and sub.status in ('submitted', 'graded', 'late')
      )
    ) as missing_count
  from public.assignments a
  join public.classes c on c.id = a.class_id
  join public.class_members cm on cm.class_id = a.class_id
  where a.organization_id = p_org_id and a.deleted_at is null and a.deadline < now()
  group by a.id, a.title, a.class_id, c.name, a.deadline
  having count(cm.student_id) filter (
    where not exists (
      select 1 from public.submissions sub
      where sub.assignment_id = a.id and sub.student_id = cm.student_id and sub.status in ('submitted', 'graded', 'late')
    )
  ) > 0
  order by a.deadline desc
  limit p_limit;
$$;

create or replace function public.get_classes_needing_review(p_org_id uuid, p_limit int default 5)
returns table (
  class_id uuid,
  class_name text,
  avg_score numeric,
  attendance_rate numeric,
  student_count bigint
)
language sql
stable
as $$
  with class_scores as (
    select c.id, avg(g.score / nullif(e.total_score, 0) * 100) as avg_score
    from public.classes c
    join public.exams e on e.class_id = c.id
    join public.grades g on g.exam_id = e.id
    where c.organization_id = p_org_id and c.deleted_at is null
    group by c.id
  ),
  class_attendance as (
    select class_id, avg((status = 'present')::int) * 100 as attendance_rate
    from public.attendance
    where organization_id = p_org_id and date >= (current_date - interval '30 days')
    group by class_id
  ),
  class_counts as (
    select class_id, count(*) as student_count from public.class_members group by class_id
  )
  select c.id, c.name, round(cs.avg_score, 1), round(ca.attendance_rate, 1), coalesce(cc.student_count, 0)
  from public.classes c
  left join class_scores cs on cs.id = c.id
  left join class_attendance ca on ca.class_id = c.id
  left join class_counts cc on cc.class_id = c.id
  where c.organization_id = p_org_id and c.deleted_at is null
    and (coalesce(cs.avg_score, 100) < 65 or coalesce(ca.attendance_rate, 100) < 75)
  order by least(coalesce(cs.avg_score, 100), coalesce(ca.attendance_rate, 100)) asc
  limit p_limit;
$$;

create or replace function public.get_exam_statistics(p_exam_id uuid)
returns table (
  average numeric,
  median numeric,
  highest numeric,
  lowest numeric,
  graded_count bigint,
  total_score numeric
)
language sql
stable
as $$
  select
    round(avg(g.score), 2),
    round(percentile_cont(0.5) within group (order by g.score), 2),
    max(g.score),
    min(g.score),
    count(*),
    max(e.total_score)
  from public.grades g
  join public.exams e on e.id = g.exam_id
  where g.exam_id = p_exam_id;
$$;

grant execute on function
  public.get_declining_students(uuid, int),
  public.get_missing_submissions(uuid, int),
  public.get_classes_needing_review(uuid, int),
  public.get_exam_statistics(uuid)
to authenticated;
