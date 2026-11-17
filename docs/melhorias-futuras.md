# Melhorias futuras e limitações conhecidas

## Limitações do MVP (o que não foi exercitado de verdade)

| Item | Situação |
|---|---|
| **Checkout real do Stripe** | Implementado e testado com um cliente simulado. A verificação de assinatura do webhook usa o SDK real, mas nenhum pagamento de teste foi feito numa conta Stripe. |
| **Resumos com o Claude** | O `AnthropicProvider` está implementado e testado com um cliente simulado. Sem chave de API, os resumos publicados hoje são do template (o site diz "resumo automático"). |
| **Partido na data da nota** | Rankings por partido usam o partido **atual** de cada deputado, porque a API de despesas não informa o partido na data da nota. |
| **Histórico** | A base tem 12 meses. "Histórico completo" (Pro) libera consultar períodos anteriores, mas é preciso carregá-los: `carga-inicial --meses 46` cobre a legislatura inteira (~30 min). |
| **Atraso das notas** | Os deputados têm até 90 dias para apresentar as notas. Os meses recentes ficam incompletos, o que o gráfico avisa e a regra 4 trata. |

## Próximos passos

### Dados e análise
- **Cruzar o CNPJ dos fornecedores com a Receita Federal:** data de abertura, situação cadastral, sócios e atividade principal. Isso permitiria regras como "empresa aberta pouco antes da primeira nota" ou "atividade incompatível com a categoria".
- **Modelo de ML para anomalias** (ex.: Isolation Forest sobre várias características ao mesmo tempo) como **quinta regra**, mantendo as regras estatísticas atuais, que são mais fáceis de explicar ao cidadão.
- **Partido histórico**, pelo endpoint de histórico de cada deputado.
- **Mais casas legislativas:** Senado (que também publica a cota) e, depois, assembleias estaduais.
- **Comparação com a cota máxima de cada estado**, mostrando quanto do limite cada deputado usou.

### Produto
- **App mobile** (React Native, reaproveitando a API) com notificações push em vez de só e-mail.
- **Recuperação de senha e verificação de e-mail** no cadastro.
- **Portal do cliente Stripe** (trocar cartão, ver faturas) e planos anuais.
- **Página por fornecedor:** quais deputados pagaram a mesma empresa.
- **Resumo da IA também por estado e por partido.**
- **Modo escuro e acessibilidade** auditada com leitor de tela.

### Engenharia (para ir a produção)
- **Deploy:** HTTPS, build estático do front, API com vários workers (Gunicorn/Uvicorn), banco gerenciado com backup.
- **Segurança:**
  - token em cookie `httpOnly` em vez de `localStorage`;
  - limite de requisições (rate limiting) no login e na exportação;
  - segredos num gerenciador de segredos.
- **CI** (GitHub Actions) rodando `pytest`, `ruff` e `tsc` a cada push.
- **Testes do front-end:** Vitest para componentes, Playwright para o fluxo assinar → exportar.
- **Observabilidade:** logs estruturados, métricas do ETL e alerta quando o ciclo diário falhar.
- **Cache** das rotas mais acessadas (visão geral, rankings), invalidado a cada atualização dos dados.
- **LGPD:** termos de uso, política de privacidade, exclusão de conta pelo próprio usuário e registro de consentimento para e-mails.
