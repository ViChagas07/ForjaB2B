# Segurança do pipeline de IA (FASE 2)

Camadas determinísticas que cercam o LLM. **Nenhuma regra crítica depende do
modelo**: o código calcula o que é permitido; o LLM só escolhe entre opções
permitidas e escreve texto curto. Com `AI_AGENTS_ENABLED=false` (padrão),
nenhum destes caminhos executa e o sistema fica idêntico ao de antes.

## Mapa de ameaças → camada que mitiga

| # | Ameaça | Camada (arquivo) | Comportamento |
|---|--------|------------------|----------------|
| 1 | Tokens invisíveis/escondidos (zero-width, controles, NFKC confuso) | `domain/security/normalize.py` | Remove e colapsa antes de QUALQUER checagem; limita a `AI_CHAT_MAX_MESSAGE_CHARS` |
| 2 | Conteúdo codificado (base64/hex/rot13 longo, letra a letra, homóglifo) | `normalize.py` (`detect_encoding_flags`, `decode_hidden_candidates`) | MARCA (SANITIZE); o payload decodificado é re-escaneado — jailbreak codificado = BLOCK |
| 3 | Jailbreak/injeção direta (pt/en/es): "ignore instruções anteriores", modo dev/DAN, pedir system prompt, "traduza e execute", role-play para burlar, multi-turno | `domain/security/injection.py` + `data/injection_patterns.v1.txt` (lista versionada, anti-ReDoS) | Veredito ALLOW/SANITIZE/BLOCK com `reason_code` estável; roda em TODA mensagem, em cada mensagem da janela, em pares consecutivos e na junção da janela |
| 4 | Ataque em múltiplos turnos | `application/security/input_gate.py` (scan da janela + pares) | BLOCK com contagem |
| 5 | Insistência (3 bloqueios na conversa) | `input_gate.py` + `BlockCounter` | CLOSE: conversa encerrada com resposta neutra; audit `agent_audit_log` (reason_code) |
| 6 | Resposta de bloqueio vaza regras/detecção | `data/neutral_responses.v1.json` (11 locales) | Única, curta, traduzida, neutra |
| 7 | Prompt injection via conteúdo não confiável (produto, carrinho, histórico, ferramenta) | `application/security/prompt_builder.py` + `data/system_prompt.chat.v1.txt` | System prompt versionado com hierarquia (sistema > usuário > dados); todo conteúdo não confiável entra em bloco `<dados_nao_confiaveis id=TAG>` com tag aleatória por requisição; ocorrências do delimitador (com/sem acento) são removidas antes |
| 8 | Vazamento do system prompt/canary na saída | `domain/security/output_guard.py` (`check_canary`, `leaks_system_prompt`) | BLOCK → resposta neutra; incidente para audit |
| 9 | Saída com HTML/Markdown executável | `output_guard.py` | BLOCK (`html_executavel`) |
| 10 | URL inventada na saída | `output_guard.py` | Remove URL absoluta/link externo; só caminhos relativos do site passam |
| 11 | PII na saída (e-mail, telefone) e segredos (sk_/whsec_/AKIA/ghp_/Bearer/api_key) | `output_guard.py` | Remove/mascara com `actions` para audit |
| 12 | Preço escrito pelo modelo | `output_guard.py` | Remove valores monetários do TEXTO (preço só em cartão montado pelo backend) |
| 13 | Idioma divergente do locale | `output_guard.py` (script Unicode) | BLOCK quando detectável (ratio > 50%) |
| 14 | Ferramenta fora do nó / desconhecida | `application/security/tools.py` (`ToolRegistry`) | Allowlist por nó: o modelo só enxerga as do nó atual |
| 15 | Identidade forjada em argumentos (`company_id`/`user_id`) | `domain/security/tool_args.py` + `ToolCallGuard` | REMOVIDA sempre; o servidor injeta a identidade real (JWT) |
| 16 | SQL/URL/caminho/instrução em argumentos | `tool_args.py` (`scan_tool_arguments`) | Rejeita (`tool_arg_sql/url/path` ou id do padrão) |
| 17 | Abuso de ferramenta | `ToolCallGuard` | Máx. 4 chamadas/turno; 1 por (nome, argumentos) canônico; schemas Pydantic strict (`extra="forbid"`, regex de IDs); ferramentas SOMENTE LEITURA — ação com efeito colateral nunca é ferramenta |
| 18 | Memory poisoning | `application/security/memory.py` | Memória aceita apenas user sanitizado + assistant aprovado (superficie sem porta para ferramenta/produto/system prompt); re-normaliza ao guardar; reinjeção sempre como DADO no bloco delimitado, truncada em `AI_CHAT_HISTORY_TURNS`; sem resumo de LLM persistido; isolada por `conversation_id` com TTL |
| 19 | RAG/catalog poisoning (instrução em nome/descrição) | `domain/security/catalog_sanitizer.py` | Allowlist de campos; HTML/URL removidos; descrição ≤ 300; documento que bate nos padrões de injeção vai para QUARENTENA: omitido do contexto do LLM (segue no catálogo normal) e marcado no audit com product_id; hash sha256 do conteúdo enviado ao modelo |
| 20 | Abuso de custo/volume | `application/security/budget.py` + `RateLimitClass.AI` (`RATE_LIMIT_AI_*`) + `AI_DAILY_TOKEN_BUDGET` | Rate limit próprio por IP/usuário (429 com `Retry-After` — mesmo mecanismo do middleware) e orçamento diário de tokens estimados; kill switch por requisição |

## O que NÃO é coberto (nenhuma defesa é perfeita)

As regras determinísticas são a rede de segurança, não garantia absoluta:

- **Detecção de idioma por script** não distingue dois idiomas no MESMO script
  (ex.: resposta em espanhol para locale pt-BR passa).
- **Padrões de jailbreak são revisados por humanos** (arquivo versionado): ataques
  com nova redação podem passar na entrada — por isso a saída continua guardada
  (canary, output guard) e o LLM nunca decide regra de negócio.
- **Homóglifos** além de cirílico/grego (armênio, etc.) não são marcados.
- **Imagens/anexos** não são aceitos no chat desta fase.
- **Base64/hex curto** (< 40/32 chars) não é marcado (custo x falso-positivo).
- **Rate limit da rota AI** está configurado (classe/policy), mas o mapeamento de
  caminho no middleware só acontece junto dos endpoints (FASE 3).
- **Memória** em memória (dev/testes); a implementação distribuída com TTL (Redis)
  é FASE 3 — a política de conteúdo já é a mesma.
- **Canary** detecta cópia literal do system prompt; parafrasear não é detectável.

## Avaliação contra LLM real

`tests/security/test_ai_guards.py::test_llm_eval_ataques_contra_llm_real` está
marcado `@pytest.mark.llm_eval` (desligado por padrão via `-m 'not llm_eval'`).
Rode explicitamente com credenciais reais: `pytest -m llm_eval`. A suíte padrão
NUNCA chama rede ou LLM real.
