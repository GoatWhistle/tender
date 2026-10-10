import { chromium } from "playwright-core"

export const launch = async () => {
  const executablePath = process.env.CHROME_PATH
  try {
    return await chromium.launch(executablePath ? { executablePath } : {})
  } catch {
    try {
      return await chromium.launch({ channel: process.env.CHROME_CHANNEL || "chrome" })
    } catch (error) {
      console.error("cannot start Chromium: run npx playwright install chromium or set CHROME_PATH")
      console.error(String(error.message).split("\n")[0])
      process.exit(2)
    }
  }
}
