import { describe, expect, it } from "vitest";

import { err, isErr, isOk, mapResult, ok } from "@/core/domain/result";

describe("Result", () => {
  it("constrói Ok e Err", () => {
    expect(ok(1)).toEqual({ ok: true, value: 1 });
    expect(err("x")).toEqual({ ok: false, error: "x" });
  });

  it("estreita o tipo com isOk/isErr", () => {
    const okResult = ok(2);
    if (isOk(okResult)) {
      expect(okResult.value).toBe(2);
    }

    const errResult = err("boom");
    if (isErr(errResult)) {
      expect(errResult.error).toBe("boom");
    }
  });

  it("mapeia apenas valores Ok", () => {
    expect(mapResult(ok(2), (v) => v * 2)).toEqual({ ok: true, value: 4 });
    expect(mapResult(err("x"), (v: number) => v)).toEqual({ ok: false, error: "x" });
  });
});
