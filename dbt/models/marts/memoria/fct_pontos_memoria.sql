{# Pontos de Memória ativos no cadastro (foto atual), um por linha. #}

select
    ponto_memoria_id,
    nome_ponto,
    uf_sigla,
    regiao_sigla,
    latitude,
    longitude,
    criado_em,
    extract(year from criado_em)            as ano_criacao,
    possui_acervo,
    possui_acervo_digital,
    fez_inventario_participativo,
    possui_sede_propria,
    contemplado_edital_ibram,
    participa_de_rede,
    tem_parceria_poder_publico,
    {{ tamanho_lista('tematicas') }}        as qtd_tematicas,
    tematicas,
    dt                                      as dt_referencia
from {{ ref('int_pontos_memoria__atual') }}
