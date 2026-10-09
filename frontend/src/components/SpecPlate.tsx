// Визуал вместо фото: светлое поле с оттенком категории, рисунок категории и код КТРУ.
import type { ReactNode } from "react";
import { byName } from "../lib/categories";
import { Glyph } from "./Glyph";

type Props = {
  category: string;
  code: string;
  size?: "card" | "tile";
  children?: ReactNode;
};

export function SpecPlate({ category, code, size = "card", children }: Props) {
  return (
    <div className={`plate plate--${size} plate--${byName(category)?.slug ?? "none"}`}>
      <Glyph category={category} className="plate__glyph" />
      <span className="plate__chip">КТРУ {code}</span>
      {children}
    </div>
  );
}
