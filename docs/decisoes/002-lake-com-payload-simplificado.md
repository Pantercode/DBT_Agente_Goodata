# 002. Lake guarda o item simplificado, não o JSON bruto da API

**Contexto.** Cada item da API Tainacan vem com ~45 KB: todo metadado chega
três vezes (`value`, `value_as_html`, `value_as_string`) e taxonomias trazem
thumbnails em seis tamanhos. 4 mil itens por dia dariam ~180 MB/dia de JSON
que ninguém consulta.

Também: a URL citada na Base dos Dados (museus.cultura.gov.br, Mapas
Culturais) não serve mais dados. O cadastro migrou para
cadastro.museus.gov.br (WordPress + Tainacan). O conjunto da Base dos Dados não
tem tabela tratada, só aponta a fonte.

**Decisão.** A ingestão guarda, por item, os campos de cabeçalho e um bloco
`metadados` em que cada valor é reduzido à forma analítica (taxonomia vira
`{id, nome, pai}`, composto vira `[{metadatum_id, valor}]`, `false` vira null).
Nada é interpretado: "Sim", "- NÃO INFORMADO -" e textos livres passam como
vieram. Ver `ingestao/tainacan.py::simplificar_valor` e os testes.

**Consequências.**
- 2,5 MB/dia comprimido para museus.
- Se um dia precisarmos do HTML renderizado, não está no lake. Aceitável: não
  há uso analítico para ele.
- A regra de simplificação é código testado; mudar a regra é mudar o contrato
  do lake, e a partição antiga continua com o formato antigo. O `_manifest.json`
  de cada partição registra parâmetros e hash.
