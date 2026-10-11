import type { Resource } from "i18next"
import cardEn from "./locales/en/card.json"
import en from "./locales/en/portal.json"
import ragEn from "./locales/en/rag.json"
import cardRu from "./locales/ru/card.json"
import ru from "./locales/ru/portal.json"
import ragRu from "./locales/ru/rag.json"
export const resources = {
  ru: { portal: ru, card: cardRu, rag: ragRu },
  en: { portal: en, card: cardEn, rag: ragEn },
} satisfies Resource
