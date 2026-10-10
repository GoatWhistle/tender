import fs from "node:fs"
import path from "node:path"
import { pathToFileURL } from "node:url"
import { ROOT } from "./assemble.mjs"
import { launch } from "./browser.mjs"
import { siteSync } from "./site-tokens.mjs"

const DIR = path.join(ROOT, "thumbnail")
const SOURCE = path.join(DIR, "thumbnail.html")
const DATA = path.join(DIR, "thumbnail.json")
const OUT = path.join(DIR, "out")
const PREVIEW = path.join(ROOT, "shots", "thumbnail-preview.png")
const MAX_BYTES = 2 * 1024 * 1024
const GLYPHS = /[\u2014\u00b7\u2190-\u21ff\u2794\u279c\u27a1\u2713-\u2718\u2705\u274c\u25b6\u25b8]/u
const EMOJI = /\p{Extended_Pictographic}/u

const data = JSON.parse(fs.readFileSync(DATA, "utf8"))
const shell = fs.readFileSync(path.join(ROOT, "src", "shell.html"), "utf8")
const mark = /<template id="brand-mark">\s*([\s\S]*?)\s*<\/template>/.exec(shell)?.[1] ?? ""
const shotFile = data.shot ? path.resolve(DIR, data.shot) : null
const shot = shotFile && fs.existsSync(shotFile) ? pathToFileURL(shotFile).href : null
const site = siteSync()
const errors = [...site.errors]
const warnings = [...site.warnings]

const texts = (variant) =>
  [variant.hook, variant.value, variant.caption, variant.before?.label, variant.before?.value, variant.after?.label, variant.after?.value]
    .filter((text) => typeof text === "string")

for (const variant of data.variants ?? []) {
  for (const text of [...texts(variant), data.badge?.text ?? ""]) {
    if (GLYPHS.test(text) || EMOJI.test(text)) errors.push(`${variant.name}: em dash, middle dot, glyph or emoji in "${text}"`)
    if (text.includes("{{")) warnings.push(`${variant.name}: placeholder "${text}"`)
  }
  const hookWords = (variant.hook ?? "").split(/\s+/).filter(Boolean).length
  if (hookWords > 4) warnings.push(`${variant.name}: hook has ${hookWords} words, keep it at four or fewer`)
  if (variant.accent && variant.hook && !variant.accent.includes("{{") && !variant.hook.includes(variant.accent)) errors.push(`${variant.name}: accent "${variant.accent}" is not part of the hook`)
}
if (!shot) warnings.push(`no screenshot at ${path.relative(ROOT, shotFile ?? DIR)}: the shot frames render empty`)

const titles = data.titles ?? []
if (titles.length < 5) warnings.push(`only ${titles.length} titles, propose at least five`)
for (const title of titles) {
  const length = [...title].length
  if (length > 100) errors.push(`title over 100 characters (${length}): ${title}`)
  else if (length > 60) warnings.push(`title of ${length} characters is cut in search and suggestions: ${title}`)
  if (GLYPHS.test(title) || EMOJI.test(title)) errors.push(`em dash, middle dot, glyph or emoji in title: ${title}`)
  if (/\p{Lu}{4,}\s+\p{Lu}{4,}/u.test(title)) warnings.push(`caps-lock words in title: ${title}`)
  if (title.includes("{{")) warnings.push(`placeholder title: ${title}`)
}
if (new Set(titles).size !== titles.length) errors.push("duplicate titles")

