import { chromium, firefox, webkit } from 'playwright'

const baseUrl = process.env.ATP_WEB_SMOKE_URL || 'http://127.0.0.1:5173/login'
const engines = { chromium, firefox, webkit }
const results = []

for (const [browserName, engine] of Object.entries(engines)) {
  const browser = await engine.launch({ headless: true })
  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 720 } })
    const response = await page.goto(baseUrl, { waitUntil: 'domcontentloaded' })
    await page.waitForSelector('input', { state: 'attached', timeout: 10000 })
    results.push({
      browser: browserName,
      status: response?.status() ?? null,
      title: await page.title(),
      loginInputs: await page.locator('input').count(),
    })
  } finally {
    await browser.close()
  }
}

console.log(JSON.stringify({ url: baseUrl, results }, null, 2))
