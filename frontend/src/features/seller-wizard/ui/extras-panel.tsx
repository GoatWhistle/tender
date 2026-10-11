import { useState, type FormEvent } from "react";
import type { Session, Suggestion } from "../../../entities/rag";
import { t } from "../../../shared/i18n";
import { Collapse } from "../../../shared/motion";
import { Banner } from "../../../shared/ui/banner/banner";
import { Button } from "../../../shared/ui/button/button";
import { Section } from "../../../shared/ui/section/section";
import { TextField } from "../../../shared/ui/field/text-field";
import { StatusBadge } from "../../../shared/ui/status-badge/status-badge";
import type { RagWizard } from "../model/use-rag-wizard";
import styles from "./extras-panel.module.css";

function split(text: string): { name: string; value: string } | null {
  const at = text.search(/[=:]/);
  if (at <= 0) return null;
  const name = text.slice(0, at).trim();
  const value = text.slice(at + 1).trim();
  return name && value ? { name, value } : null;
}

function SuggestionItem({
  item,
  busy,
  onAdd,
}: {
  readonly item: Suggestion;
  readonly busy: boolean;
  readonly onAdd: () => void;
}) {
  const value = item.value || item.options.join(", ");
  return (
    <li className={styles.suggestion}>
      <div className={styles.suggestionMain}>
        <span className={styles.suggestionName}>
          {item.name}
          {item.unit && <span className={styles.unit}>, {item.unit}</span>}
        </span>
        {value && <span className={styles.suggestionValue}>{value}</span>}
        {item.why && <span className={styles.why}>{item.why}</span>}
      </div>
      <div className={styles.suggestionSide}>
        <StatusBadge
          tone={item.source === "СТЕ" ? "info" : "neutral"}
          label={
            typeof item.share === "number"
              ? t("seller:extras.shareSource", {
                  source: item.source,
                  share: Math.round(item.share * 100),
                })
              : item.source
          }
        />
        <Button size="sm" variant="secondary" icon="plus" disabled={busy || !value} onClick={onAdd}>
          {t("seller:extras.add")}
        </Button>
      </div>
    </li>
  );
}

export function ExtrasPanel({
  wizard,
  session,
}: {
  readonly wizard: RagWizard;
  readonly session: Session;
}) {
  const [text, setText] = useState("");
  const [reason, setReason] = useState("");
  const parsed = split(text);
  const verdict = wizard.verdict;
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!parsed) return;
    wizard.addExtra({ ...parsed, reason: reason.trim() }, () => {
      setText("");
      setReason("");
    });
  };
  return (
    <Section
      title={t("seller:extras.title")}
      lead={t("seller:extras.lead")}
      actions={
        <Button variant="secondary" icon="products" disabled={wizard.busy} onClick={wizard.suggest}>
          {t("seller:extras.suggest")}
        </Button>
      }
    >
      {session.extras.length > 0 && (
        <ul className={styles.extras}>
          {session.extras.map((extra, index) => (
            <li key={`${extra.name}-${extra.value}`} className={styles.extra}>
              <span className={styles.extraName}>{extra.name}</span>
              <span>{extra.value}</span>
              <StatusBadge tone="success" label={t("seller:extras.checked")} />
              <Button
                variant="ghost"
                size="sm"
                icon="trash"
                disabled={wizard.busy}
                aria-label={t("seller:extras.remove", { name: extra.name })}
                onClick={() => wizard.removeExtra(index)}
              />
            </li>
          ))}
        </ul>
      )}
      <form className={styles.form} onSubmit={submit}>
        <TextField
          label={t("seller:extras.field")}
          placeholder={t("seller:extras.placeholder")}
          value={text}
          disabled={wizard.busy}
          onChange={(e) => setText(e.target.value)}
        />
        <TextField
          label={t("seller:extras.reason")}
          value={reason}
          disabled={wizard.busy}
          onChange={(e) => setReason(e.target.value)}
        />
        <Button type="submit" variant="primary" icon="plus" disabled={wizard.busy || !parsed}>
          {t("seller:extras.check")}
        </Button>
      </form>
      <Collapse open={Boolean(verdict && !verdict.accepted)}>
        {verdict && !verdict.accepted && (
          <Banner
            tone="error"
            title={t("seller:extras.rejected")}
            actions={
              verdict.fixed && (
                <Button
                  size="sm"
                  disabled={wizard.busy}
                  onClick={() => verdict.fixed && wizard.addExtra(verdict.fixed)}
                >
                  {t("seller:extras.applyFix", {
                    name: verdict.fixed.name,
                    value: verdict.fixed.value,
                  })}
                </Button>
              )
            }
          >
            {verdict.problems.map((p) => (
              <p key={p}>{p}</p>
            ))}
          </Banner>
        )}
      </Collapse>
      <Collapse open={Boolean(verdict?.accepted && verdict.warnings.length)}>
        {verdict && verdict.warnings.length > 0 && (
          <Banner tone="warning" title={t("seller:extras.warnings")}>
            {verdict.warnings.map((w) => (
              <p key={w}>{w}</p>
            ))}
          </Banner>
        )}
      </Collapse>
      <Collapse open={wizard.suggestions !== null}>
        {wizard.suggestions && (
          <div className={styles.suggestions}>
            <p className={styles.caption}>
              {wizard.suggestions.length
                ? t("seller:extras.suggestions", { count: wizard.suggestions.length })
                : t("seller:extras.noSuggestions")}
            </p>
            <ul className={styles.suggestionList}>
              {wizard.suggestions.map((item) => (
                <SuggestionItem
                  key={item.name}
                  item={item}
                  busy={wizard.busy}
                  onAdd={() =>
                    wizard.addExtra({
                      name: item.unit ? `${item.name}, ${item.unit}` : item.name,
                      value: item.value || item.options[0] || "",
                      reason: item.why,
                    })
                  }
                />
              ))}
            </ul>
          </div>
        )}
      </Collapse>
    </Section>
  );
}
