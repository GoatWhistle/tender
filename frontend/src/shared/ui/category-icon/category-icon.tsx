import styles from "./category-icon.module.css"
import { categoryIcon } from "./icons"

const sizes = { sm: 18, lg: 28 }

export function CategoryIcon({
  code,
  size = "sm",
}: {
  readonly code: string
  readonly size?: keyof typeof sizes
}) {
  const Component = categoryIcon(code)
  return (
    <span className={styles.tile} data-size={size} aria-hidden="true">
      <Component size={sizes[size]} strokeWidth={1.6} />
    </span>
  )
}
