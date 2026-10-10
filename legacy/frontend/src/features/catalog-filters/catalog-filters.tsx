import { useState } from "react";
import type { Facet, ProductPage } from "../../api";
import { shortLabel } from "../../lib/format";
import { Collapse } from "../../shared/motion";
import { t } from "../../shared/i18n";
import { Button } from "../../shared/ui/button/button";
import { ChoiceList } from "../../shared/ui/choice/choice-list";
import { Disclosure } from "../../shared/ui/disclosure/disclosure";
import styles from "./catalog-filters.module.css";

const LIMIT = 6;

export interface CatalogFiltersProps {
  readonly data: ProductPage;
  readonly position: string | null;
  readonly filters: Record<string, string[]>;
  readonly onPosition: (code: string | null) => void;
  readonly onFacet: (characteristic: string, values: string[]) => void;
}

function FacetBlock({
  facet,
  selected,
  onChange,
  open,
}: {
  readonly facet: Facet;
  readonly selected: string[];
  readonly onChange: (values: string[]) => void;
  readonly open: boolean;
}) {
  const [all, setAll] = useState(false);
  const options = facet.values.map((v) => ({
    id: v.code,
    label: shortLabel(v.label, v.unit),
    hint: String(v.count),
  }));
  const extra = options.length - LIMIT;
  return (
    <Disclosure summary={facet.name} defaultOpen={open || selected.length > 0}>
      <ChoiceList
        compact
        multiple
        legend={facet.name}
        options={options.slice(0, LIMIT)}
        value={selected}
        onChange={onChange}
      />
      <Collapse open={all}>
        <ChoiceList
          compact
          multiple
          legend={facet.name}
          options={options.slice(LIMIT)}
          value={selected}
          onChange={onChange}
        />
      </Collapse>
      {extra > 0 && (
        <Button variant="ghost" size="sm" onClick={() => setAll(!all)}>
          {all ? t("store:catalog.less") : t("store:catalog.more", { count: extra })}
        </Button>
      )}
    </Disclosure>
  );
}

export function CatalogFilters({
  data,
  position,
  filters,
  onPosition,
  onFacet,
}: CatalogFiltersProps) {
  const total = data.positions.reduce((n, p) => n + p.count, 0);
  const options = [
    { id: "", label: t("store:catalog.allPositions"), hint: String(total) },
    ...data.positions.map((p) => ({ id: p.code, label: p.name, hint: String(p.count) })),
  ];
  return (
    <div className={styles.filters}>
      <section className={styles.group}>
        <h2 className={styles.title}>{t("store:catalog.position")}</h2>
        <ChoiceList
          compact
          legend={t("store:catalog.position")}
          options={options}
          value={[position ?? ""]}
          onChange={([code]) => onPosition(code ? code : null)}
        />
      </section>
      <Collapse open={!position}>
        <p className={styles.hint}>{t("store:catalog.facetsHint")}</p>
      </Collapse>
      <Collapse open={Boolean(position)}>
        <div className={styles.facets}>
          {data.facets.map((f, i) => (
            <FacetBlock
              key={f.code}
              facet={f}
              open={i < 3}
              selected={filters[f.code] ?? []}
              onChange={(values) => onFacet(f.code, values)}
            />
          ))}
        </div>
      </Collapse>
    </div>
  );
}
