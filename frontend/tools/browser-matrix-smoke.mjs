import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { chromium, firefox, webkit } from 'playwright'

const rawBaseUrl = process.env.ATP_WEB_SMOKE_URL || 'http://127.0.0.1:5173/login'
const artifactDir = process.env.ATP_WEB_SMOKE_ARTIFACT_DIR?.trim() || ''
const reportPath = process.env.ATP_WEB_SMOKE_REPORT?.trim() || ''
const headless = process.env.ATP_WEB_SMOKE_HEADLESS !== 'false'
const requestedBrowsers = (process.env.ATP_WEB_SMOKE_BROWSERS || 'chromium,firefox,webkit')
  .split(',')
  .map((value) => value.trim().toLowerCase())
  .filter(Boolean)
const engines = { chromium, firefox, webkit }

function safeUrl(raw) {
  try {
    const value = new URL(raw)
    if (!['http:', 'https:'].includes(value.protocol) || value.username || value.password) {
      throw new Error('only credential-free HTTP(S) URLs are supported')
    }
    value.search = ''
    value.hash = ''
    return value.toString()
  } catch (error) {
    throw new Error(`invalid ATP_WEB_SMOKE_URL: ${error.message}`)
  }
}

function parseViewport(raw) {
  const match = /^(\d+)x(\d+)$/.exec(raw || '1280x720')
  if (!match) throw new Error('ATP_WEB_SMOKE_VIEWPORT must use WIDTHxHEIGHT')
  const width = Number(match[1])
  const height = Number(match[2])
  if (width < 320 || height < 240) throw new Error('ATP_WEB_SMOKE_VIEWPORT is too small')
  return { width, height }
}

function safeUrlForEvidence(raw) {
  try {
    return safeUrl(raw)
  } catch {
    return '<redacted-url>'
  }
}

function shortText(value, maxLength = 400) {
  return String(value || '').replace(/[\r\n]+/g, ' ').trim().slice(0, maxLength)
}

function errorText(error) {
  return shortText(error instanceof Error ? error.message : error)
}

async function runBrowser(browserName, engine, baseUrl, viewport) {
  const browser = await engine.launch({ headless })
  let context
  let tracingStarted = false
  const consoleMessages = []
  const failedRequests = []
  const errorResponses = []
  const result = { browser: browserName, status: null, title: '', loginInputs: 0 }
  const traceFile = artifactDir ? `${browserName}.trace.zip` : ''
  const harFile = artifactDir ? `${browserName}.har` : ''

  try {
    const contextOptions = { viewport }
    if (artifactDir) {
      contextOptions.recordHar = {
        path: path.join(artifactDir, harFile),
        content: 'omit',
        mode: 'minimal',
      }
    }
    context = await browser.newContext(contextOptions)
    if (artifactDir) {
      await context.tracing.start({ screenshots: true, snapshots: true, sources: false })
      tracingStarted = true
    }
    const page = await context.newPage()
    page.on('console', (message) => {
      consoleMessages.push({ type: message.type(), text: shortText(message.text()) })
    })
    page.on('requestfailed', (request) => {
      failedRequests.push({ method: request.method(), url: safeUrlForEvidence(request.url()), error: shortText(request.failure()?.errorText) })
    })
    page.on('response', (response) => {
      if (response.status() >= 400) {
        errorResponses.push({ method: response.request().method(), url: safeUrlForEvidence(response.url()), status: response.status() })
      }
    })

    const response = await page.goto(baseUrl, { waitUntil: 'domcontentloaded' })
    await page.waitForSelector('input', { state: 'attached', timeout: 10000 })
    result.status = response?.status() ?? null
    result.title = shortText(await page.title(), 200)
    result.loginInputs = await page.locator('input').count()
    result.console = consoleMessages.slice(0, 100)
    result.failedRequests = failedRequests.slice(0, 100)
    result.errorResponses = errorResponses.slice(0, 100)
    if (artifactDir) {
      result.trace = traceFile
      result.har = harFile
    }
  } catch (error) {
    result.error = errorText(error)
    result.console = consoleMessages.slice(0, 100)
    result.failedRequests = failedRequests.slice(0, 100)
    result.errorResponses = errorResponses.slice(0, 100)
  } finally {
    if (context && tracingStarted) {
      try {
        await context.tracing.stop({ path: path.join(artifactDir, traceFile) })
      } catch (error) {
        result.traceError = errorText(error)
      }
    }
    if (context) {
      await context.close().catch((error) => {
        result.contextCloseError = errorText(error)
      })
    }
    await browser.close()
  }
  return result
}

async function main() {
  const baseUrl = safeUrl(rawBaseUrl)
  const viewport = parseViewport(process.env.ATP_WEB_SMOKE_VIEWPORT)
  const unknown = requestedBrowsers.filter((name) => !engines[name])
  if (!requestedBrowsers.length || unknown.length) {
    throw new Error(`unsupported browser selection: ${unknown.join(', ') || 'empty'}`)
  }
  if (artifactDir) await mkdir(artifactDir, { recursive: true })

  const results = []
  for (const browserName of requestedBrowsers) {
    results.push(await runBrowser(browserName, engines[browserName], baseUrl, viewport))
  }
  const report = {
    ok: results.every((item) => item.status !== null && item.status < 400 && !item.error),
    url: baseUrl,
    headless,
    viewport,
    browsers: requestedBrowsers,
    results,
  }
  const output = JSON.stringify(report, null, 2)
  if (reportPath) {
    await mkdir(path.dirname(reportPath), { recursive: true })
    await writeFile(reportPath, `${output}\n`, 'utf8')
  }
  console.log(output)
  if (!report.ok) process.exitCode = 1
}

main().catch((error) => {
  console.error(errorText(error))
  process.exitCode = 1
})
