#!/usr/bin/env node
import fs from "node:fs"
import path from "node:path"

const ROOT = process.cwd()
const SKIP = new Set(["node_modules", ".git", "dist", "build", ".venv", "venv", "target", "presentation", ".claude", ".agents", "context"])
const NOISE = new Set(["css", "html", "js", "javascript", "ai", "app", "project", "code", "web", "website", "software", "tool", "tools", "github", "repo", "misc", "test", "demo"])
const BANNED = [
  "ai-powered", "ai powered", "innovative", "cutting-edge", "cutting edge", "seamless", "revolutionary", "leverage", "leverages",
  "robust", "state-of-the-art", "next-generation", "next generation", "powerful", "comprehensive", "designed to", "aims to",
  "helps you", "a tool that", "a platform that", "solution", "empower", "unlock", "harness the", "game-changing", "world-class",
  "this repository", "this project", "hackathon project", "built with", "made with",
]
const DASHES = /[\u2014\u2013\u00b7\u2192\u2190\u21d2\u2794\u27a1]|\s-\s/u
const EMOJI = /\p{Extended_Pictographic}/u
const TOPIC = /^[a-z0-9][a-z0-9-]{0,49}$/

const DEPENDENCIES = {
  react: "react", "react-dom": "react", next: "nextjs", vue: "vue", svelte: "svelte", "@angular/core": "angular", vite: "vite",
  typescript: "typescript", express: "express", fastify: "fastify", "@nestjs/core": "nestjs", "socket.io": "websockets",
  "@tanstack/react-query": "tanstack-query", "three": "threejs", "d3": "d3", "react-native": "react-native", electron: "electron",
  fastapi: "fastapi", django: "django", flask: "flask", pydantic: "pydantic", sqlalchemy: "sqlalchemy", alembic: "alembic",
  celery: "celery", torch: "pytorch", tensorflow: "tensorflow", "scikit-learn": "scikit-learn", catboost: "catboost",
  xgboost: "xgboost", lightgbm: "lightgbm", transformers: "transformers", "sentence-transformers": "embeddings",
  langchain: "langchain", "langgraph": "langgraph", openai: "openai", anthropic: "anthropic", ollama: "ollama", vllm: "vllm",
  polars: "polars", pandas: "pandas", numpy: "numpy", scipy: "scipy", "opencv-python": "opencv", networkx: "networkx",
  "rank-bm25": "bm25", faiss: "faiss", "faiss-cpu": "faiss", qdrant: "qdrant", "qdrant-client": "qdrant", chromadb: "chromadb",
  "clickhouse-connect": "clickhouse", psycopg: "postgresql", "psycopg2": "postgresql", "psycopg2-binary": "postgresql",
  asyncpg: "postgresql", redis: "redis", aiogram: "telegram-bot", "python-telegram-bot": "telegram-bot", rclpy: "ros2",
  axum: "axum", tokio: "tokio", actix: "actix", "actix-web": "actix", hyper: "hyper", serde: "serde", gin: "gin", fiber: "fiber",
}
const IMAGES = { postgres: "postgresql", redis: "redis", clickhouse: "clickhouse", rabbitmq: "rabbitmq", kafka: "kafka", nginx: "nginx", qdrant: "qdrant", minio: "minio", ollama: "ollama", elasticsearch: "elasticsearch", mongo: "mongodb" }
const HEADLINE = new Set([
  "typescript", "python", "rust", "go", "ruby", "fsharp", "kotlin", "java", "csharp", "swift", "cpp", "c",
  "react", "vue", "svelte", "angular", "nextjs", "react-native", "electron",
  "fastapi", "django", "flask", "express", "fastify", "nestjs", "axum", "actix", "gin", "fiber",
  "postgresql", "clickhouse", "redis", "mongodb", "qdrant", "elasticsearch", "kafka", "rabbitmq", "chromadb", "faiss",
  "pytorch", "tensorflow", "catboost", "xgboost", "lightgbm", "transformers", "langchain", "langgraph", "ollama", "vllm", "ros2",
  "docker",
])
const EXTENSIONS = { ".ts": "typescript", ".tsx": "typescript", ".py": "python", ".rs": "rust", ".go": "go", ".rb": "ruby", ".fs": "fsharp", ".kt": "kotlin", ".java": "java", ".cs": "csharp", ".swift": "swift", ".cpp": "cpp", ".c": "c" }

const walk = (dir, found = []) => {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (SKIP.has(entry.name) || entry.name.startsWith(".")) continue
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) walk(full, found)
    else found.push(full)
  }
  return found
}

