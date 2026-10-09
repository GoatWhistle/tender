import { Link } from "react-router-dom";
import type { ProductSummary } from "../api";
import { price } from "../lib/format";
import { Ring } from "./Ring";
import { SpecPlate } from "./SpecPlate";

export function ProductCard({ p }: { p: ProductSummary }) {
  return (
    <Link to={`/product/${p.id}`} className="card">
      <SpecPlate category={p.category} code={p.position_code}>
        <span className="plate__ring">
          <Ring filled={p.required_filled} total={p.required_total} size={40} />
        </span>
      </SpecPlate>
      <div className="card__body">
        <span className="card__eyebrow">{p.position_name}</span>
        <h3 className="card__title">{p.title}</h3>
        <span className="card__price">от {price(p.price)}</span>
      </div>
    </Link>
  );
}

export function CardSkeleton() {
  return (
    <div className="card card--skeleton" aria-hidden="true">
      <div className="plate plate--card skeleton" />
      <div className="card__body">
        <span className="skeleton skeleton--line" />
        <span className="skeleton skeleton--title" />
        <span className="skeleton skeleton--line" />
      </div>
    </div>
  );
}
