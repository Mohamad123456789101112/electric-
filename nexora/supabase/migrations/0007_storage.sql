-- =============================================================================
-- NEXORA — 0007: Storage buckets & policies
-- =============================================================================
-- Path conventions (enforced by both the app and these policies):
--   avatars/{user_id}/{filename}
--   org-logos/{organization_id}/{filename}
--   assignment-files/{organization_id}/{assignment_id}/{filename}
--   submission-files/{organization_id}/{assignment_id}/{student_id}/{filename}
--
-- Only "avatars" and "org-logos" are public-read (profile pictures / org
-- branding shown across the UI). Assignment and submission files are PRIVATE
-- and must be fetched through signed URLs generated server-side after an
-- authorization check — see src/lib/supabase/signed-url.ts.
-- =============================================================================

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values
  ('avatars', 'avatars', true, 5242880, array['image/png','image/jpeg','image/webp']),
  ('org-logos', 'org-logos', true, 5242880, array['image/png','image/jpeg','image/webp','image/svg+xml']),
  ('assignment-files', 'assignment-files', false, 26214400,
     array['application/pdf','image/png','image/jpeg','image/webp',
           'application/msword',
           'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
           'application/vnd.ms-powerpoint',
           'application/vnd.openxmlformats-officedocument.presentationml.presentation',
           'text/plain']),
  ('submission-files', 'submission-files', false, 26214400,
     array['application/pdf','image/png','image/jpeg','image/webp',
           'application/msword',
           'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
           'application/zip',
           'text/plain'])
on conflict (id) do update set
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

-- ---------------------------------------------------------------------------
-- avatars: public read, write restricted to the user's own folder.
-- ---------------------------------------------------------------------------
create policy avatars_public_read on storage.objects
  for select to authenticated, anon
  using (bucket_id = 'avatars');

create policy avatars_owner_write on storage.objects
  for insert to authenticated
  with check (bucket_id = 'avatars' and (storage.foldername(name))[1] = auth.uid()::text);

create policy avatars_owner_update on storage.objects
  for update to authenticated
  using (bucket_id = 'avatars' and (storage.foldername(name))[1] = auth.uid()::text)
  with check (bucket_id = 'avatars' and (storage.foldername(name))[1] = auth.uid()::text);

create policy avatars_owner_delete on storage.objects
  for delete to authenticated
  using (bucket_id = 'avatars' and (storage.foldername(name))[1] = auth.uid()::text);

-- ---------------------------------------------------------------------------
-- org-logos: public read, write restricted to org admins/owners.
-- ---------------------------------------------------------------------------
create policy org_logos_public_read on storage.objects
  for select to authenticated, anon
  using (bucket_id = 'org-logos');

create policy org_logos_admin_write on storage.objects
  for insert to authenticated
  with check (
    bucket_id = 'org-logos'
    and public.is_org_admin(((storage.foldername(name))[1])::uuid)
  );

create policy org_logos_admin_update on storage.objects
  for update to authenticated
  using (bucket_id = 'org-logos' and public.is_org_admin(((storage.foldername(name))[1])::uuid))
  with check (bucket_id = 'org-logos' and public.is_org_admin(((storage.foldername(name))[1])::uuid));

create policy org_logos_admin_delete on storage.objects
  for delete to authenticated
  using (bucket_id = 'org-logos' and public.is_org_admin(((storage.foldername(name))[1])::uuid));

-- ---------------------------------------------------------------------------
-- assignment-files: private. Readable by org admins/teachers of the class and
-- students/guardians enrolled in that class. Writable by staff only.
-- Path: {organization_id}/{assignment_id}/{filename}
-- ---------------------------------------------------------------------------
create policy assignment_files_select on storage.objects
  for select to authenticated
  using (
    bucket_id = 'assignment-files'
    and (
      public.is_org_admin(((storage.foldername(name))[1])::uuid)
      or exists (
        select 1 from public.assignments a
        where a.id = ((storage.foldername(name))[2])::uuid
          and public.is_class_teacher(a.class_id)
      )
      or exists (
        select 1 from public.assignments a
        join public.class_members cm on cm.class_id = a.class_id
        where a.id = ((storage.foldername(name))[2])::uuid
          and (public.is_student_self(cm.student_id) or public.is_guardian_of(cm.student_id))
      )
    )
  );

create policy assignment_files_write on storage.objects
  for insert to authenticated
  with check (
    bucket_id = 'assignment-files'
    and (
      public.is_org_admin(((storage.foldername(name))[1])::uuid)
      or exists (
        select 1 from public.assignments a
        where a.id = ((storage.foldername(name))[2])::uuid
          and public.is_class_teacher(a.class_id)
      )
    )
  );

create policy assignment_files_delete on storage.objects
  for delete to authenticated
  using (
    bucket_id = 'assignment-files'
    and (
      public.is_org_admin(((storage.foldername(name))[1])::uuid)
      or exists (
        select 1 from public.assignments a
        where a.id = ((storage.foldername(name))[2])::uuid
          and public.is_class_teacher(a.class_id)
      )
    )
  );

-- ---------------------------------------------------------------------------
-- submission-files: private. Student owns their own submission folder; staff
-- of the related class can read all submissions for grading.
-- Path: {organization_id}/{assignment_id}/{student_id}/{filename}
-- ---------------------------------------------------------------------------
create policy submission_files_select on storage.objects
  for select to authenticated
  using (
    bucket_id = 'submission-files'
    and (
      public.is_org_admin(((storage.foldername(name))[1])::uuid)
      or public.is_student_self(((storage.foldername(name))[3])::uuid)
      or public.is_guardian_of(((storage.foldername(name))[3])::uuid)
      or exists (
        select 1 from public.assignments a
        where a.id = ((storage.foldername(name))[2])::uuid
          and public.is_class_teacher(a.class_id)
      )
    )
  );

create policy submission_files_write on storage.objects
  for insert to authenticated
  with check (
    bucket_id = 'submission-files'
    and (
      public.is_student_self(((storage.foldername(name))[3])::uuid)
      or public.is_org_admin(((storage.foldername(name))[1])::uuid)
      or exists (
        select 1 from public.assignments a
        where a.id = ((storage.foldername(name))[2])::uuid
          and public.is_class_teacher(a.class_id)
      )
    )
  );

create policy submission_files_delete on storage.objects
  for delete to authenticated
  using (
    bucket_id = 'submission-files'
    and (
      public.is_student_self(((storage.foldername(name))[3])::uuid)
      or public.is_org_admin(((storage.foldername(name))[1])::uuid)
    )
  );
