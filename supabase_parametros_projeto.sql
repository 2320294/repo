-- ============================================================
-- PARÂMETROS GERAIS DO PROJETO
-- Execute UMA VEZ no SQL Editor do Supabase.
-- ============================================================

alter table public.dados_projetos
    add column if not exists tensao_projeto integer default 110;

alter table public.dados_projetos
    add column if not exists pe_direito numeric(5,2) default 2.80;

update public.dados_projetos
set tensao_projeto = 110
where tensao_projeto is null;

update public.dados_projetos
set pe_direito = 2.80
where pe_direito is null;

update public.dados_projetos
set tensao_projeto = 110
where tensao_projeto = 127;

alter table public.dados_projetos
    drop constraint if exists dados_projetos_tensao_projeto_check;

alter table public.dados_projetos
    add constraint dados_projetos_tensao_projeto_check
    check (tensao_projeto in (110, 220));

alter table public.dados_projetos
    drop constraint if exists dados_projetos_pe_direito_check;

alter table public.dados_projetos
    add constraint dados_projetos_pe_direito_check
    check (pe_direito >= 2.00 and pe_direito <= 10.00);
