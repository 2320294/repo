-- ============================================================
-- FASE 4 - PARÂMETROS GERAIS DO PROJETO
-- Execute uma única vez no SQL Editor do Supabase.
-- ============================================================

alter table public.dados_projetos
    add column if not exists tensao_projeto integer default 127;

alter table public.dados_projetos
    add column if not exists pe_direito numeric(5,2) default 2.70;

-- Restringe a tensão aos valores usados atualmente pelo aplicativo.
alter table public.dados_projetos
    drop constraint if exists dados_projetos_tensao_projeto_check;

alter table public.dados_projetos
    add constraint dados_projetos_tensao_projeto_check
    check (tensao_projeto in (127, 220));

-- Pé-direito positivo e dentro de uma faixa prática para o aplicativo.
alter table public.dados_projetos
    drop constraint if exists dados_projetos_pe_direito_check;

alter table public.dados_projetos
    add constraint dados_projetos_pe_direito_check
    check (pe_direito >= 2.00 and pe_direito <= 10.00);
