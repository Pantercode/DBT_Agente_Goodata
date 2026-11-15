{# Conversões de domínio usadas no staging. Não dependem de engine. #}

{# "Sim" / "Não" / "Sim, SOMENTE mediante agendamento" -> boolean. Qualquer outra coisa -> null. #}
{% macro sim_nao(expr) -%}
    case
        when lower(trim({{ expr }})) like 'sim%' then true
        when lower(trim({{ expr }})) like 'n_o%' then false
    end
{%- endmacro %}


{#
  Inteiro informado em campo livre: "2", " 12 ", "1.200", "aprox 30".
  Pega o primeiro grupo de dígitos (ignorando separador de milhar) e descarta o
  que estiver fora do intervalo plausível.
#}
{% macro inteiro_livre(expr, minimo=0, maximo=1000000) -%}
    case
        when try_cast(regexp_replace(regexp_extract({{ expr }}, '[0-9][0-9.]*', 0), '\.', '', 'g') as bigint)
             between {{ minimo }} and {{ maximo }}
        then try_cast(regexp_replace(regexp_extract({{ expr }}, '[0-9][0-9.]*', 0), '\.', '', 'g') as bigint)
    end
{%- endmacro %}


{# Valor monetário em campo livre: "10", "10,50", "R$ 5,00". #}
{#
  Coordenada "lat,lon" ou "lat, lon". Retorna a parte pedida (1 = lat, 2 = lon)
  só se o par cair no retângulo do Brasil; há cadastros com lat/lon trocados
  ou com 0,0.
#}
{% macro coordenada(expr, parte) -%}
    case
        when try_cast(trim(split_part({{ expr }}, ',', 1)) as double) between -34.0 and 5.5
         and try_cast(trim(split_part({{ expr }}, ',', 2)) as double) between -74.5 and -28.5
        then round(try_cast(trim(split_part({{ expr }}, ',', {{ parte }})) as double), 6)
    end
{%- endmacro %}


{% macro decimal_livre(expr) -%}
    try_cast(replace(regexp_extract(replace({{ expr }}, '.', ''), '[0-9]+(,[0-9]+)?', 0), ',', '.') as decimal(10, 2))
{%- endmacro %}
