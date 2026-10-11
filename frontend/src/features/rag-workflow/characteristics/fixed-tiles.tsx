import { BackendText } from "@/shared/ui/message"
import styles from "./fixed-tiles.module.css"

export function FixedTiles({ entries }: { readonly entries: readonly [string, string][] }) {
  return (
    <dl className={styles.tiles}>
      {entries.map(([name, value]) => (
        <div key={name}>
          <dt>
            <BackendText>{name}</BackendText>
          </dt>
          <dd>
            <BackendText>{value}</BackendText>
          </dd>
        </div>
      ))}
    </dl>
  )
}
