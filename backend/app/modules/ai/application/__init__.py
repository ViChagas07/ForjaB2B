"""Casos de uso e portas do contexto de IA.

A camada de application orquestra: guardas (o que e permitido), chamadas ao
LLM por tras da porta `LLMPort` (com timeout e 1 retry) e montagem de saida
deterministica quando o LLM falha ou responde algo invalido. A camada NUNCA
importa langchain/langgraph (restrito a infrastructure).
"""
