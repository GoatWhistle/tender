import { t, useLocale, type Locale, type MessageKey } from "../../shared/i18n";
import { Button } from "../../shared/ui/button/button";

const SHORT: Record<Locale, MessageKey> = {
  ru: "common:language.short.ru",
  en: "common:language.short.en",
};

const SWITCH_TO: Record<Locale, MessageKey> = {
  ru: "common:language.switchToEn",
  en: "common:language.switchToRu",
};

export function LocaleSwitch() {
  const { locale, setLocale } = useLocale();
  const label = t(SWITCH_TO[locale]);
  return (
    <Button
      variant="ghost"
      icon="globe"
      aria-label={`${t(SHORT[locale])}, ${label}`}
      title={label}
      onClick={() => setLocale(locale === "ru" ? "en" : "ru")}
    >
      {t(SHORT[locale])}
    </Button>
  );
}
