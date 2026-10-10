import fs from "node:fs"
import path from "node:path"
import { ROOT } from "./assemble.mjs"
import { launch } from "./browser.mjs"
import {
  captions,
  checkScript,
  clock,
  DEFAULTS,
  labels,
  location,
  parseScript,
  retime,
  scriptLanguages,
  scriptPath,
  seconds,
  settings,
  TEMPLATE,
  VIDEO,
  vocabulary,
  voiceOver,
} from "./video-script.mjs"

const [, , command = "check", ...args] = process.argv
const option = (name) => {
  const index = args.indexOf(`--${name}`)
  return index === -1 ? null : (args[index + 1] ?? null)
}
const flag = (name) => args.includes(`--${name}`)
const rel = (file) => path.relative(ROOT, file).split(path.sep).join("/")

const languages = () => {
  const asked = option("lang")
  const found = asked ? [asked] : scriptLanguages()
  if (found.length === 0) {
    console.error("video: no video/script.<lang>.md, run npm run video:init -- --lang ru")
    process.exit(1)
  }
  for (const lang of found) {
    if (!fs.existsSync(scriptPath(lang))) {
      console.error(`video: ${rel(scriptPath(lang))} not found, run npm run video:init -- --lang ${lang}`)
      process.exit(1)
    }
  }
  return found
}

const init = () => {
  const lang = option("lang") ?? "ru"
  const target = seconds(option("target") ?? "5:00")
  const limit = seconds(option("limit"))
  const file = scriptPath(lang)
  if (fs.existsSync(file) && !flag("force")) {
    console.error(`video: ${rel(file)} exists, pass --force to overwrite`)
    process.exit(1)
  }
  const template = fs.readFileSync(TEMPLATE, "utf8").replace(/\r/g, "")
  const heads = [...template.matchAll(/^## (\d+)\. (.+) \[(\d+)\]$/gm)]
  const weight = heads.reduce((sum, m) => sum + Number(m[3]), 0)
  const lengths = heads.map((m) => Math.max(3, Math.round((Number(m[3]) * target) / weight)))
  lengths[lengths.length - 1] += target - lengths.reduce((sum, value) => sum + value, 0)
  let cursor = 0
  let text = template
  heads.forEach((m, i) => {
    text = text.replace(m[0], `## ${m[1]}. ${m[2]}, ${clock(cursor)}\u2013${clock(cursor + lengths[i])}`)
    cursor += lengths[i]
  })
  text = text
    .replaceAll("{{lang}}", lang)
    .replace("{{target}}", clock(target))
    .replace("{{limit}}", limit === null ? "{{limit from context/PLATFORM.md}}" : clock(limit))
    .replace("{{wpm}}", String((DEFAULTS[lang] ?? DEFAULTS.en).wpm))
  fs.writeFileSync(file, text)
  console.log(`${rel(file)}: ${heads.length} sections, ${clock(target)}`)
}

const check = () => {
  const strict = flag("strict")
  let failed = false
  for (const lang of languages()) {
    const file = scriptPath(lang)
    let script = parseScript(fs.readFileSync(file, "utf8"))
    if (flag("retime")) {
      fs.writeFileSync(file, retime(script))
      script = parseScript(fs.readFileSync(file, "utf8"))
    }
    const vocab = vocabulary(lang)
    const conf = settings(script.meta, lang)
    const result = checkScript(script, conf, vocab, strict)
    console.log(`\n${rel(file)}: ${clock(result.total)}, limit ${conf.limit === null ? "unknown" : clock(conf.limit)}, ${conf.wpm} wpm`)
    for (const row of result.rows) {
      const slot = `${clock(row.s.start)}-${clock(row.s.end)}`.padEnd(10)
      console.log(`  ${row.s.no.padStart(3)}. ${row.s.title.slice(0, 32).padEnd(32)} ${slot} ${String(row.words).padStart(4)} words ${row.need.toFixed(0).padStart(4)}/${String(row.slot).padEnd(3)} s ${row.status}`)
    }
    for (const message of result.warnings) console.log(`  warn  ${message}`)
    for (const message of result.errors) console.log(`  error ${message}`)
    const voice = path.join(VIDEO, `voice-over.${lang}.md`)
    const srt = path.join(VIDEO, `captions.${lang}.srt`)
    fs.writeFileSync(voice, voiceOver(script, conf, vocab))
    fs.writeFileSync(srt, captions(script, conf, vocab))
    console.log(`  wrote ${rel(voice)}, ${rel(srt)}`)
    console.log(`  ${result.errors.length} errors, ${result.warnings.length} warnings`)
    if (result.errors.length > 0) failed = true
  }
  if (failed) process.exit(1)
}

const shots = async () => {
  const browser = await launch()
  let failed = false
  for (const lang of languages()) {
    const script = parseScript(fs.readFileSync(scriptPath(lang), "utf8"))
    const conf = settings(script.meta, lang)
    const site = (option("site") ?? conf.site ?? "").replace(/\/$/, "")
    if (!/^https?:\/\//.test(site)) {
      console.error(`video: set site in ${rel(scriptPath(lang))} or pass --site http://localhost:8080`)
      process.exit(1)
    }
    const out = path.join(ROOT, "shots", "video", lang)
    fs.rmSync(out, { recursive: true, force: true })
    fs.mkdirSync(out, { recursive: true })
    const context = await browser.newContext({ viewport: { width: 1920, height: 1080 }, locale: lang, colorScheme: conf.theme })
    const page = await context.newPage()
    console.log(`\n${site} as ${lang}, ${conf.theme}`)
    for (const s of script.sections) {
      const target = location(s)
      if (target === null || target.includes("{{")) {
        console.log(`  ${s.no.padStart(3)}. skipped, no /path or URL in Screen`)
        continue
      }
      const url = /^https?:/.test(target) ? target : `${site}${target}`
      const response = await page.goto(url, { waitUntil: "networkidle", timeout: 30000 }).catch((error) => ({ error }))
      const status = response?.error ? String(response.error.message).split("\n")[0] : response?.status()
      const missing = []
      for (const label of labels(s)) {
        if ((await page.getByText(label, { exact: false }).count()) === 0) missing.push(label)
      }
      const shot = path.join(out, `${s.no.padStart(2, "0")}.png`)
      if (!response?.error) await page.screenshot({ path: shot })
      const bad = response?.error || status >= 400 || missing.length > 0
      if (bad) failed = true
      console.log(`  ${s.no.padStart(3)}. ${bad ? "FAIL" : "ok  "} ${url} ${status}${missing.length ? `, not on the page: ${missing.map((label) => `\u00ab${label}\u00bb`).join(", ")}` : ""}`)
    }
    await context.close()
    console.log(`  storyboard in ${rel(out)}`)
  }
  await browser.close()
  if (failed) process.exit(1)
}

const commands = { init, check, shots }
if (!commands[command]) {
  console.error(`video: unknown command ${command}, use init, check or shots`)
  process.exit(1)
}
await commands[command]()
