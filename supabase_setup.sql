-- 旦旦物理 · AI教学工作台 V1.1
-- 在 Supabase Dashboard -> SQL Editor 中执行一次。

create table if not exists public.teacher_workspaces (
  user_id uuid primary key references auth.users(id) on delete cascade,
  workspace jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

alter table public.teacher_workspaces enable row level security;

drop policy if exists "teachers_select_own_workspace" on public.teacher_workspaces;
create policy "teachers_select_own_workspace"
on public.teacher_workspaces for select
to authenticated
using (auth.uid() = user_id);

drop policy if exists "teachers_insert_own_workspace" on public.teacher_workspaces;
create policy "teachers_insert_own_workspace"
on public.teacher_workspaces for insert
to authenticated
with check (auth.uid() = user_id);

drop policy if exists "teachers_update_own_workspace" on public.teacher_workspaces;
create policy "teachers_update_own_workspace"
on public.teacher_workspaces for update
to authenticated
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

grant select, insert, update on table public.teacher_workspaces to authenticated;

create or replace function public.set_workspace_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists trg_workspace_updated_at on public.teacher_workspaces;
create trigger trg_workspace_updated_at
before update on public.teacher_workspaces
for each row execute function public.set_workspace_updated_at();
