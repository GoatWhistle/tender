import { createContext, useContext, useLayoutEffect, useState, type ReactNode } from "react";
import { detectLocale, setCurrentLocale, type Locale } from "./locale";

interface LocaleState {
  readonly locale: Locale;
  readonly setLocale: (locale: Locale) => void;
}

const LocaleContext = createContext<LocaleState | null>(null);

export function LocaleProvider({ children }: { readonly children: (locale: Locale) => ReactNode }) {
  const [locale, setLocale] = useState<Locale>(() => {
    const initial = detectLocale();
    setCurrentLocale(initial);
    return initial;
  });
  useLayoutEffect(() => {
    setCurrentLocale(locale);
    document.documentElement.lang = locale;
  }, [locale]);
  const change = (next: Locale) => {
    setCurrentLocale(next);
    setLocale(next);
  };
  return (
    <LocaleContext.Provider value={{ locale, setLocale: change }}>
      {children(locale)}
    </LocaleContext.Provider>
  );
}

export function useLocale(): LocaleState {
  const value = useContext(LocaleContext);
  if (!value) throw new Error("LocaleProvider is missing");
  return value;
}
