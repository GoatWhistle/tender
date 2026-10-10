import { createContext, useContext, useLayoutEffect, useState, type ReactNode } from "react";
import { useMediaQuery } from "../hooks/use-media-query";
import {
  DARK_QUERY,
  readThemeChoice,
  resolveTheme,
  storeThemeChoice,
  type Theme,
  type ThemeChoice,
} from "./theme";

interface ThemeState {
  readonly choice: ThemeChoice;
  readonly theme: Theme;
  readonly setChoice: (choice: ThemeChoice) => void;
}

const ThemeContext = createContext<ThemeState | null>(null);

export function ThemeProvider({ children }: { readonly children: ReactNode }) {
  const [choice, setChoiceState] = useState<ThemeChoice>(readThemeChoice);
  const systemDark = useMediaQuery(DARK_QUERY);
  const theme = resolveTheme(choice, systemDark);
  useLayoutEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);
  const setChoice = (next: ThemeChoice) => {
    storeThemeChoice(next);
    setChoiceState(next);
  };
  return (
    <ThemeContext.Provider value={{ choice, theme, setChoice }}>{children}</ThemeContext.Provider>
  );
}

export function useTheme(): ThemeState {
  const value = useContext(ThemeContext);
  if (!value) throw new Error("ThemeProvider is missing");
  return value;
}
