"""Infraestrutura de banco: engine, sessao, Unit of Work e base ORM.

A configuracao vem de Settings (ambiente), nunca de strings hardcoded.
O contexto de tenant RLS e aplicado DENTRO da transacao pela UoW.
"""
