"""Abstracoes transversais: configuracao, erros base, logging, correlacao e telemetria.

Regra: app.core nao importa camadas (domain/application/infrastructure/interface)
nem modulos de negocio. Verificado pelo contrato `core-neutrality` do import-linter.
"""
