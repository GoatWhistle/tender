import { Link } from "react-router-dom";
import type { ProductSummary } from "../api";
import { price } from "../lib/format";
import { SpecPlate } from "./SpecPlate";

export function ProductCard({ p }: { p: ProductSummary }) {
  const complete = p.required_filled === p.required_total;
  return (
    <Link to={`/product/${p.id}`} className="card">
      <SpecPlate category={p.category} code={p.position_code} />
      <div className="card__body">
        <span className="card__eyebrow">{p.position_name}</span>
        <h3 className="card__title">{p.title}</h3>
        <div className="card__meta">
          <span className="card__price">от {price(p.price)}</span>
          <span className={complete ? "card__fill" : "card__fill card__fill--gap"}>
            {p.required_filled}/{p.required_total} обяз.
          </span>
        </div>
      </div>
    </Link>
  );
}

export function CardSkeleton() {
  return (
    <div className="card card--skeleton" aria-hidden="true">
      <div className="plate plate--card" />
      <div className="card__body">
        <span className="skeleton skeleton--line" />
        <span className="skeleton skeleton--title" />
        <span className="skeleton skeleton--line" />
      </div>
    </div>
  );
}
