import { describe, expect, it } from "vitest";
import { dictionaries } from "./resources";

const PLURAL = /_(zero|one|two|few|many|other)$/;

function entries(node: unknown, prefix = ""): [string, string][] {
  if (typeof node === "string") return [[prefix, node]];
  return Object.entries(node as Record<string, unknown>).flatMap(([k, v]) =>
    entries(v, prefix ? `${prefix}.${k}` : k),
  );
}

function variables(template: string): string[] {
  return [...template.matchAll(/\{\{\s*(\w+)/g)].map((m) => m[1] ?? "").sort();
}

function index(dictionary: unknown): Map<string, Set<string>> {
  const result = new Map<string, Set<string>>();
  for (const [key, value] of entries(dictionary)) {
    const base = key.replace(PLURAL, "");
    const known = result.get(base) ?? new Set<string>();
    known.add(variables(value).join(","));
    result.set(base, known);
  }
  return result;
}

describe("словари ru и en", () => {
  const ru = index(dictionaries.ru);
  const en = index(dictionaries.en);

  it("содержат одинаковые ключи", () => {
    expect([...en.keys()].sort()).toEqual([...ru.keys()].sort());
  });

  it("используют одинаковые переменные", () => {
    for (const [key, vars] of ru) {
      expect({ key, vars: [...(en.get(key) ?? [])].sort() }).toEqual({
        key,
        vars: [...vars].sort(),
      });
    }
  });

  it("не оставляют пустых строк", () => {
    const blank = entries(dictionaries.en).filter(([, v]) => !v.trim());
    expect(blank).toEqual([]);
  });
});
