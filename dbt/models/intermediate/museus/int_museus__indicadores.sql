{#
  Regras de negócio por museu (grão: museu x partição).

  Índice de gestão (0-100)
      Soma ponderada de seis critérios. Os pesos ficam no seed
      pesos_indice_gestao para a área de negócio poder ajustar sem mexer em SQL;
      o teste `soma_pesos_100` no seed garante que continuam somando 100.
      Critério não respondido conta como "não atende". O campo
      `criterios_respondidos` deixa explícito quanto do índice é informação e
      quanto é ausência de resposta.

  Acessibilidade
      Três dimensões: física, sensorial (auditiva/visual) e atendimento a
      estrangeiro. Uma dimensão conta se o museu declarou ao menos um recurso
      real nela; respostas do tipo "não possui" vêm misturadas na mesma lista e
      são removidas por lista_sem_negativas.
#}

with museus as (

    select * from {{ ref('stg_tainacan__museus') }}

),

pesos as (

    select
        max(case when criterio = 'plano_museologico'   then peso end) as p_plano,
        max(case when criterio = 'regimento_interno'   then peso end) as p_regimento,
        max(case when criterio = 'documentacao_acervo' then peso end) as p_documentacao,
        max(case when criterio = 'politica_aquisicao'  then peso end) as p_aquisicao,
        max(case when criterio = 'politica_descarte'   then peso end) as p_descarte,
        max(case when criterio = 'equipe_propria'      then peso end) as p_equipe
    from {{ ref('pesos_indice_gestao') }}

),

listas_limpas as (

    select
        museu_id,
        dt,
        {{ lista_sem_negativas('instrumentos_documentacao') }}          as instrumentos_documentacao_validos,
        {{ lista_sem_negativas('recursos_acessibilidade_fisica') }}     as acess_fisica_validos,
        {{ lista_sem_negativas('recursos_acessibilidade_sensorial') }}  as acess_sensorial_validos,
        {{ lista_sem_negativas('recursos_turista_estrangeiro') }}       as turista_validos
    from museus

),

criterios as (

    select
        m.museu_id,
        m.dt,
        coalesce(m.possui_plano_museologico, false)                                  as c_plano,
        coalesce(m.possui_regimento_interno, false)                                  as c_regimento,
        {{ tamanho_lista('l.instrumentos_documentacao_validos') }} > 0               as c_documentacao,
        coalesce(m.possui_politica_aquisicao, false)                                 as c_aquisicao,
        coalesce(m.possui_politica_descarte, false)                                  as c_descarte,
        coalesce(m.qtd_pessoas_trabalham, 0) > 0                                     as c_equipe,

        (case when m.possui_plano_museologico  is not null then 1 else 0 end
       + case when m.possui_regimento_interno  is not null then 1 else 0 end
       + case when {{ tamanho_lista('m.instrumentos_documentacao') }} > 0 then 1 else 0 end
       + case when m.possui_politica_aquisicao is not null then 1 else 0 end
       + case when m.possui_politica_descarte  is not null then 1 else 0 end
       + case when m.qtd_pessoas_trabalham     is not null then 1 else 0 end)       as criterios_respondidos,

        {{ tamanho_lista('l.acess_fisica_validos') }}                                as qtd_recursos_acess_fisica,
        {{ tamanho_lista('l.acess_sensorial_validos') }}                             as qtd_recursos_acess_sensorial,
        {{ tamanho_lista('l.turista_validos') }}                                     as qtd_recursos_turista,
        l.acess_fisica_validos,
        l.acess_sensorial_validos
    from museus as m
    inner join listas_limpas as l
        on l.museu_id = m.museu_id and l.dt = m.dt

)

select
    c.museu_id,
    c.dt,

    -- gestão
    c.c_plano       as atende_plano_museologico,
    c.c_regimento   as atende_regimento_interno,
    c.c_documentacao as atende_documentacao_acervo,
    c.c_aquisicao   as atende_politica_aquisicao,
    c.c_descarte    as atende_politica_descarte,
    c.c_equipe      as atende_equipe_propria,
    c.criterios_respondidos,
    cast(
          (case when c.c_plano        then p.p_plano        else 0 end)
        + (case when c.c_regimento    then p.p_regimento    else 0 end)
        + (case when c.c_documentacao then p.p_documentacao else 0 end)
        + (case when c.c_aquisicao    then p.p_aquisicao    else 0 end)
        + (case when c.c_descarte     then p.p_descarte     else 0 end)
        + (case when c.c_equipe       then p.p_equipe       else 0 end)
    as integer) as indice_gestao,

    -- acessibilidade
    c.qtd_recursos_acess_fisica,
    c.qtd_recursos_acess_sensorial,
    c.qtd_recursos_turista,
    c.acess_fisica_validos      as recursos_acessibilidade_fisica,
    c.acess_sensorial_validos   as recursos_acessibilidade_sensorial,
    (case when c.qtd_recursos_acess_fisica    > 0 then 1 else 0 end
   + case when c.qtd_recursos_acess_sensorial > 0 then 1 else 0 end
   + case when c.qtd_recursos_turista         > 0 then 1 else 0 end) as dimensoes_acessibilidade

from criterios as c
cross join pesos as p
