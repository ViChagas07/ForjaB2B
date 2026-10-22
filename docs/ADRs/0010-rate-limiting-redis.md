# ADR-0010: Rate limiting com Redis e fail-open

- **Status:** **proposto — NÃO implementado** (decisão registrada para não simular controle)
- **Data:** 2026-10-22
- **Contexto do código:** `backend/app/infrastructure/cache/redis.py`,
  `backend/app/interface/middleware.py`, `backend/app/core/config.py`
- **Evidência da lacuna:** não há middleware/limitador, nem chamada `INCR`/`EXPIRE` no
  backend; o Redis é usado para refresh token, cache, OAuth state/exchange e readiness.

## Contexto

A API tem endpoints públicos de catálogo e busca, login e webhook. Sem limite de
requisições, um cliente pode abusar de busca, autenticação ou criação de pedidos. O
`docker-compose.yml` já sobe Redis, mas ele não é usado para rate limiting hoje.

## Decisão proposta

1. Limitar por **IP** (rotas públicas) e por **usuário/tenant** (rotas autenticadas), com
   janela deslizante no Redis e chaves de baixa cardinalidade (rota normalizada, não path
   cru).
2. Limites diferentes por classe: leitura pública, autenticação, escrita de pedido,
   webhook. Resposta `429` com `Retry-After` e Problem Details RFC 7807.
3. **Fail-open:** se o Redis estiver indisponível, a requisição segue (com log/métrica de
   degradação). O risco de abuso é aceito em troca de não derrubar a loja; em produção, o
   edge/WAF é a primeira linha.
4. Respeitar `X-Forwarded-For` apenas de proxies confiáveis; nunca confiar no header vindo
   direto da internet.
5. Configuração por ambiente (`RATE_LIMIT_*`) e testes de janela, expiração, 429 e
   fail-open.

## Alternativas consideradas

- **WAF/edge (Cloudflare, AWS WAF):** melhor primeira linha, mas não substitui limites por
  usuário/tenant; seria complementar.
- **Limitador em memória:** não funciona com múltiplas réplicas; rejeitado.
- **Biblioteca `slowapi`:** útil, mas adiciona dependência e não cobre tenant/IP da mesma
  forma; poderia ser usada como implementação.
- **Redis com `INCR` simples (janela fixa):** mais barato, mas permite rajadas na virada da
  janela; a janela deslizante é preferível.

## Consequências (se implementado)

- Proteção básica contra abuso e brute force, com custo de uma chamada Redis por request.
- Fail-open exige métrica e alerta para não mascarar Redis fora do ar.
- Chaves precisam de TTL e de uma política de privacidade (IP é dado pessoal; reter o
  mínimo).
- O webhook precisa de limite próprio para não ser bloqueado por tráfego de loja.

## Em produção real, seria diferente

- Colocar WAF/CDN na borda com regras gerenciadas e bot detection.
- Usar rate limit distribuído (Redis Cluster ou serviço dedicado) com limites por API key e
  por tenant, e dashboards de 429.
- Ter circuit breaker para o próprio Redis e fallback local temporário.
- Fazer testes de carga para calibrar limites (ver `docs/testing/LOAD.md`), o que ainda não
  foi feito.
- Considerar custo/abuso por endpoint de embeddings, que é o mais caro quando habilitado.
