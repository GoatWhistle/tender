import fs from "node:fs"
import os from "node:os"
import path from "node:path"
import { pathToFileURL } from "node:url"
import { launch } from "./browser.mjs"

const ROOT = path.resolve(import.meta.dirname, "..")
const REPO = path.resolve(ROOT, "..")
const DATA = path.join(ROOT, "favicons", "favicons.json")
const LOGO = path.join(REPO, "frontend", "src", "shared", "assets", "portal-logo.svg")
const FONTS = path.join(REPO, "frontend", "public", "fonts", "open-sans")
const OUT = path.join(REPO, "frontend", "public")
const MARK_EDGE = 45

const data = JSON.parse(fs.readFileSync(DATA, "utf8"))
const logo = fs.readFileSync(LOGO, "utf8")
const groups = [...logo.matchAll(/<g transform="translate\(([\d.]+) ([\d.]+)\)">.*?<\/g>/g)]
const markGroups = groups.filter((g) => Number(g[1]) < MARK_EDGE).map((g) => g[0]).join("")
if (!markGroups) throw new Error("logo mark not found")

const fontFaces = ["cyrillic", "latin"]
  .map((range) => {
    const url = pathToFileURL(path.join(FONTS, `open-sans-${range}-wght-normal.woff2`)).href
    return `@font-face{font-family:"Open Sans";src:url("${url}") format("woff2");font-weight:300 800;font-display:block}`
  })
  .join("")

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "favicons-"))
const browser = await launch()
const page = await browser.newPage()

const show = async (html, width, height) => {
  const file = path.join(tmp, "page.html")
  fs.writeFileSync(
    file,
    `<!doctype html><meta charset="utf-8"><style>${fontFaces}*{margin:0;box-sizing:border-box}html,body{width:${width}px;height:${height}px;overflow:hidden;background:transparent}</style>${html}`,
  )
  await page.setViewportSize({ width, height })
  await page.goto(pathToFileURL(file).href)
  await page.evaluate(() => document.fonts.ready)
}

await show(`<svg id="probe" width="200" height="200"><g id="mark">${markGroups}</g></svg>`, 200, 200)
const box = await page.evaluate(() => {
  const b = document.getElementById("mark").getBBox()
  return { x: b.x, y: b.y, width: b.width, height: b.height }
})
const side = Math.max(box.width, box.height)
const viewBox = [box.x - (side - box.width) / 2, box.y - (side - box.height) / 2, side, side]
  .map((n) => Number(n.toFixed(4)))
  .join(" ")
const markSvg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${viewBox}" fill="none">${markGroups}</svg>`
fs.writeFileSync(path.join(OUT, "favicon.svg"), `${markSvg}\n`)

const icon = async (size, { background = "transparent", padding = 0 } = {}) => {
  const inner = Math.round(size * (1 - padding * 2))
  await show(
    `<div style="width:${size}px;height:${size}px;display:grid;place-items:center;background:${background}"><div style="width:${inner}px;height:${inner}px">${markSvg.replace("<svg ", '<svg width="100%" height="100%" ')}</div></div>`,
    size,
    size,
  )
  return page.screenshot({ type: "png", omitBackground: background === "transparent" })
}

const ico = (images) => {
  const header = Buffer.alloc(6 + images.length * 16)
  header.writeUInt16LE(0, 0)
  header.writeUInt16LE(1, 2)
  header.writeUInt16LE(images.length, 4)
  let offset = header.length
  images.forEach(({ size, png }, i) => {
    const entry = 6 + i * 16
    header.writeUInt8(size >= 256 ? 0 : size, entry)
    header.writeUInt8(size >= 256 ? 0 : size, entry + 1)
    header.writeUInt16LE(1, entry + 4)
    header.writeUInt16LE(32, entry + 6)
    header.writeUInt32LE(png.length, entry + 8)
    header.writeUInt32LE(offset, entry + 12)
    offset += png.length
  })
  return Buffer.concat([header, ...images.map((image) => image.png)])
}

const icoImages = []
for (const size of [16, 32, 48]) icoImages.push({ size, png: await icon(size) })
fs.writeFileSync(path.join(OUT, "favicon.ico"), ico(icoImages))

const plates = {
  "apple-touch-icon.png": [180, { background: data.background, padding: 0.14 }],
  "icon-192.png": [192, { background: data.background, padding: 0.1 }],
  "icon-512.png": [512, { background: data.background, padding: 0.1 }],
  "icon-maskable-512.png": [512, { background: data.background, padding: 0.22 }],
}
for (const [name, [size, options]] of Object.entries(plates)) {
  fs.writeFileSync(path.join(OUT, name), await icon(size, options))
}

const escape = (text) => text.replace(/&/g, "&amp;").replace(/</g, "&lt;")
const logoSvg = logo.replace(/<svg [^>]*?width="[^"]*" height="[^"]*"/, (tag) =>
  tag.replace(/width="[^"]*" height="[^"]*"/, 'width="360" height="79.45"'),
)
await show(
  `<div style="width:1200px;height:630px;display:flex;flex-direction:column;justify-content:space-between;padding:72px 80px 0;background:${data.og.background};font-family:'Open Sans';color:${data.og.text}">
    <div>${logoSvg}</div>
    <div style="padding-bottom:64px">
      <div style="font-size:60px;line-height:1.15;font-weight:700;letter-spacing:-0.01em;max-width:1000px">${escape(data.og.title)}</div>
      <div style="margin-top:24px;font-size:28px;line-height:1.4;color:${data.og.muted};max-width:900px">${escape(data.og.subtitle)}</div>
    </div>
    <div style="height:16px;margin:0 -80px;background:${data.og.accent}"></div>
  </div>`,
  1200,
  630,
)
await page.screenshot({ path: path.join(OUT, "og-image.png"), type: "png" })

const manifest = {
  name: data.name,
  short_name: data.shortName,
  description: data.og.subtitle,
  lang: "ru",
  start_url: "/",
  scope: "/",
  display: "standalone",
  background_color: data.background,
  theme_color: data.themeColor,
  icons: [
    { src: "/icon-192.png", sizes: "192x192", type: "image/png" },
    { src: "/icon-512.png", sizes: "512x512", type: "image/png" },
    { src: "/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
  ],
}
fs.writeFileSync(path.join(OUT, "site.webmanifest"), `${JSON.stringify(manifest, null, 2)}\n`)

await browser.close()
fs.rmSync(tmp, { recursive: true, force: true })
console.log(`frontend/public: favicon.svg, favicon.ico (16, 32, 48), apple-touch-icon, icon-192/512, maskable, og-image 1200x630, site.webmanifest`)
