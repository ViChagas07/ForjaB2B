"""Bounded context reservado: pricing.

O calculo de preco compartilhado (tier, regra da empresa e desconto automatico
CNPJ) vive em ``app.domain.pricing``, porque cart, ordering e search nao podem
importar modulos entre si (contrato de bounded contexts do import-linter).
Este pacote permanece reservado para um caso de uso proprio de pricing, sem
duplicar a regra ja centralizada no dominio.
"""
