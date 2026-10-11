import { t } from "../../shared/i18n";
import { Facts } from "../../shared/ui/facts/facts";
import { Illustration } from "../../shared/ui/illustration/illustration";
import type { Position } from "../rag";
import styles from "./card-header.module.css";

export interface CardHeaderProps {
  readonly position: Position;
  readonly withName?: boolean;
}

export function CardHeader({ position, withName = true }: CardHeaderProps) {
  const items = [
    { key: "name", label: t("seller:card.dialogName"), value: position.name },
    { key: "category", label: t("seller:card.category"), value: position.okpd2_name },
    { key: "code", label: t("seller:card.code"), value: position.code },
    { key: "okpd2", label: t("seller:card.okpd2"), value: position.okpd2 },
  ];
  return (
    <div className={styles.header}>
      <div className={styles.media}>
        <Illustration name="boxes" size="sm" />
      </div>
      <Facts layout="rows" items={withName ? items : items.slice(1)} />
    </div>
  );
}
