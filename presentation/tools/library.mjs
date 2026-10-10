import { spawnSync } from "node:child_process"
import fs from "node:fs"
import path from "node:path"
import { DeckError, LIBRARY, ROOT, assemble } from "./assemble.mjs"
import { launch } from "./browser.mjs"

const OUT = path.join(ROOT, "dist", "library.html")
const SHOTS = path.join(ROOT, "shots", "library")
const SHEET = path.join(ROOT, "shots", "library.png")

try {
  const { html, slides } = assemble({ inline: true, slidesDir: LIBRARY })
  fs.mkdirSync(path.dirname(OUT), { recursive: true })
  fs.writeFileSync(OUT, html)
  console.log(`dist/library.html: ${slides} layouts`)
} catch (error) {
  if (!(error instanceof DeckError)) throw error
  console.error(`library build failed\n${error.message}`)
  process.exit(1)
}

fs.rmSync(SHOTS, { recursive: true, force: true })
const shot = spawnSync(process.execPath, [path.join(ROOT, "tools", "shot.mjs"), "--deck", "dist/library.html", "--out", "shots/library"], {
  cwd: ROOT,
  stdio: "inherit",
})

const layouts = fs
  .readdirSync(LIBRARY, { withFileTypes: true })
  .filter((entry) => entry.isDirectory() && /^\d{2}-/.test(entry.name))
  .map((entry) => {
    const html = fs.readFileSync(path.join(LIBRARY, entry.name, "slide.html"), "utf8")
    const title = /data-title="([^"]*)"/.exec(html)?.[1] ?? ""
    const image = fs
      .readdirSync(SHOTS)
      .filter((name) => name.startsWith(entry.name))
      .sort()
      .at(-1)
    return { name: entry.name, title, image: image ? `data:image/png;base64,${fs.readFileSync(path.join(SHOTS, image)).toString("base64")}` : null }
  })

const escape = (text) => String(text).replaceAll("&", "&amp;").replaceAll("<", "&lt;")
const tiles = layouts
  .map((item) => `<figure>${item.image ? `<img src="${item.image}">` : "<div></div>"}<figcaption><b>${escape(item.name)}</b> ${escape(item.title)}</figcaption></figure>`)
  .join("")
const page = `<!doctype html><meta charset="utf-8"><style>
  body{margin:0;padding:24px;background:#8a8a8a;font:16px system-ui,sans-serif;color:#111}
  main{display:grid;grid-template-columns:repeat(4,480px);gap:20px}
  figure{margin:0;display:grid;gap:8px}
  img,figure div{display:block;width:480px;height:270px;border-radius:6px;background:#fff}
  figcaption{color:#fff}
</style><main>${tiles}</main>`

const browser = await launch()
const sheet = await browser.newPage({ viewport: { width: 4 * 500 + 28, height: 800 }, deviceScaleFactor: 1 })
await sheet.setContent(page)
await sheet.evaluate(() => Promise.all([...document.images].map((img) => img.decode().catch(() => null))))
await sheet.screenshot({ path: SHEET, fullPage: true })
await browser.close()
console.log(`shots/library.png: ${layouts.length} layouts on one sheet; open dist/library.html to see them animated`)
if (shot.status !== 0) process.exit(shot.status ?? 1)
