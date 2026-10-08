/**
 * Erro de domínio neutro.
 *
 * Esta camada NÃO pode depender de React, Next.js, fetch, TanStack Query,
 * Zustand, browser APIs ou componentes visuais. `DomainError` é a raiz de
 * erros esperados do domínio/aplicação; o mapeamento para HTTP/RFC 7807 é
 * responsabilidade da camada de infraestrutura.
 */

export class DomainError extends Error {
  readonly code: string;
  readonly detail?: string;

  constructor(code: string, message: string, detail?: string) {
    super(message);
    this.name = new.target.name;
    this.code = code;
    this.detail = detail;
  }
}
