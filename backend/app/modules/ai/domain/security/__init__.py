"""Seguranca do pipeline de IA (dominio puro, sem framework).

Camadas deterministicas ANTES e DEPOIS do LLM: normalizacao/deteccao de
texto codificado, detector de injecao (padroes em arquivo de dados), output
guard, scanner de argumentos de ferramenta e sanitizador de catalogo.
Aqui NAO entra nada de LLM/langchain — so regras deterministas.
"""
