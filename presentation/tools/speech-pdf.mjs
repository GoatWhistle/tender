import fs from "node:fs"
import path from "node:path"
import { pathToFileURL } from "node:url"
import { ROOT, SRC } from "./assemble.mjs"
import { launch } from "./browser.mjs"

const SPEECH = path.join(ROOT, "SPEECH.md")
const DIST = path.join(ROOT, "dist")
const PDF = path.join(DIST, "speech.pdf")
const MD = path.join(DIST, "speech.md")
const PAGE = path.join(DIST, "speech.html")
const NEXT = '<span class="next"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14M12 5l7 7-7 7"/></svg></span>'
const KEY = /`?\[\u2192\]`?/g

if (!fs.existsSync(SPEECH)) {
  console.error("SPEECH.md not found, run npm run speech:init")
  process.exit(1)
}

const escape = (text) => text.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
const inline = (text) =>
  escape(text)
    .replace(KEY, NEXT)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
    .replace(/(^|[\s(])[*_]([^*_]+)[*_](?=[\s.,;:!?)]|$)/g, "$1<i>$2</i>")

const cells = (line) =>
  line
    .trim()
    .replace(/^\||\|$/g, "")
    .split("|")
    .map((cell) => cell.trim())

const render = (markdown) => {
  const lines = markdown.replace(/\r/g, "").split("\n")
  const out = []
  let paragraph = []
  let list = null
  const flush = () => {
    if (paragraph.length) out.push(`<p>${inline(paragraph.join(" "))}</p>`)
    paragraph = []
    if (list) out.push(`<${list.tag}>${list.items.map((item) => `<li>${inline(item)}</li>`).join("")}</${list.tag}>`)
    list = null
  }
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i]
    const heading = /^(#{1,3})\s+(.*)$/.exec(line)
    if (heading) {
      flush()
      const level = heading[1].length
      const text = heading[2].replace(/\s*\[[a-z0-9-]+\]/, "")
      const timing = level === 2 ? /\s(\d+:\d{2})\s\((\d+:\d{2})\)\s*$/.exec(text) : null
      const title = timing ? text.slice(0, timing.index) : text
      if (timing && out.some((line) => line.startsWith("<section>"))) out.push("</section>")
      if (timing) out.push("<section>")
      out.push(timing ? `<h2><span>${inline(title)}</span><small>${timing[1]}<em>${timing[2]}</em></small></h2>` : `<h${level}>${inline(title)}</h${level}>`)
    } else if (/^\s*\|/.test(line) && /^\s*\|[\s:|-]+\|\s*$/.test(lines[i + 1] ?? "")) {
      flush()
      const head = cells(line)
      const align = cells(lines[i + 1]).map((cell) => (cell.endsWith(":") ? "right" : "left"))
      const rows = []
      i += 2
      while (i < lines.length && /^\s*\|/.test(lines[i])) rows.push(cells(lines[i++]))
      i -= 1
      const th = head.map((cell, k) => `<th style="text-align:${align[k]}">${inline(cell.replace(/\s*\[[a-z0-9-]+\]/, ""))}</th>`).join("")
      const tr = rows.map((row) => `<tr>${row.map((cell, k) => `<td style="text-align:${align[k]}">${inline(cell.replace(/\s*\[[a-z0-9-]+\]/, ""))}</td>`).join("")}</tr>`).join("")
      out.push(`<table><thead><tr>${th}</tr></thead><tbody>${tr}</tbody></table>`)
    } else if (/^\s*([-*]|\d+\.)\s+/.test(line)) {
      if (paragraph.length) {
        out.push(`<p>${inline(paragraph.join(" "))}</p>`)
        paragraph = []
      }
      const tag = /^\s*\d+\./.test(line) ? "ol" : "ul"
      if (!list || list.tag !== tag) {
        if (list) flush()
        list = { tag, items: [] }
      }
      list.items.push(line.replace(/^\s*([-*]|\d+\.)\s+/, ""))
    } else if (/^>\s?/.test(line)) {
      flush()
      out.push(`<blockquote>${inline(line.replace(/^>\s?/, ""))}</blockquote>`)
    } else if (/^---+\s*$/.test(line)) {
      flush()
      out.push("<hr>")
    } else if (line.trim() === "") {
      flush()
    } else {
      paragraph.push(line.trim())
    }
  }
  flush()
  if (out.some((line) => line.startsWith("<section>"))) out.push("</section>")
  return out.join("\n")
}

