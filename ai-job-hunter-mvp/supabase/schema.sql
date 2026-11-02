-- Execute in Supabase SQL Editor. Requires Supabase Auth for user-owned rows.
create extension if not exists pgcrypto;
create table if not exists candidate_profiles (
 user_id uuid primary key references auth.users(id) on delete cascade,
 profile jsonb not null,
 updated_at timestamptz not null default now()
);
create table if not exists jobs (
 id uuid primary key default gen_random_uuid(),
 source text not null,
 external_id text not null,
 company text not null,
 title text not null,
 location text,
 url text not null,
 description text,
 is_demo boolean not null default false,
 first_seen timestamptz not null default now(),
 unique(source,external_id)
);
create table if not exists job_matches (
 user_id uuid not null references auth.users(id) on delete cascade,
 job_id uuid not null references jobs(id) on delete cascade,
 score int not null check(score between 0 and 100),
 reasons jsonb not null default '{}'::jsonb,
 primary key(user_id,job_id)
);
create table if not exists applications (
 id uuid primary key default gen_random_uuid(),
 user_id uuid not null references auth.users(id) on delete cascade,
 job_external_id text not null,
 job_url text not null,
 cv_version text not null,
 answers jsonb not null default '{}'::jsonb,
 cover_letter text not null default '',
 status text not null default 'pending_approval' check(status in ('pending_approval','approved','rejected','submission_in_progress','submitted','failed')),
 approved_at timestamptz,
 submitted_at timestamptz,
 confirmation text,
 created_at timestamptz not null default now(),
 unique(user_id,job_external_id)
);
create table if not exists approval_events (
 id uuid primary key default gen_random_uuid(),
 application_id uuid not null references applications(id) on delete cascade,
 user_id uuid not null references auth.users(id) on delete cascade,
 decision text not null check(decision in ('approved','rejected')),
 payload_snapshot jsonb not null,
 created_at timestamptz not null default now()
);
create table if not exists submission_attempts (
 id uuid primary key default gen_random_uuid(),
 application_id uuid not null references applications(id) on delete cascade,
 result text not null,
 confirmation text,
 error_message text,
 created_at timestamptz not null default now()
);
alter table candidate_profiles enable row level security;
alter table jobs enable row level security;
alter table job_matches enable row level security;
alter table applications enable row level security;
alter table approval_events enable row level security;
alter table submission_attempts enable row level security;
create policy "own profile" on candidate_profiles for all to authenticated using (user_id=auth.uid()) with check (user_id=auth.uid());
create policy "read real jobs" on jobs for select to authenticated using (is_demo=false);
create policy "own matches" on job_matches for all to authenticated using (user_id=auth.uid()) with check (user_id=auth.uid());
create policy "own applications" on applications for select to authenticated using (user_id=auth.uid());
create policy "own approvals" on approval_events for select to authenticated using (user_id=auth.uid());
create policy "own attempts" on submission_attempts for select to authenticated using (exists(select 1 from applications a where a.id=application_id and a.user_id=auth.uid()));
-- All writes to applications/approvals/attempts should go through authenticated backend with verified JWT.
