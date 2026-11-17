# Metodologia: como os gastos fora do padrão são encontrados

> **Um gasto fora do padrão não significa irregularidade.** Os destaques são estatísticos: eles mostram que um valor é muito diferente do comum, não que ele seja ilegal. Muitos têm explicação simples, como uma viagem longa, um evento ou uma compra anual. Use os destaques como ponto de partida para consultar a nota original, nunca como conclusão.

## De onde vêm os dados

Todas as despesas vêm da [API de Dados Abertos da Câmara dos Deputados](https://dadosabertos.camara.leg.br). São as notas fiscais e os recibos reembolsados pela Cota para o Exercício da Atividade Parlamentar (CEAP) nos últimos 12 meses. Os dados são atualizados periodicamente, e o valor considerado é o **valor líquido**: o valor da nota menos a parte que a Câmara não reembolsou (glosa).

## As quatro regras

### 1. Valor atípico para a categoria no estado

**O que procura:** uma nota com valor muito maior que as notas da mesma categoria apresentadas por deputados do mesmo estado.

**Por que comparar só com o mesmo estado:** o valor da cota muda de estado para estado. Ele é maior para quem mora longe de Brasília, porque as passagens são mais caras.

**Como calcula:**

1. Junta todas as notas da mesma categoria (ex.: combustível) de deputados do mesmo estado. Grupos com menos de 30 notas ficam de fora, porque são pequenos demais para comparar.
2. Calcula a **mediana** (o valor do meio) e o **desvio absoluto mediano** (MAD: quanto as notas costumam se afastar da mediana).
3. Calcula um **z-score robusto** para cada nota: `0,6745 × (valor − mediana) ÷ MAD`. Esse número diz quantas "distâncias típicas" a nota está acima do normal.
4. A nota é destacada quando o z-score passa de **3,5**, o limite recomendado por Iglewicz e Hoaglin (1993) para esse método.

**Dois cuidados:**

- **Mediana e MAD, em vez de média e desvio-padrão:** um único valor enorme puxa a média para cima e "esconde" a si mesmo. A mediana praticamente não se mexe.
- **O cálculo é feito sobre o logaritmo do valor:** a maioria das notas é pequena e poucas são grandes. Sem o logaritmo, quase toda nota grande seria marcada (nos testes com dados reais, seriam ~10 mil destaques contra ~1,9 mil). Com ele, "fora do padrão" passa a significar "muitas vezes maior que o comum". Os destaques ficam, em geral, **5 a 30 vezes acima da mediana**.

**Exemplo de texto:** *"Valor de R$ 7.351,90 é 32,0 vezes a mediana de Combustíveis e lubrificantes para deputados de RJ (R$ 230,06)."*

### 2. Concentração em um fornecedor

**O que procura:** um único fornecedor que recebe **mais de 40%** do que o deputado gastou numa categoria durante o ano.

**Quando vale:** só quando o gasto na categoria passa de R$ 10 mil no ano, com pelo menos 5 notas.

**Onde NÃO vale:** em muitas categorias, ter um fornecedor só é o normal: a operadora de telefone, o aluguel do escritório, o contrato de locação do carro, as companhias aéreas. Por isso a regra só se aplica às categorias em que **o deputado típico divide os gastos** entre vários fornecedores, ou seja, onde a mediana da fatia do maior fornecedor fica abaixo de 40%. Esse critério é recalculado a partir dos dados a cada atualização. Nos dados atuais, entram combustíveis, hospedagem e alimentação. Divulgação fica de fora, porque contratar uma agência só é o comum.

**Exemplo:** *"O fornecedor POSTO X recebeu 87% do gasto com Combustíveis e lubrificantes em 2026 (R$ 69.606,83 de R$ 79.634,96). Nesta categoria, o maior fornecedor de um deputado costuma ficar com 24%."*

### 3. Notas repetidas

**O que procura:** duas ou mais notas do **mesmo fornecedor**, com o **mesmo valor**, na **mesma data**.

**Fica de fora:**

- notas abaixo de R$ 100;
- as categorias em que notas iguais no mesmo dia são rotina: passagens (ida e volta custam o mesmo), pedágio e estacionamento, hospedagem (uma nota por diária), telefonia, aluguel de escritório, locação de veículos e auxílio-moradia.

**Exemplo:** *"2 notas de R$ 7.665,00 do mesmo fornecedor (EMPRESA X) na mesma data (25/08/2026), em Divulgação da atividade parlamentar."*

### 4. Gasto mensal atípico

**O que procura:** um mês em que o **total** gasto pelo deputado ficou muito acima do total dos outros deputados do mesmo estado, no mesmo mês.

**Como calcula:**

- usa o mesmo z-score robusto da regra 1, com limite de 3,5;
- exige também que o total seja **pelo menos o dobro da mediana** do estado. Assim, diferenças pequenas não são marcadas nos meses em que os deputados de um estado gastaram valores muito parecidos;
- só considera estados e meses com pelo menos 5 deputados com gastos;
- só considera **meses consolidados**, com pelo menos 60% do número típico (mediano) de notas por mês. As notas chegam com até 90 dias de atraso. Num mês recente, a maioria dos deputados ainda tem pouco lançado, a mediana fica artificialmente baixa e um gasto normal pareceria "200 vezes a mediana". Isso aconteceu na primeira versão da regra e foi corrigido. Com os dados atuais, setembro, outubro e novembro de 2026 ainda não entram.

**Exemplo:** *"O gasto total em ago/2026 (R$ 129.940,19) foi 5,7 vezes a mediana dos 14 deputados de PA no mesmo mês (R$ 22.970,83)."*

## Limitações conhecidas

- **O contexto não aparece nos números.** Um evento, uma missão ou uma compra anual podem explicar um valor alto.
- **Notas chegam com atraso** (até 90 dias). Os meses mais recentes ainda estão incompletos, e os alertas desses meses podem mudar.
- **Os parâmetros são escolhas.** Limites diferentes produziriam mais ou menos destaques. Todos podem ser ajustados no arquivo de configuração (`ANOMALIA_*` no `.env`), e os valores atuais foram calibrados com os dados reais para chegar a uma quantidade que dê para acompanhar.
- **Os dados são os publicados pela Câmara.** Erros na fonte aparecem aqui também. Encontramos e corrigimos um: o sinal invertido do valor líquido na API (ver `docs/arquitetura.md`).

## Atualização

Os destaques são recalculados depois de cada atualização dos dados (`python -m app.etl recalcular-alertas`).

- Um destaque que deixa de se aplicar (porque a Câmara corrigiu a nota, por exemplo) é removido.
- Um destaque que continua válido mantém a data em que apareceu pela primeira vez.

## Parâmetros atuais

| Parâmetro | Valor | Variável |
|---|---|---|
| Limite do z-score robusto (regras 1 e 4) | 3,5 | `ANOMALIA_Z_LIMIAR` |
| Mínimo de notas para comparar (regra 1) | 30 | `ANOMALIA_MIN_GRUPO` |
| Fatia do maior fornecedor (regra 2) | 40% | `ANOMALIA_CONCENTRACAO_LIMITE` |
| Gasto mínimo na categoria no ano (regra 2) | R$ 10.000 | `ANOMALIA_CONCENTRACAO_MIN_TOTAL` |
| Notas mínimas na categoria no ano (regra 2) | 5 | `ANOMALIA_CONCENTRACAO_MIN_NOTAS` |
| Valor mínimo da nota (regra 3) | R$ 100 | `ANOMALIA_REPETIDAS_VALOR_MINIMO` |
| Diferença máxima de dias (regra 3) | 0 (mesma data) | `ANOMALIA_REPETIDAS_JANELA_DIAS` |
| Múltiplo mínimo da mediana (regra 4) | 2× | `ANOMALIA_MENSAL_RAZAO_MINIMA` |
| Deputados mínimos no estado e mês (regra 4) | 5 | `ANOMALIA_MENSAL_MIN_DEPUTADOS` |
| Fração mínima do volume típico de notas para o mês contar (regra 4) | 60% | `ANOMALIA_MENSAL_COMPLETUDE_MINIMA` |

## Resultado com os dados atuais (dez/2025 a nov/2026)

| Regra | Destaques |
|---|---|
| Valor atípico para a categoria no estado | 1.850 |
| Concentração em um fornecedor | 167 |
| Notas repetidas | 273 |
| Gasto mensal atípico | 45 |
| **Total** (sobre ~180 mil notas) | **2.335** |
