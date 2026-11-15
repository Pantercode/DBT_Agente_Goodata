{% docs __overview__ %}
# Museus do Brasil

Camada analítica sobre o **Cadastro Nacional de Museus (MuseusBr / Ibram)**,
cruzada com malha municipal e população do **IBGE (Censo 2022)**.

Camadas:

| camada | schema | materialização | papel |
|---|---|---|---|
| raw | `raw` | view / external table | o lake como veio da API |
| staging | `staging` | view | renomear, tipar, limpar |
| intermediate | `intermediate` | view | regras de negócio e junções |
| marts | `auditoria` -> `publicado` | table / incremental | consumo (WAP) |

Consumidores leem **só** `publicado`. Ver `docs/arquitetura.md` no repositório.
{% enddocs %}


{% docs museu_ativo %}
Museu com status de funcionamento **"Aberto"** no cadastro. É a definição usada em
toda métrica de cobertura. Museu fechado, em implantação ou sem status conta em
`qtd_museus_cadastrados`, nunca em `qtd_museus_ativos`.
{% enddocs %}


{% docs indice_gestao %}
Índice de gestão museológica, de 0 a 100. Soma ponderada de seis critérios do
formulário de cadastro, com pesos no seed `pesos_indice_gestao`:

| critério | peso |
|---|---|
| plano museológico | 30 |
| regimento interno | 20 |
| instrumento de documentação do acervo | 15 |
| política de aquisição | 15 |
| política de descarte | 10 |
| equipe própria (≥ 1 pessoa) | 10 |

Critério não respondido conta como não atendido. Faixas: **Estruturada** (≥ 70),
**Em estruturação** (40-69), **Incipiente** (1-39), **Sem instrumentos** (0).
{% enddocs %}


{% docs museus_por_100k %}
Museus ativos por 100 mil habitantes: `qtd_museus_ativos * 100000 / populacao`.
População do Censo 2022. Em agregações acima do grão da tabela, **recalcule com
numerador e denominador**; não tire média de razões.
{% enddocs %}


{% docs dt %}
Data da partição de extração no lake (`dt=AAAA-MM-DD`). Não é a data de
atualização na origem; para isso use `atualizado_na_origem_em`.
{% enddocs %}
