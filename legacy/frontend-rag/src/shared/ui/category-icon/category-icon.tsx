import styles from "./category-icon.module.css"
import { categoryIcon } from "./icons"

const sizes = { sm: 18, lg: 28, xl: 64 }

function tone(code: string) {
  const section = Number.parseInt(code.slice(0, 2), 10)
  if (section <= 12) return "green"
  if (section <= 18 || section === 31 || section === 32) return "orange"
  if (section <= 33) return "sea"
  return "blue"
}

export function CategoryIcon({
  code,
  size = "sm",
}: {
  readonly code: string
  readonly size?: keyof typeof sizes
}) {
  const Component = categoryIcon(code)
  return (
    <span className={styles.tile} data-size={size} data-tone={tone(code)} aria-hidden="true">
      <Component size={sizes[size]} strokeWidth={1.6} />
    </span>
  )
}
