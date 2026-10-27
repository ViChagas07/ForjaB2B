"use client";

import * as React from "react";

export interface HighlightPart {
  text: string;
  bold: boolean;
}

interface FoldedText {
  /** Caracteres (codepoints) normalizados: sem diacríticos, minúsculos. */
  chars: string[];
  /** Índice de codepoint ORIGINAL para cada caractere normalizado. */
  map: number[];
}

/**
 * Compara sem maiúsculas/acentos: decompõe (NFD), descarta marcas de
 * diacrítico e minúsculas. `map` guarda o codepoint original de cada
 * caractere normalizado — a decompissão muda o comprimento (ex.: harakat do
 * árabe), e os recortes precisam voltar ao texto original.
 */
function foldWithMap(text: string): FoldedText {
  const chars: string[] = [];
  const map: number[] = [];
  let originalIndex = 0;
  for (const char of text) {
    for (const piece of char.normalize("NFD")) {
      if (/\p{M}/u.test(piece)) {
        continue;
      }
      chars.push(piece.toLowerCase());
      map.push(originalIndex);
    }
    originalIndex += 1;
  }
  return { chars, map };
}

function indexOfSubarray(haystack: string[], needle: string[]): number {
  if (needle.length === 0) {
    return 0;
  }
  for (let start = 0; start + needle.length <= haystack.length; start++) {
    let matches = true;
    for (let offset = 0; offset < needle.length; offset++) {
      if (haystack[start + offset] !== needle[offset]) {
        matches = false;
        break;
      }
    }
    if (matches) {
      return start;
    }
  }
  return -1;
}

function codepointToStringIndex(text: string, codepointIndex: number): number {
  let stringIndex = 0;
  let count = 0;
  for (const char of text) {
    if (count === codepointIndex) {
      return stringIndex;
    }
    count += 1;
    stringIndex += char.length;
  }
  return text.length;
}

/**
 * Divide `text` em partes, marcando em negrito a primeira ocorrência de
 * `query` (sem diferenciar maiúsculas nem acentos). Nunca usa HTML: o
 * componente renderiza as partes como nós de texto + <strong>.
 */
export function splitHighlight(text: string, query: string): HighlightPart[] {
  const folded = foldWithMap(text);
  const needle = foldWithMap(query);
  if (needle.chars.length === 0) {
    return [{ text, bold: false }];
  }
  const index = indexOfSubarray(folded.chars, needle.chars);
  if (index < 0) {
    return [{ text, bold: false }];
  }
  const startCodepoint = folded.map[index] ?? 0;
  const endCodepoint = (folded.map[index + needle.chars.length - 1] ?? startCodepoint) + 1;
  const start = codepointToStringIndex(text, startCodepoint);
  const end = codepointToStringIndex(text, endCodepoint);
  return [
    { text: text.slice(0, start), bold: false },
    { text: text.slice(start, end), bold: true },
    { text: text.slice(end), bold: false },
  ].filter((part) => part.text !== "");
}

interface HighlightMatchProps {
  text: string;
  query: string;
  className?: string;
}

/** Texto com o trecho digitado em <strong> (sem HTML bruto). */
export function HighlightMatch({ text, query, className }: HighlightMatchProps) {
  const parts = React.useMemo(() => splitHighlight(text, query), [text, query]);
  return (
    <span className={className}>
      {parts.map((part, index) =>
        part.bold ? (
          <strong key={index} className="font-semibold">
            {part.text}
          </strong>
        ) : (
          <React.Fragment key={index}>{part.text}</React.Fragment>
        ),
      )}
    </span>
  );
}
