-- =============================================================================
-- NEXORA — 0009: Member invitations
-- =============================================================================
-- Invited members are created with user_id = null and invited_email set.
-- When the invited person signs up/logs in with a matching email, this
-- function links their auth user id to the pending membership row. It is
-- SECURITY DEFINER so it can bridge the "no user_id yet" row, but it only
-- ever matches on the caller's OWN verified JWT email — never a client-
-- supplied one — so it cannot be used to hijack someone else's invite.
-- =============================================================================

create or replace function public.accept_pending_invites()
returns setof public.organization_members
language plpgsql
security definer
set search_path = public
as $$
declare
  v_email citext;
begin
  if auth.uid() is null then
    raise exception 'AUTH_REQUIRED' using errcode = '28000';
  end if;

  select email into v_email from auth.users where id = auth.uid();
  if v_email is null then
    return;
  end if;

  return query
  update public.organization_members
     set user_id = auth.uid(), status = 'active', joined_at = now(), invited_email = null
   where invited_email = v_email and user_id is null
  returning *;
end;
$$;

grant execute on function public.accept_pending_invites() to authenticated;