const scan = () => {
  const files = walk(ROOT)
  const stack = new Map()
  const add = (topic, where) => {
    if (!stack.has(topic)) stack.set(topic, new Set())
    stack.get(topic).add(path.relative(ROOT, where).split(path.sep).join("/"))
  }
  const counts = {}
  for (const file of files) {
    const lang = EXTENSIONS[path.extname(file)]
    if (lang) counts[lang] = (counts[lang] ?? 0) + 1
    const name = path.basename(file)
    const text = () => fs.readFileSync(file, "utf8")
    if (name === "package.json") {
      const pkg = JSON.parse(text())
      for (const dep of Object.keys({ ...pkg.dependencies, ...pkg.devDependencies })) if (DEPENDENCIES[dep]) add(DEPENDENCIES[dep], file)
    }
    if (/^(pyproject\.toml|requirements[\w.-]*\.txt|Cargo\.toml|go\.mod|Gemfile)$/.test(name)) {
      const body = text().toLowerCase()
      for (const [dep, topic] of Object.entries(DEPENDENCIES)) if (new RegExp(`(^|[\\s"'\\[,=/])${dep.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}([\\s"'\\]<>=~,;@/]|$)`, "m").test(body)) add(topic, file)
    }
    if (/^(docker-compose|compose)[\w.-]*\.ya?ml$/.test(name) || name === "Dockerfile") {
      add("docker", file)
      const body = text().toLowerCase()
      for (const [image, topic] of Object.entries(IMAGES)) if (new RegExp(`image:\\s*["']?${image}|FROM\\s+${image}`, "i").test(body)) add(topic, file)
    }
  }
  const total = Object.values(counts).reduce((sum, n) => sum + n, 0) || 1
  for (const [lang, n] of Object.entries(counts)) if (n / total >= 0.05) add(lang, path.join(ROOT, `*${Object.keys(EXTENSIONS).find((ext) => EXTENSIONS[ext] === lang)}`))
  return stack
}

const check = (file) => {
  const meta = JSON.parse(fs.readFileSync(path.resolve(file), "utf8"))
  const errors = []
  const warnings = []
  const description = String(meta.description ?? "").trim()
  const topics = (meta.topics ?? []).map(String)
  const length = [...description].length
  if (!description) errors.push("description is empty")
  if (length > 350) errors.push(`description is ${length} characters, GitHub allows 350`)
  else if (length > 300) warnings.push(`description is ${length} characters, lists cut it; aim for 140 to 300`)
  if (length && length < 80) warnings.push(`description is ${length} characters: say the rule and what it is`)
  if (DASHES.test(description)) errors.push("description has an em dash, en dash, spaced hyphen, middle dot or arrow; use a period, a colon or a comma")
  if (EMOJI.test(description)) errors.push("description has an emoji")
  if (/[\u0400-\u04ff]/.test(description) && meta.language !== "ru") errors.push("description is not in English")
  if (/\.$/.test(description)) warnings.push("no trailing period at the end of the description")
  if (/#\d+/.test(description)) errors.push("issue reference in the description")
  if (meta.name && description.toLowerCase().startsWith(String(meta.name).toLowerCase())) warnings.push("description starts with the repository name, which GitHub already shows")
  for (const phrase of BANNED) if (description.toLowerCase().includes(phrase)) errors.push(`description uses "${phrase}"`)
  if (topics.length > 20) errors.push(`${topics.length} topics, GitHub allows 20`)
  if (topics.length < 8) warnings.push(`${topics.length} topics, use 10 to 20 so the project is findable`)
  const seen = new Set()
  for (const topic of topics) {
    if (!TOPIC.test(topic)) errors.push(`topic "${topic}" is not lowercase letters, digits and hyphens, at most 50`)
    if (seen.has(topic)) errors.push(`topic "${topic}" twice`)
    seen.add(topic)
    if (NOISE.has(topic)) errors.push(`topic "${topic}" is noise nobody searches for`)
  }
  if (topics.includes("javascript") && topics.includes("typescript")) warnings.push("javascript next to typescript: keep the real one")
  const stack = scan()
  for (const topic of topics) if (HEADLINE.has(topic) && !stack.has(topic)) warnings.push(`topic "${topic}" names a technology not found in the code`)
  const missing = [...stack.keys()].filter((topic) => HEADLINE.has(topic) && !topics.includes(topic))
  if (missing.length) warnings.push(`found in the code but not in topics: ${missing.join(", ")}`)
  if (meta.homepage && !/^https:\/\//.test(meta.homepage)) warnings.push("homepage should start with https://")
  const quote = (text) => `'${String(text).replaceAll("'", "'\\''")}'`
  const repo = meta.repo ? ` ${meta.repo}` : ""
  console.log(`description, ${length} characters:\n  ${description}\n`)
  console.log(`topics, ${topics.length}:\n  ${topics.join(", ")}\n`)
  for (const message of warnings) console.log(`warn  ${message}`)
  for (const message of errors) console.log(`error ${message}`)
  console.log(`${errors.length} errors, ${warnings.length} warnings\n`)
  console.log("apply (needs gh and write access):")
  console.log(`  gh repo edit${repo} --description ${quote(description)}${meta.homepage ? ` --homepage ${quote(meta.homepage)}` : ""}`)
  if (topics.length) console.log(`  gh repo edit${repo} ${topics.map((topic) => `--add-topic ${topic}`).join(" ")}`)
  if (errors.length) process.exit(1)
}

const [, , command, file] = process.argv
if (command === "scan") {
  const stack = scan()
  for (const [topic, where] of [...stack.entries()].sort()) console.log(`${HEADLINE.has(topic) ? "stack " : "lib   "} ${topic.padEnd(18)} ${[...where].slice(0, 3).join(", ")}`)
} else if (command === "check" && file) check(file)
else {
  console.error("usage: node .claude/skills/repo-meta/meta.mjs scan | check <repo.json>")
  process.exit(2)
}
