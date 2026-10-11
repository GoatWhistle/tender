import { useState, type FormEvent, type KeyboardEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { SearchForm } from "../../features/catalog-search";
import { useDocumentTitle } from "../../shared/hooks/use-document-title";
import { t, type MessageKey } from "../../shared/i18n";
import { Button } from "../../shared/ui/button/button";
import { Icon } from "../../shared/ui/icon/icon";
import { Illustration } from "../../shared/ui/illustration/illustration";
import { TextArea } from "../../shared/ui/field/text-area";
import styles from "./home-page.module.css";

const EXAMPLES: readonly MessageKey[] = [
  "seller:describe.example1",
  "seller:describe.example2",
  "seller:describe.example4",
];

const POPULAR: readonly { readonly label: MessageKey; readonly q: string }[] = [
  { label: "store:home.popular.laptop", q: "ноутбук" },
  { label: "store:home.popular.printer", q: "принтер" },
  { label: "store:home.popular.paper", q: "бумага" },
  { label: "store:home.popular.chair", q: "стул" },
  { label: "store:home.popular.gloves", q: "перчатки" },
  { label: "store:home.popular.milk", q: "молоко" },
];

export function HomePage() {
  useDocumentTitle(undefined);
  const navigate = useNavigate();
  const [text, setText] = useState("");
  const start = (e?: FormEvent) => {
    e?.preventDefault();
    const value = text.trim();
    if (value) navigate(`/sell?q=${encodeURIComponent(value)}`);
  };
  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) start(e);
  };
  return (
    <div className={styles.page}>
      <section className={styles.hero} aria-labelledby="home-title">
        <form className={styles.describe} onSubmit={start}>
          <div className={styles.intro}>
            <div className={styles.introText}>
              <h1 id="home-title" className={styles.title}>
                {t("store:home.title")}
              </h1>
              <p className={styles.lead}>{t("store:home.lead")}</p>
            </div>
            <Illustration name="funnel" size="lg" className={styles.art} />
          </div>
          <TextArea
            id="home-describe"
            label={t("seller:describe.label")}
            size="lg"
            value={text}
            placeholder={t("seller:describe.placeholder")}
            hint={t("seller:describe.hint")}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={onKeyDown}
          />
          <div className={styles.actions}>
            <Button type="submit" variant="primary" disabled={!text.trim()}>
              {t("seller:describe.submit")}
            </Button>
            <ul className={styles.examples} aria-label={t("seller:describe.examples")}>
              {EXAMPLES.map((key) => (
                <li key={key}>
                  <button type="button" className={styles.example} onClick={() => setText(t(key))}>
                    {t(key)}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </form>
        <aside className={styles.lookup} aria-labelledby="lookup-title">
          <h2 id="lookup-title" className={styles.lookupTitle}>
            {t("store:home.lookupTitle")}
          </h2>
          <p className={styles.lookupLead}>{t("store:home.lookupLead")}</p>
          <SearchForm />
          <nav className={styles.popular} aria-labelledby="popular-title">
            <h3 id="popular-title" className={styles.popularTitle}>
              {t("store:home.popularTitle")}
            </h3>
            <ul className={styles.popularList}>
              {POPULAR.map((item) => (
                <li key={item.q}>
                  <Link
                    className={styles.popularLink}
                    to={`/catalog?q=${encodeURIComponent(item.q)}`}
                  >
                    <Icon name="search" size={16} />
                    <span className={styles.popularName}>{t(item.label)}</span>
                    <Icon name="chevron-right-small" size={16} />
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
          <Link className={styles.all} to="/catalog">
            {t("store:home.allCatalog")}
            <Icon name="chevron-right-small" size={16} />
          </Link>
        </aside>
      </section>
    </div>
  );
}
