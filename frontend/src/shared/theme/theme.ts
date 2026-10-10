export const THEME_CHOICES = ["system", "light", "dark"] as const;

export type ThemeChoice = (typeof THEME_CHOICES)[number];

export type Theme = Exclude<ThemeChoice, "system">;

export const THEME_STORAGE_KEY = "portal-theme";

export const DARK_QUERY = "(prefers-color-scheme: dark)";

export function isThemeChoice(value: unknown): value is ThemeChoice {
  return typeof value === "string" && (THEME_CHOICES as readonly string[]).includes(value);
}

export function readThemeChoice(): ThemeChoice {
  try {
    const stored = globalThis.localStorage?.getItem(THEME_STORAGE_KEY);
    return isThemeChoice(stored) ? stored : "system";
  } catch {
    return "system";
  }
}

export function storeThemeChoice(choice: ThemeChoice): void {
  try {
    globalThis.localStorage?.setItem(THEME_STORAGE_KEY, choice);
  } catch {
    return;
  }
}

export function resolveTheme(choice: ThemeChoice, systemDark: boolean): Theme {
  if (choice !== "system") return choice;
  return systemDark ? "dark" : "light";
}
