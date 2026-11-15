{#
  Dataset "Museu" do modelo lógico do GoodData (foto atual, um por museu).
  Referencia gd_municipio por municipio_id. Museu sem município no cadastro
  entra com municipio_id nulo: some do recorte por UF ("vazio"), mas conta no
  total, que precisa bater com o painel.
#}

select
    museu_id,
    nome_museu,
    tipo_museu,
    tematica,
    status_funcionamento,
    natureza_administrativa,
    coalesce(nivel_governo, subtipo_privado, 'Não se aplica')   as perfil_administrativo,
    faixa_gestao,
    coalesce(cast(decada_abertura as varchar), 'Não informada') as decada_abertura,
    municipio_id,
    case when is_aberto then 1 else 0 end                       as is_aberto,
    indice_gestao,
    case when is_aberto then indice_gestao else 0 end           as indice_gestao_se_ativo,
    case when possui_plano_museologico then 1 else 0 end        as possui_plano_museologico,
    case when possui_plano_museologico is not null then 1 else 0 end as respondeu_plano_museologico,
    dimensoes_acessibilidade,
    case when dimensoes_acessibilidade = 0 then 1 else 0 end    as sem_acessibilidade,
    coalesce(qtd_pessoas_trabalham, 0)                          as qtd_pessoas_trabalham,
    coalesce(qtd_bens_culturais, 0)                             as qtd_bens_culturais
from {{ ref('int_museus__atual') }}
