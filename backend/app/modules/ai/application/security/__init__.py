"""Orquestracao de seguranca do pipeline de IA (camada application).

Compoem as regras deterministicas do dominio (`domain/security`) em um
pipeline: entrada (gate), prompt (construtor com delimitadores/canary),
memoria (somente conteudo aprovado) e registro de bloqueios. Sem I/O de
rede e sem langchain — a integracao com o grafo acontece na FASE 3.
"""
