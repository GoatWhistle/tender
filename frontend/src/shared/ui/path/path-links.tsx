import { Fragment } from "react";
import { Link } from "react-router-dom";
import { Icon } from "../icon/icon";
import styles from "./catalog-path.module.css";

export interface PathItem {
  readonly label: string;
  readonly to?: string;
}

export interface PathLinksProps {
  readonly items: readonly PathItem[];
  readonly label: string;
}

export function PathLinks({ items, label }: PathLinksProps) {
  return (
    <nav aria-label={label}>
      <ol className={styles.path}>
        {items.map((item, index) => (
          <Fragment key={`${index}:${item.label}`}>
            {index > 0 && <Icon name="chevron-right-small" size={12} className={styles.sep} />}
            <li className={styles.item}>
              {item.to ? (
                <Link to={item.to} className={styles.link}>
                  {item.label}
                </Link>
              ) : (
                <span className={styles.current} aria-current="page">
                  {item.label}
                </span>
              )}
            </li>
          </Fragment>
        ))}
      </ol>
    </nav>
  );
}