fs.rmSync(OUT, { recursive: true, force: true })
fs.mkdirSync(OUT, { recursive: true })
const browser = await launch()
const page = await browser.newPage({ viewport: { width: 1400, height: 900 }, deviceScaleFactor: 1 })
await page.goto(pathToFileURL(SOURCE).href)
await page.evaluate(
  ({ data, mark, shot }) => {
    const out = document.getElementById("out")
    const icon = (name) => document.querySelector(`#icons [data-icon="${name}"]`)?.cloneNode(true)
    const fill = (root, slot, text) => {
      for (const el of root.querySelectorAll(`[data-slot="${slot}"]`)) el.textContent = text ?? ""
    }
    const hook = (el, text, accent) => {
      el.textContent = ""
      const at = accent ? text.indexOf(accent) : -1
      if (at < 0) {
        el.textContent = text
        return
      }
      const em = document.createElement("em")
      em.textContent = accent
      el.append(text.slice(0, at), em, text.slice(at + accent.length))
    }
    const image = () => {
      const img = document.createElement("img")
      img.src = shot
      return img
    }
    for (const variant of data.variants ?? []) {
      const template = document.getElementById(`layout-${variant.layout}`)
      if (!template) continue
      const node = template.content.firstElementChild.cloneNode(true)
      node.dataset.name = variant.name
      node.dataset.theme = variant.theme ?? data.theme ?? "dark"
      fill(node, "product", data.product)
      fill(node, "value", variant.value)
      fill(node, "caption", variant.caption)
      fill(node, "before-label", variant.before?.label)
      fill(node, "before-value", variant.before?.value)
      fill(node, "after-label", variant.after?.label)
      fill(node, "after-value", variant.after?.value)
      for (const el of node.querySelectorAll('[data-slot="hook"]')) hook(el, variant.hook ?? "", variant.accent)
      for (const el of node.querySelectorAll('[data-slot="badge"]')) {
        if (!data.badge?.text) {
          el.remove()
          continue
        }
        const svg = icon(data.badge.icon)
        if (svg) el.append(svg)
        el.append(data.badge.text)
      }
      for (const el of node.querySelectorAll("[data-icon-slot]")) {
        const svg = icon(el.dataset.iconSlot)
        if (svg) el.append(svg)
      }
      for (const el of node.querySelectorAll('[data-slot="shot"]')) {
        if (shot) el.append(image())
        else el.classList.add("is-empty")
      }
      for (const el of node.querySelectorAll('[data-slot="zoom"]')) {
        if (!shot || !variant.focus) {
          el.remove()
          continue
        }
        const img = image()
        img.dataset.focus = JSON.stringify(variant.focus)
        el.append(img)
      }
      out.append(node)
    }
    for (const host of document.querySelectorAll("[data-mark]")) host.innerHTML = mark
  },
  { data, mark, shot },
)
await page.evaluate(() => document.fonts.ready)
await page.evaluate(() =>
  Promise.all([...document.images].map((img) => (img.complete ? null : new Promise((done) => img.addEventListener("load", done, { once: true }))))),
)
await page.evaluate(() => {
  for (const img of document.querySelectorAll(".zoom img")) {
    const focus = JSON.parse(img.dataset.focus)
    const frame = img.closest(".thumb").querySelector(".frame")
    const size = img.parentElement.clientWidth
    const width = frame.clientWidth * focus.scale
    const height = (width * img.naturalHeight) / Math.max(1, img.naturalWidth)
    img.style.width = `${width}px`
    img.style.left = `${size / 2 - focus.x * width}px`
    img.style.top = `${size / 2 - focus.y * height}px`
  }
})
await page.evaluate(() => {
  for (const el of document.querySelectorAll("[data-fit]")) {
    const lines = Number(el.dataset.fit)
    let size = Number.parseFloat(getComputedStyle(el).fontSize)
    const min = size * 0.6
    const tooBig = () =>
      el.scrollWidth > el.clientWidth + 1 ||
      el.getBoundingClientRect().height > Number.parseFloat(getComputedStyle(el).lineHeight) * lines + 2
    while (tooBig() && size > min) {
      size -= 2
      el.style.fontSize = `${size}px`
    }
  }
})
const problems = await page.evaluate(() =>
  [...document.querySelectorAll(".thumb")].flatMap((thumb) => {
      const box = thumb.getBoundingClientRect()
      const covers = [...thumb.querySelectorAll(".frame, .zoom")].map((el) => el.getBoundingClientRect())
      return [...thumb.querySelectorAll("[data-slot]")]
        .filter((el) => el.textContent.trim() !== "" && !el.textContent.includes("{{"))
        .flatMap((el) => {
          const r = el.getBoundingClientRect()
          const found = []
          if (r.left < box.left || r.right > box.right + 1 || r.top < box.top || r.bottom > box.bottom + 1 || el.scrollWidth > el.clientWidth + 1)
            found.push(`${thumb.dataset.name}: "${el.textContent.trim().slice(0, 40)}" does not fit the frame`)
          if (r.right > box.right - 260 && r.bottom > box.bottom - 150)
            found.push(`${thumb.dataset.name}: "${el.textContent.trim().slice(0, 40)}" sits under the duration label in the bottom right corner`)
          if (covers.some((c) => r.left < c.right && r.right > c.left && r.top < c.bottom && r.bottom > c.top))
            found.push(`${thumb.dataset.name}: "${el.textContent.trim().slice(0, 40)}" does not fit, the screenshot covers it`)
          return found
        })
    }),
)
errors.push(...problems.filter((p) => p.includes("does not fit")))
warnings.push(...problems.filter((p) => p.includes("duration label")))

