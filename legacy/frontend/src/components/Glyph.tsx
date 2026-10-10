// Линейные рисунки категорий вместо фотографий: тонкий белый штрих на чёрном.
import type { CategoryName } from "../lib/categories";

const PATHS: Record<CategoryName, JSX.Element> = {
  Одежда: (
    <>
      <path d="M44 18h24l-12 10z" />
      <path d="M44 18 22 28 14 70h12l6-30v58h48V40l6 30h12l-8-42-22-10" />
      <path d="M56 28v70M50 44h12M50 60h12M50 76h12" />
    </>
  ),
  Мебель: (
    <>
      <path d="M14 46h84v6H14z" />
      <path d="M20 52v40M92 52v40" />
      <path d="M28 52v24h56V52" />
      <path d="M28 64h56M56 52v24" />
      <path d="M40 46V24h32v22" />
    </>
  ),
  Инструменты: (
    <>
      <path d="M22 40h46v18H22z" />
      <path d="M68 44h14v10H68M82 49h16" />
      <path d="M32 58l-6 32h18l4-32" />
      <path d="M30 70h14M22 49h-6" />
      <path d="M50 40V30h10v10" />
    </>
  ),
};

export function Glyph({ category, className }: { category: string; className?: string }) {
  const paths = PATHS[category as CategoryName];
  return (
    <svg
      className={className}
      viewBox="0 0 112 112"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      vectorEffect="non-scaling-stroke"
      aria-hidden="true"
    >
      {paths}
    </svg>
  );
}

export function Arrow({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      aria-hidden="true"
    >
      <path
        d="M5 12h14M13 6l6 6-6 6"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function Search({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      aria-hidden="true"
    >
      <circle cx="11" cy="11" r="6.5" strokeWidth="1.75" />
      <path d="m16 16 4 4" strokeWidth="1.75" strokeLinecap="round" />
    </svg>
  );
}
