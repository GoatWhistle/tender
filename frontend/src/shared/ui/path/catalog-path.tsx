import { Fragment } from "react";
import { Icon } from "../icon/icon";
import styles from "./catalog-path.module.css";

export interface CatalogPathProps {
  readonly items: readonly string[];
  readonly label: string;
}

export function CatalogPath({ items, label }: CatalogPathProps) {
  return (
    <ol className={styles.path} aria-label={label}>
      {items.map((item, index) => (
        <Fragment key={`${index}:${item}`}>
          {index > 0 && <Icon name="chevron-right-small" size={12} className={styles.sep} />}
          <li className={styles.item}>{item}</li>
        </Fragment>
      ))}
    </ol>
  );
}
