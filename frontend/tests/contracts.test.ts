import { readFileSync } from "node:fs"
import { describe, expect, it } from "vitest"
import cardEn from "../src/shared/i18n/locales/en/card.json"
import en from "../src/shared/i18n/locales/en/portal.json"
import ragEn from "../src/shared/i18n/locales/en/rag.json"
import cardRu from "../src/shared/i18n/locales/ru/card.json"
import ru from "../src/shared/i18n/locales/ru/portal.json"
import ragRu from "../src/shared/i18n/locales/ru/rag.json"

function keys(value: Record<string, unknown>, prefix = ""): string[] {
  return Object.entries(value)
    .flatMap(([key, item]) =>
      item && typeof item === "object" && !Array.isArray(item)
        ? keys(item as Record<string, unknown>, `${prefix}${key}.`)
        : [`${prefix}${key}`],
    )
    .sort()
}
describe("Контракты интерфейса", () => {
  it("сохраняет одинаковые ключи переводов", () => {
    expect(keys(ru)).toEqual(keys(en))
    expect(keys(cardRu)).toEqual(keys(cardEn))
    expect(keys(ragRu)).toEqual(keys(ragEn))
  })
  it("определяет все семантические токены в обеих темах", () => {
    const css = readFileSync("src/shared/styles/tokens/semantic.css", "utf8")
    const themes = css
      .split(":root[data-theme=")
      .slice(1)
      .map((theme) => [...theme.matchAll(/(--[\w-]+):/g)].map((match) => match[1]).sort())
    expect(themes).toHaveLength(2)
    expect(themes[0]).toEqual(themes[1])
  })
  it("сжимает длительности для reduced motion", () => {
    const css = readFileSync("src/shared/styles/tokens/motion.css", "utf8")
    const [normal, reduced] = css.split("@media (prefers-reduced-motion: reduce)")
    const durations = [...(normal ?? "").matchAll(/(--dur-[\w-]+):/g)].map((match) => match[1])
    for (const name of new Set(durations)) expect(reduced).toContain(`${name}: 1ms`)
  })
})
