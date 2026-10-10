import type { CSSProperties } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api";
import { SearchForm } from "../../features/catalog-search";
import { useResource } from "../../shared/hooks/use-resource";
import { useDocumentTitle } from "../../shared/hooks/use-document-title";
import { t } from "../../shared/i18n";
import { Banner } from "../../shared/ui/banner/banner";
import { LinkButton } from "../../shared/ui/button/link-button";
import { Icon } from "../../shared/ui/icon/icon";
import { SkeletonRows } from "../../shared/ui/skeleton/skeleton";
import styles from "./home-page.module.css";

export function HomePage() {
  const categories = useResource(() => api.categories(), "categories");
  useDocumentTitle(undefined);
  return (
    <div className={styles.page}>
      <section className={styles.hero}>
        <h1 className={styles.title}>{t("store:title")}</h1>
        <p className={styles.lead}>{t("store:home.lead")}</p>
        <SearchForm size="lg" />
      </section>
      <section className={styles.block} aria-labelledby="categories">
        <h2 id="categories" className={styles.blockTitle}>
          {t("store:home.categories")}
        </h2>
        {categories.error && (
          <Banner tone="error" title={t("store:catalog.error")}>
            {t("store:catalog.errorText")}
          </Banner>
        )}
        {!categories.data && !categories.error && (
          <SkeletonRows rows={3} label={t("store:catalog.loading")} />
        )}
        <ul className={styles.cards}>
          {categories.data?.map((c, i) => (
            <li key={c.slug} style={{ "--i": i } as CSSProperties} className={styles.cardItem}>
              <Link to={`/catalog/${c.slug}`} className={styles.card}>
                <span className={styles.cardName}>{c.name}</span>
                <span className={styles.cardMeta}>
                  {t("store:home.positions", { count: c.positions })}
                </span>
                <span className={styles.cardMeta}>
                  {t("store:home.products", { count: c.products })}
                </span>
                <Icon name="chevron-right" size={20} className={styles.cardArrow} />
              </Link>
            </li>
          ))}
        </ul>
      </section>
      <section className={styles.sell}>
        <div className={styles.sellText}>
          <h2 className={styles.blockTitle}>{t("store:home.sellTitle")}</h2>
          <p className={styles.lead}>{t("store:home.sellText")}</p>
        </div>
        <LinkButton to="/sell" variant="primary" icon="plus">
          {t("store:home.sellAction")}
        </LinkButton>
      </section>
    </div>
  );
}
