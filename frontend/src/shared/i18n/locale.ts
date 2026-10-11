export const LOCALES = ["ru", "en"] as const;

export type Locale = (typeof LOCALES)[number];

export const LOCALE_STORAGE_KEY = "portal-locale";

let current: Locale = "ru";

export function isLocale(value: unknown): value is Locale {
  return typeof value === "string" && (LOCALES as readonly string[]).includes(value);
}

export function detectLocale(): Locale {
  try {
    const stored = globalThis.localStorage?.getItem(LOCALE_STORAGE_KEY);
    if (isLocale(stored)) return stored;
  } catch {
    return "ru";
  }
  const preferred = globalThis.navigator?.languages ?? [];
  const match = preferred.map((l) => l.slice(0, 2)).find(isLocale);
  return match ?? "ru";
}

export function getLocale(): Locale {
  return current;
}

export function setCurrentLocale(locale: Locale): void {
  current = locale;
  try {
    globalThis.localStorage?.setItem(LOCALE_STORAGE_KEY, locale);
  } catch {
    return;
  }
}
