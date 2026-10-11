import type { ButtonHTMLAttributes } from "react"
import styles from "./text-button.module.css"

export function TextButton(props: ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button {...props} type={props.type ?? "button"} className={styles.button} />
}
