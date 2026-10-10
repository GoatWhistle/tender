import fs from "node:fs"
import path from "node:path"
import { LIBRARY, SLIDES } from "./assemble.mjs"

const [, , wanted, target] = process.argv
const usage = "usage: npm run slide:add -- <layout id or number> <NN-new-id>, for example: npm run slide:add -- hub 05-agents"

if (!wanted || !target || !/^\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*$/.test(target)) {
  console.error(usage)
  process.exit(2)
}

const layouts = fs.readdirSync(LIBRARY).filter((name) => /^\d{2}-/.test(name))
const source = layouts.find((name) => name.slice(3) === wanted || name.slice(0, 2) === wanted.padStart(2, "0") || name === wanted)
if (!source) {
  console.error(`layout "${wanted}" not found; layouts: ${layouts.map((name) => name.slice(3)).join(", ")}`)
  process.exit(1)
}

const dest = path.join(SLIDES, target)
if (fs.existsSync(dest)) {
  console.error(`src/slides/${target} exists, pick another number or id`)
  process.exit(1)
}

const from = source.slice(3)
const to = target.slice(3)
const taken = fs.readdirSync(SLIDES).filter((name) => name.slice(3) === to)
if (taken.length) {
  console.error(`slide id "${to}" is already used by src/slides/${taken[0]}`)
  process.exit(1)
}

const rename = (text) =>
  text
    .replace(new RegExp(`id="${from}"`, "g"), `id="${to}"`)
    .replace(new RegExp(`#${from}(?![\\w-])`, "g"), `#${to}`)
    .replace(new RegExp(`(deckScene|deckNotes)\\("${from}"`, "g"), `$1("${to}"`)

fs.mkdirSync(dest, { recursive: true })
for (const file of fs.readdirSync(path.join(LIBRARY, source))) {
  const text = fs.readFileSync(path.join(LIBRARY, source, file), "utf8")
  fs.writeFileSync(path.join(dest, file), rename(text))
}
console.log(`src/slides/${target} from library/${source}`)
console.log("next: fill the placeholders, npm run speech:init, npm run build, npm run shots")
