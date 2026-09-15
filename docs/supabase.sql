-- 서버 전용 백업 테이블. 기존 DAMAGOCHI 저장 테이블과 분리한다.
create table if not exists public.shinsu_backups (
    id text primary key,
    save_data jsonb not null,
    updated_at timestamptz not null default now()
);
alter table public.shinsu_backups enable row level security;
revoke all on public.shinsu_backups from anon, authenticated;
grant select, insert, update on public.shinsu_backups to service_role;
