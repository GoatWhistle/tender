import { t, type MessageKey } from "../../shared/i18n";
import { THEME_CHOICES, useTheme, type ThemeChoice } from "../../shared/theme";
import type { IconName } from "../../shared/ui/icon/icon";
import { Segmented } from "../../shared/ui/segmented/segmented";

const ICON: Record<ThemeChoice, IconName> = { system: "monitor", light: "sun", dark: "moon" };
const LABEL: Record<ThemeChoice, MessageKey> = {
  system: "common:theme.system",
  light: "common:theme.light",
  dark: "common:theme.dark",
};

export function ThemeSwitch() {
  const { choice, setChoice } = useTheme();
  return (
    <Segmented
      label={t("common:theme.legend")}
      display="icon"
      value={choice}
      options={THEME_CHOICES.map((value) => ({ value, label: t(LABEL[value]), icon: ICON[value] }))}
      onChange={setChoice}
    />
  );
}
