"""Bounded context de agentes de IA (chat no app, recuperacao de carrinho).

Clean Architecture: domain (tipos puros, sem framework) -> application (casos
de uso, portas LLMPort, resilience) -> infrastructure (adaptadores LangChain/
LangGraph, fake para testes) -> interface (endpoints/jobs, FASE 2).

Regras inegociaveis deste contexto:
- O LLM NUNCA decide regra de negocio: o codigo calcula o que e permitido e o
  LLM apenas escolhe entre opcoes permitidas e escreve texto curto.
- Nenhuma saida de LLM e usada sem validacao; saida invalida cai em fallback
  deterministico.
- O LLM NUNCA recebe precos, dados de contrato, CNPJ, e-mail ou telefone.
- company_id/user_id vem SEMPRE do contexto de autenticacao no servidor.
- Falha de IA nunca bloqueia catalogo, carrinho, checkout ou pedido.
"""
