import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const LOCALES = ["es", "fr", "de", "it", "ar", "ja", "ko", "ru", "zh-CN"] as const;

function settings(locale: string): Record<string, unknown> {
  const messages = JSON.parse(
    readFileSync(join(process.cwd(), "messages", `${locale}.json`), "utf-8"),
  ) as { settings: Record<string, unknown> };
  return messages.settings;
}

describe("tradução das configurações", () => {
  it("não deixa os 9 locales não-pt em inglês", () => {
    for (const locale of LOCALES) {
      const messages = settings(locale);
      expect(messages.title, locale).not.toBe("Settings");
      expect(messages.appearance, locale).not.toBe("Appearance");
      expect((messages.accents as Record<string, string>).amber, locale).not.toBe("Amber");
    }
  });
});
