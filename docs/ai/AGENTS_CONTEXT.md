# Contexto dos agentes de IA (Forja B2B) — leia antes de cada fase

Resumo das decisões FIXAS do projeto de IA. Em caso de dúvida, vale o código e
os docs em `docs/ai/` (`SECURITY.md`, este arquivo).

## Módulo e camadas
- Tudo vive em `backend/app/modules/ai/` com Clean Architecture:
  `domain/` (puro: sem pydantic/fastapi/sqlalchemy/langchain/langgraph),
  `application/` (casos de uso, portas, grafos), `infrastructure/`
  (adaptadores SQLAlchemy, langchain-openai, FakeLLM), `interface/` (rotas).
- **domain NUNCA importa langchain/langgraph** (contrato do import-linter
  `ai-domain-llm-independence`). LangGraph/langchain-core/langchain-openai
  ficam em application/infrastructure. Sem CrewAI/GraphRAG/GraphiFy.
- Bounded contexts: `modules/ai` NÃO importa outros módulos (cart, search,
  notification...). Quando precisa de dados deles, define uma PORTA e a raiz
  de composição (`app/main.py` ou `app/tasks/*`) injeta o adaptador.

## LLM
- LLM via API compatível com OpenAI configurada por `.env`: `LLM_BASE_URL`,
  `LLM_API_KEY`, `LLM_MODEL`, `LLM_TIMEOUT_S`, `LLM_MAX_TOKENS`. A chave fica
  SOMENTE no backend; nunca em logs, respostas ou frontend.
- `AI_AGENTS_ENABLED=false` é o KILL SWITCH (default). Endpoints de IA devem
  responder 503 e jobs não fazem nada (ou degradam para o fallback
  determinístico, quando a fase define fallback).
- Acesso por portas: `LLMPort` (`complete_structured(schema, messages)`,
  `complete_text(messages)`) com `ResilientLLM` (timeout + 1 retry, erro
  tipado `LLMUnavailableError`). `FakeLLM` determinístico em
  `infrastructure/llm_fake.py` — NENHUM teste chama rede/LLM real (opcional:
  `@pytest.mark.llm_eval`, desligado por padrão).

## Regras invioláveis do LLM
1. O LLM NUNCA decide regra de negócio: o código calcula o que é permitido;
   o LLM só escolhe entre opções permitidas e escreve texto curto.
2. Toda saída do LLM é validada (Pydantic strict + schema fechado); inválida
   cai em FALLBACK DETERMINÍSTICO.
3. O LLM NUNCA recebe preços, dados de contrato, CNPJ, e-mail ou telefone.
   Cartões de produto e preços são montados pelo BACKEND a partir do Postgres.
4. `company_id`/`user_id` NUNCA vêm de argumento do LLM: vêm do contexto de
   autenticação no servidor (JWT).
5. Falha de IA NUNCA bloqueia catálogo, carrinho, checkout ou pedido — sempre
   degrada (resposta neutra/fallback), nunca lança para o usuário.
6. Todo conteúdo não confiável (mensagem, produto, histórico, ferramenta) entra
   no prompt dentro de bloco delimitado com tag aleatória
   (`<dados_nao_confiaveis id=TAG>`), como DADO, nunca instrução.

## Segurança (Fase 2) — onde está
- `modules/ai/domain/security/`: `normalize.py` (NFKC, encoding suspeito),
  `injection.py` (+ `data/injection_patterns.v1.txt`, ALLOW/SANITIZE/BLOCK,
  resposta neutra em 11 locales), `output_guard.py` (URLs/PII/segredos/preços/
  idioma/HTML executável/canary), `tool_args.py`, `catalog_sanitizer.py`.
- `modules/ai/application/security/`: `input_gate.py` (toda mensagem + janela,
  3 bloqueios = CLOSE), `prompt_builder.py` (system prompt versionado +
  delimitadores + canary), `memory.py` (memória só com conteúdo aprovado),
  `tools.py` (allowlist por nó, schemas strict, somente leitura),
  `budget.py`, `note_sanitizer.py`.
- `agent_audit_log` grava auditoria SEM PII (hash + tamanho + prefixo ≤80).

## Dados do chat (Fase 5)
- `chat_conversations` (UUID não adivinhável; visitante = company/user NULL)
  e `chat_messages` (role user|assistant, conteúdo sanitizado). Conversa de
  usuário logado só é lida pelo dono (mesma empresa E mesmo usuário); RLS por
  tenant; TTL `AI_CONVERSATION_TTL_DAYS` com limpeza diária
  (`app.delete_expired_chat_conversations`).
- Histórico truncado em `AI_CHAT_HISTORY_TURNS`; nunca persistir saída de
  ferramenta, texto de produto ou system prompt; sem resumo gerado por LLM.
