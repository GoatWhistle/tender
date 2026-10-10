import { LOCALES, t, useLocale, type Locale, type MessageKey } from "../../shared/i18n";
import { Segmented } from "../../shared/ui/segmented/segmented";

const LABEL: Record<Locale, MessageKey> = { ru: "common:language.ru", en: "common:language.en" };
const SHORT: Record<Locale, MessageKey> = {
  ru: "common:language.short.ru",
  en: "common:language.short.en",
};

export function LocaleSwitch() {
  const { locale, setLocale } = useLocale();
  return (
    <Segmented
      label={t("common:language.legend")}
      display="short"
      value={locale}
      options={LOCALES.map((value) => ({ value, label: t(LABEL[value]), short: t(SHORT[value]) }))}
      onChange={setLocale}
    />
  );
}