const spoken = (markdown) => {
  const lines = markdown.replace(/\r/g, "").split("\n")
  const first = lines.findIndex((line) => /^## \d{2}\./.test(line))
  const end = lines.findIndex((line, index) => index > first && first >= 0 && /^## /.test(line) && !/^## \d{2}\./.test(line))
  return (end < 0 ? lines : lines.slice(0, end)).join("\n")
}

const shell = fs.readFileSync(path.join(SRC, "shell.html"), "utf8")
const lang = /<html\b[^>]*\blang="([^"]+)"/.exec(shell)?.[1] ?? "ru"
const theme = /<html\b[^>]*\bdata-theme="([^"]+)"/.exec(shell)?.[1] ?? "light"
const css = ["tokens.css", "fonts.css"]
  .map((name) => path.join(SRC, "core", "css", name))
  .filter((file) => fs.existsSync(file))
  .map((file) => `<link rel="stylesheet" href="${pathToFileURL(file).href}">`)
  .join("")

const html = `<!doctype html><html lang="${lang}" data-theme="${theme}"><head><meta charset="utf-8"><title>Speech</title>${css}<style>
  @page { size: A4; margin: 18mm 18mm 20mm; }
  body { margin: 0; color: var(--text-primary); font-family: var(--font-sans); font-size: 12.5pt; line-height: 1.55; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  h1 { margin: 0 0 6pt; font-size: 24pt; line-height: 1.15; letter-spacing: -0.02em; }
  h1 + p { margin-top: 0; color: var(--text-secondary); }
  h2 { display: flex; justify-content: space-between; align-items: baseline; gap: 12pt; margin: 22pt 0 8pt; padding-top: 10pt; border-top: 1px solid var(--border-subtle); font-size: 15pt; break-after: avoid; }
  h2 small { font-family: var(--font-mono); font-size: 10.5pt; font-weight: 600; color: var(--action-primary); white-space: nowrap; }
  h2 small em { margin-left: 8pt; font-style: normal; color: var(--text-muted); }
  h3 { margin: 14pt 0 6pt; font-size: 13pt; }
  p, li, blockquote { orphans: 3; widows: 3; }
  p { margin: 0 0 8pt; }
  b { font-weight: 650; }
  code { font-family: var(--font-mono); font-size: 0.9em; }
  hr { display: none; }
  section { break-inside: avoid; }
  table { width: 100%; margin: 10pt 0 6pt; border-collapse: collapse; font-size: 10.5pt; }
  th { padding: 5pt 6pt; border-bottom: 1.5px solid var(--border-strong); color: var(--text-muted); font-weight: 600; }
  td { padding: 4pt 6pt; border-bottom: 1px solid var(--border-subtle); font-variant-numeric: tabular-nums; }
  blockquote { margin: 0 0 8pt; padding: 4pt 12pt; border-left: 3px solid var(--action-primary); color: var(--text-secondary); }
  .next { display: inline-grid; place-items: center; width: 18pt; height: 18pt; margin: 0 2pt; border-radius: 50%; background: var(--action-primary); color: var(--action-primary-text); vertical-align: -4pt; }
  .next svg { width: 11pt; height: 11pt; fill: none; stroke: currentColor; stroke-width: 2.6; stroke-linecap: round; stroke-linejoin: round; }
  p:has(> .next:only-child) { margin: -2pt 0 10pt; }
</style></head><body>${render(spoken(fs.readFileSync(SPEECH, "utf8")))}</body></html>`

fs.mkdirSync(DIST, { recursive: true })
fs.writeFileSync(PAGE, html)
fs.copyFileSync(SPEECH, MD)
const browser = await launch()
const page = await browser.newPage()
await page.goto(pathToFileURL(PAGE).href)
await page.evaluate(() => document.fonts.ready)
await page.pdf({
  path: PDF,
  format: "A4",
  printBackground: true,
  displayHeaderFooter: true,
  headerTemplate: "<span></span>",
  footerTemplate: '<div style="width:100%;font-size:8pt;color:#888;text-align:right;padding:0 18mm"><span class="pageNumber"></span></div>',
  margin: { top: "18mm", bottom: "20mm", left: "18mm", right: "18mm" },
})
await browser.close()
fs.rmSync(PAGE)
console.log("dist/speech.pdf and dist/speech.md written from SPEECH.md")
