// «Табличка оборудования» на месте фото: рисунок категории, сетка и маркировка кода КТРУ.
import { byName } from "../lib/categories";
import { Glyph } from "./Glyph";

type Props = {
  category: string;
  code: string;
  caption?: string;
  size?: "card" | "hero";
};

export function SpecPlate({ category, code, caption, size = "card" }: Props) {
  return (
    <div className={`plate plate--${size}`}>
      <div className="plate__grid" aria-hidden="true" />
      <Glyph category={category} className="plate__glyph" />
      <span className="plate__mark plate__mark--tl">{byName(category)?.index ?? "00"}</span>
      <span className="plate__mark plate__mark--tr">{category}</span>
      <span className="plate__mark plate__mark--bl">КТРУ {code}</span>
      {caption && <span className="plate__mark plate__mark--br">{caption}</span>}
    </div>
  );
}
