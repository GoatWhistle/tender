import { useEffect, useId, useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { t } from "../../shared/i18n";
import { Button } from "../../shared/ui/button/button";
import styles from "./search-form.module.css";

export interface SearchFormProps {
  readonly base?: string;
  readonly size?: "md" | "lg";
}

export function SearchForm({ base = "/catalog", size = "md" }: SearchFormProps) {
  const id = useId();
  const [params] = useSearchParams();
  const [q, setQ] = useState(params.get("q") ?? "");
  const navigate = useNavigate();
  useEffect(() => setQ(params.get("q") ?? ""), [params]);
  const submit = (e: FormEvent) => {
    e.preventDefault();
    const text = q.trim();
    navigate(text ? `${base}?q=${encodeURIComponent(text)}` : base);
  };
  return (
    <form role="search" className={size === "lg" ? styles.large : styles.form} onSubmit={submit}>
      <label htmlFor={id} className="sr-only">
        {t("store:search.label")}
      </label>
      <input
        id={id}
        className={styles.input}
        value={q}
        placeholder={t("store:search.placeholder")}
        autoComplete="off"
        onChange={(e) => setQ(e.target.value)}
      />
      <Button type="submit" variant="primary" icon="search">
        {t("store:search.submit")}
      </Button>
    </form>
  );
}
