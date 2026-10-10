import fs from "node:fs"
import path from "node:path"
import { pathToFileURL } from "node:url"
import { chromium } from "playwright-core"
import { ROOT } from "./assemble.mjs"

export const DECK = path.join(ROOT, "dist", "deck.html")

export const launch = async () => {
  const executablePath = process.env.CHROME_PATH
  const attempts = executablePath
    ? [{ executablePath }]
    : [{}, { channel: process.env.CHROME_CHANNEL || "chrome" }]
  let failure
  for (const options of attempts) {
    try {
      return await chromium.launch(options)
    } catch (error) {
      failure = error
    }
  }
  console.error("cannot start Chrome: set CHROME_PATH, install Google Chrome or run npx playwright install chromium")
  console.error(String(failure?.message).split("\n")[0])
  process.exit(2)
}

export const requireDeck = (file = DECK) => {
  if (!fs.existsSync(file)) {
    console.error(`${path.relative(ROOT, file)} not found, run npm run build first`)
    process.exit(1)
  }
}

export const deckUrl = (query = "", hash = "", file = DECK) => `${pathToFileURL(file).href}${query}${hash}`

export const waitReady = (page) =>
  page.waitForFunction(() => document.documentElement.classList.contains("is-ready"), null, { timeout: 15000 })
