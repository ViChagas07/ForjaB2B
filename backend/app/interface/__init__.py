"""Camada de interface (HTTP): routers, schemas Pydantic, middlewares e erros.

Validacao de borda com Pydantic e mapeamento de erros para RFC 7807 vivem
aqui. Nenhuma regra de negocio e nenhum import direto de infraestrutura:
recursos tecnicos chegam via app.state, ligados na raiz de composicao.
"""