const files = []
const thumbs = page.locator(".thumb")
for (let i = 0; i < (await thumbs.count()); i += 1) {
  const name = await thumbs.nth(i).getAttribute("data-name")
  const file = path.join(OUT, `${name}.jpg`)
  await thumbs.nth(i).screenshot({ path: file, type: "jpeg", quality: 90 })
  const bytes = fs.statSync(file).size
  if (bytes > MAX_BYTES) errors.push(`${name}.jpg is ${(bytes / 1048576).toFixed(1)} MB, the limit is 2 MB`)
  files.push({ name, file })
}

const escape = (text) => String(text).replaceAll("&", "&amp;").replaceAll("<", "&lt;")
const tile = (item, i, width) => `
  <figure style="width:${width}px">
    <div class="pic"><img src="${pathToFileURL(item.file).href}" width="${width}" height="${Math.round((width * 9) / 16)}"><span class="time">5:00</span></div>
    <figcaption style="font-size:${width > 200 ? 16 : 13}px">${escape(titles[i % Math.max(1, titles.length)] ?? "")}</figcaption>
    <small>${escape(data.product)}</small>
  </figure>`
const band = (bg, fg, width) =>
  `<section style="background:${bg};color:${fg}">${files.map((item, i) => tile(item, i, width)).join("")}</section>`
const sheet = `<!doctype html><meta charset="utf-8"><style>
  body{margin:0;font-family:system-ui,sans-serif}
  section{display:flex;flex-wrap:wrap;gap:24px;padding:24px}
  figure{margin:0;display:grid;gap:6px}
  .pic{position:relative}
  img{display:block;border-radius:10px;object-fit:cover}
  .time{position:absolute;right:6px;bottom:6px;padding:1px 5px;border-radius:4px;background:rgba(0,0,0,.8);color:#fff;font-size:12px;font-weight:600}
  figcaption{font-weight:600;line-height:1.3;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
  small{opacity:.6;font-size:12px}
</style>${band("#ffffff", "#0f0f0f", 360)}${band("#0f0f0f", "#f1f1f1", 360)}${band("#ffffff", "#0f0f0f", 168)}${band("#0f0f0f", "#f1f1f1", 168)}`
await page.setViewportSize({ width: Math.max(800, files.length * 384 + 48), height: 600 })
await page.setContent(sheet)
await page.evaluate(() => Promise.all([...document.images].map((img) => img.decode().catch(() => null))))
fs.mkdirSync(path.dirname(PREVIEW), { recursive: true })
await page.screenshot({ path: PREVIEW, fullPage: true })
await browser.close()

for (const { name } of files) console.log(`thumbnail/out/${name}.jpg`)
console.log(`${path.relative(ROOT, PREVIEW).split(path.sep).join("/")}: as the feed shows them, light and dark, 360 and 168 px`)
console.log("\ntitles:")
for (const title of titles) console.log(`  ${String([...title].length).padStart(3)}  ${title}`)
for (const message of warnings) console.log(`warn  ${message}`)
for (const message of errors) console.log(`error ${message}`)
console.log(`${errors.length} errors, ${warnings.length} warnings`)
if (errors.length > 0) process.exit(1)
