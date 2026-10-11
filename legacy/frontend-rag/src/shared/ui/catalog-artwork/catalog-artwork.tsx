import styles from "./catalog-artwork.module.css"

export function CatalogArtwork() {
  return (
    <div className={styles.artwork} aria-hidden="true">
      <svg aria-hidden="true" viewBox="0 0 360 200" fill="none" focusable="false">
        <g stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <path
            className={styles.guide}
            d="M12 164h336M36 180h48m224 0h24M42 64h34m208-26h36M24 108h26"
          />
          <rect
            className={styles.back}
            x="76"
            y="35"
            width="114"
            height="130"
            rx="10"
            transform="rotate(-12 76 35)"
          />
          <rect className={styles.sheet} x="122" y="20" width="128" height="145" rx="10" />
          <path d="M144 43h44m-44 12h76M144 82h12m14 0h49M144 105h12m14 0h49M144 128h12m14 0h32" />
          <path className={styles.accent} d="m143 80 4 4 8-9m-12 28 4 4 8-9m-12 28 4 4 8-9" />
          <circle className={styles.sheet} cx="260" cy="143" r="31" />
          <path className={styles.accent} d="m247 143 9 9 18-20M291 174l17 17" />
          <path className={styles.guide} d="M297 85h22m-11-11v22M51 139h14m-7-7v14" />
        </g>
      </svg>
    </div>
  )
}
