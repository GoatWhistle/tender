import fs from "node:fs"
import path from "node:path"
import { REPO, SRC } from "./assemble.mjs"

const SITE = path.join(REPO, "frontend", "src", "shared", "styles", "tokens")
const DECK = path.join(SRC, "core", "css")
const FILES = ["palette.css", "radius.css", "typography.css", "elevation.css"]
const FIX = "run cd frontend && npm run tokens:export -- --fonts"

const declarations = (text) => {
  const found = new Map()
  for (const match of text.replace(/\/\*[\s\S]*?\*\//g, "").matchAll(/(--[a-z0-9-]+)\s*:\s*([^;]+);/g)) {
    if (!found.has(match[1])) found.set(match[1], match[2].replace(/\s+/g, " ").trim())
  }
  return found
}

export const siteSync = () => {
  const errors = []
  const warnings = []
  if (!fs.existsSync(SITE)) return { errors, warnings }
  const deckFile = path.join(DECK, "tokens.css")
  if (!fs.existsSync(deckFile)) return { errors: [`src/core/css/tokens.css is missing, ${FIX}`], warnings }
  const deck = declarations(fs.readFileSync(deckFile, "utf8"))
  const drift = []
  for (const name of FILES) {
    const file = path.join(SITE, name)
    if (!fs.existsSync(file)) continue
    for (const [key, value] of declarations(fs.readFileSync(file, "utf8"))) {
      if (deck.has(key) && deck.get(key) !== value) drift.push(`${key} is ${value} on the site, ${deck.get(key)} here`)
      if (!deck.has(key)) drift.push(`${key} from the site is missing here`)
    }
  }
  if (drift.length) errors.push(`images are not in the site's design system (${drift.length} tokens differ, first: ${drift[0]}); ${FIX}`)
  if (!fs.existsSync(path.join(DECK, "fonts.css"))) warnings.push(`the site's fonts are not exported, images fall back to system fonts; ${FIX}`)
  return { errors, warnings }
}
