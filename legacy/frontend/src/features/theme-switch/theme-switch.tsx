import { t, type MessageKey } from "../../shared/i18n";
import { THEMES, useTheme, type Theme } from "../../shared/theme";
import type { IconName } from "../../shared/ui/icon/icon";
import { Segmented } from "../../shared/ui/segmented/segmented";

const ICON: Record<Theme, IconName> = { light: "sun", dark: "moon" };
const LABEL: Record<Theme, MessageKey> = {
  light: "common:theme.light",
  dark: "common:theme.dark",
};

export function ThemeSwitch() {
  const { theme, setTheme } = useTheme();
  return (
    <Segmented
      label={t("common:theme.legend")}
      display="icon"
      value={theme}
      options={THEMES.map((value) => ({ value, label: t(LABEL[value]), icon: ICON[value] }))}
      onChange={setTheme}
    />
  );
}
