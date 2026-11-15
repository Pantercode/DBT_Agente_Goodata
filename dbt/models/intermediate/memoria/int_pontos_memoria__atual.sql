{# Pontos de Memória na partição válida mais recente, com região do IBGE. #}

with ultima_valida as (

    select max(dt) as dt
    from {{ ref('int_particoes__validacao') }}
    where fonte = 'pontos_memoria' and status = 'valida'

),

pontos as (

    select *
    from {{ ref('stg_tainacan__pontos_memoria') }}
    where dt = (select dt from ultima_valida)

),

ufs as (

    select distinct uf_sigla, uf_nome, regiao_sigla, regiao_nome
    from {{ ref('stg_ibge__municipios') }}

)

select
    p.ponto_memoria_id,
    p.nome_ponto,
    p.tematicas,
    p.tipo_entidade,
    p.natureza_juridica,
    p.criado_em,
    p.uf_sigla,
    u.regiao_sigla,
    u.regiao_nome,
    p.latitude,
    p.longitude,
    p.possui_acervo,
    p.acervo_inventariado,
    p.possui_acervo_digital,
    p.fez_inventario_participativo,
    p.possui_sede_propria,
    p.sede_aberta_ao_publico,
    p.contemplado_edital_ibram,
    p.participa_de_rede,
    p.tem_parceria_poder_publico,
    p.promove_atividades_regulares,
    p.dt
from pontos as p
left join ufs as u
    on u.uf_sigla = p.uf_sigla
