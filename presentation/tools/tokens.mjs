import fs from "node:fs"
import path from "node:path"
import { REPO, SRC } from "./assemble.mjs"

const SITE = path.join(REPO, "frontend", "src", "shared", "styles", "tokens")
const SITE_FONTS = path.join(REPO, "frontend", "public")
const DECK = path.join(SRC, "core", "css")
const FILES = ["palette.css", "radius.css", "space.css", "typography.css", "elevation.css", "motion.css", "semantic.css"]
const SCOPE = ":root:has([data-portal])"

const CONTRACT = {
  "--surface-base": "var(--surface-page)",
  "--surface-raised": "var(--surface-card)",
  "--surface-sunken": "var(--surface-field)",
  "--status-success": "var(--text-success)",
  "--status-warning": "var(--text-warning)",
  "--status-danger": "var(--text-error)",
  "--shadow-raised": "var(--shadow-card)",
  "--shadow-float": "var(--shadow-popup)",
}

const GLOBAL = {
  "--font-sans": "var(--font-family)",
  "--font-mono": "var(--font-family)",
  "--radius-md": "var(--radius-sm)",
  "--radius-lg": "var(--radius-sm)",
  "--radius-pill": "var(--radius-sm)",
}

const blocks = (css) => {
  const found = []
  let depth = 0
  let start = 0
  let head = ""
  for (let i = 0; i < css.length; i += 1) {
    if (css[i] === "{") {
      if (depth === 0) {
        head = css.slice(start, i).trim()
        start = i + 1
      }
      depth += 1
    } else if (css[i] === "}") {
      depth -= 1
      if (depth === 0) {
        found.push({ head, body: css.slice(start, i).trim() })
        start = i + 1
      }
    }
  }
  return found
}

const selectorFor = (head, file) => {
  if (head === `${SCOPE}[data-theme="dark"]`) return '[data-theme="dark"]'
  if (head === SCOPE) return file === "semantic.css" ? ':root,\n[data-theme="light"]' : ":root"
  return null
}

const rule = (selector, entries) =>
  `${selector} {\n${entries.map(([key, value]) => `  ${key}: ${value};`).join("\n")}\n}`

const parts = []
const faces = []
for (const file of FILES) {
  const css = fs.readFileSync(path.join(SITE, file), "utf8").replace(/\/\*[\s\S]*?\*\//g, "")
  for (const { head, body } of blocks(css)) {
    if (head === "@font-face") {
      faces.push(body)
      continue
    }
    const selector = selectorFor(head, file)
    if (!selector) continue
    const lines = body.replace(/\s+/g, " ").split(";").map((line) => line.trim()).filter(Boolean)
    const entries = lines.filter((line) => line.startsWith("--")).map((line) => {
      const at = line.indexOf(":")
      return [line.slice(0, at).trim(), line.slice(at + 1).trim()]
    })
    if (entries.length) parts.push(rule(selector, entries))
  }
}

const contract = Object.entries(CONTRACT)
parts.push(rule(':root,\n[data-theme="light"]', contract))
parts.push(rule('[data-theme="dark"]', contract))
parts.push(rule(":root", Object.entries(GLOBAL)))
fs.writeFileSync(path.join(DECK, "tokens.css"), `${parts.join("\n\n")}\n`)

const fontsDir = path.join(DECK, "fonts")
fs.mkdirSync(fontsDir, { recursive: true })
const fontCss = faces.map((body) => {
  const local = body.replace(/url\("\/([^"]+)"\)/g, (match, ref) => {
    const name = path.basename(ref)
    fs.copyFileSync(path.join(SITE_FONTS, ref), path.join(fontsDir, name))
    return `url("fonts/${name}")`
  })
  return `@font-face {\n  ${local.replace(/\s*;\s*/g, ";\n  ").trim()}\n}`
})
fs.writeFileSync(path.join(DECK, "fonts.css"), `${fontCss.join("\n\n").replace(/\n  \n}/g, "\n}")}\n`)

console.log(`tokens: ${parts.length} blocks from frontend/src/shared/styles/tokens into src/core/css/tokens.css; fonts: ${faces.length} faces`)
