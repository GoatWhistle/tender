import {
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  CircleAlert,
  Download,
  FileText,
  Globe,
  Info,
  ListFilter,
  LoaderCircle,
  MessageSquare,
  Moon,
  Pencil,
  Plus,
  Search,
  ShieldCheck,
  Sun,
  User,
} from "lucide-react"

const icons = {
  download: Download,
  back: ArrowLeft,
  next: ArrowRight,
  check: Check,
  success: CheckCircle2,
  expand: ChevronDown,
  chevron: ChevronRight,
  alert: CircleAlert,
  document: FileText,
  language: Globe,
  info: Info,
  rank: ListFilter,
  loading: LoaderCircle,
  message: MessageSquare,
  moon: Moon,
  edit: Pencil,
  plus: Plus,
  search: Search,
  send: ArrowUp,
  shield: ShieldCheck,
  sun: Sun,
  user: User,
}
export type IconName = keyof typeof icons
export function Icon({ name, size = 18 }: { readonly name: IconName; readonly size?: number }) {
  const Component = icons[name]
  return <Component size={size} strokeWidth={1.7} aria-hidden="true" />
}
