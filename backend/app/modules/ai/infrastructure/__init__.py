"""Adaptadores de infraestrutura do contexto de IA.

Aqui (e somente aqui) ficam os imports de langchain/langgraph. A raiz de
composicao so monta o adaptador real quando `ai_agents_enabled` e
`llm_ready` (kill switch em `app.core.config`); testes usam o `FakeLLM`.
"""
