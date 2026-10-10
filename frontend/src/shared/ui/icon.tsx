import { Globe, LoaderCircle, Moon, Sun } from "lucide-react"
import Alert from "@/shared/assets/icons/alert.svg?react"
import Back from "@/shared/assets/icons/back.svg?react"
import Check from "@/shared/assets/icons/check.svg?react"
import Chevron from "@/shared/assets/icons/chevron.svg?react"
import Download from "@/shared/assets/icons/download.svg?react"
import Edit from "@/shared/assets/icons/edit.svg?react"
import Expand from "@/shared/assets/icons/expand.svg?react"
import Next from "@/shared/assets/icons/next.svg?react"
import Plus from "@/shared/assets/icons/plus.svg?react"
import Rank from "@/shared/assets/icons/rank.svg?react"
import Search from "@/shared/assets/icons/search.svg?react"
import Send from "@/shared/assets/icons/send.svg?react"
import Success from "@/shared/assets/icons/success.svg?react"
import User from "@/shared/assets/icons/user.svg?react"

const portal = {
  alert: Alert,
  back: Back,
  check: Check,
  chevron: Chevron,
  download: Download,
  edit: Edit,
  expand: Expand,
  next: Next,
  plus: Plus,
  rank: Rank,
  search: Search,
  send: Send,
  success: Success,
  user: User,
}
const stroked = { language: Globe, loading: LoaderCircle, moon: Moon, sun: Sun }
export type IconName = keyof typeof portal | keyof typeof stroked

export function Icon({ name, size = 20 }: { readonly name: IconName; readonly size?: number }) {
  if (name in portal) {
    const Art = portal[name as keyof typeof portal]
    return <Art width={size} height={size} aria-hidden="true" focusable="false" />
  }
  const Art = stroked[name as keyof typeof stroked]
  return <Art size={size} strokeWidth={1.8} aria-hidden="true" />
}
