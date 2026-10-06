import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import fs from 'node:fs'
import net from 'node:net'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const htmlPath = process.env.AUDIT_MOCKUP_PATH
  ? path.resolve(process.env.AUDIT_MOCKUP_PATH)
  : fileURLToPath(new URL('./audit_pending_finishing_plans_master_detail.html', import.meta.url))
const profilePath = fs.mkdtempSync(path.join(os.tmpdir(), 'audit-finishing-plan-test-'))

const portServer = net.createServer()
await new Promise((resolve) => portServer.listen(0, '127.0.0.1', resolve))
const port = portServer.address().port
await new Promise((resolve, reject) => portServer.close((error) => error ? reject(error) : resolve()))

const chrome = spawn('/usr/bin/google-chrome', [
  '--headless=new',
  '--no-sandbox',
  '--disable-gpu',
  `--remote-debugging-port=${port}`,
  '--remote-allow-origins=*',
  `--user-data-dir=${profilePath}`,
  pathToFileURL(htmlPath).href,
], { stdio: 'ignore' })

async function waitForPage() {
  for (let attempt = 0; attempt < 80; attempt += 1) {
    try {
      const pages = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json()
      const page = pages.find((entry) => entry.type === 'page')
      if (page) return page
    } catch {}
    await new Promise((resolve) => setTimeout(resolve, 100))
  }
  throw new Error('Chrome page did not become available')
}

const page = await waitForPage()
const socket = new WebSocket(page.webSocketDebuggerUrl)
await new Promise((resolve, reject) => {
  socket.addEventListener('open', resolve, { once: true })
  socket.addEventListener('error', reject, { once: true })
})

let requestId = 0
const pendingRequests = new Map()
socket.addEventListener('message', (event) => {
  const message = JSON.parse(event.data)
  const resolve = pendingRequests.get(message.id)
  if (!resolve) return
  pendingRequests.delete(message.id)
  resolve(message)
})

function call(method, params = {}) {
  return new Promise((resolve) => {
    const id = ++requestId
    pendingRequests.set(id, resolve)
    socket.send(JSON.stringify({ id, method, params }))
  })
}

async function evaluate(expression) {
  const response = await call('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })
  if (response.result?.exceptionDetails) throw new Error(response.result.exceptionDetails.text)
  return response.result.result.value
}

try {
  await evaluate('new Promise((resolve) => document.readyState === "complete" ? resolve() : addEventListener("load", resolve, { once: true }))')

  const matrixState = await evaluate(`(() => {
    const top = document.getElementById('content-148-top')
    switchTab('148', 'bottom')
    const bottom = document.getElementById('content-148-bottom')
    const firstMatrixHeader = top.querySelector('table.pending-matrix thead tr')
    return {
      topTables: top.querySelectorAll('table.pending-matrix').length,
      topHeaders: firstMatrixHeader ? [...firstMatrixHeader.children].map((cell) => cell.textContent.trim()) : [],
      topFooters: top.querySelectorAll('table.pending-matrix tfoot').length,
      bottomTables: bottom.querySelectorAll('table.pending-matrix').length,
      bottomHasRejectedTotal: bottom.textContent.includes('Rejected Pieces') && bottom.textContent.includes('7 pcs'),
      chips: document.querySelectorAll('.qty-chip').length,
    }
  })()`)

  assert.equal(matrixState.topTables, 2, 'Top must show one Loose Piece matrix and one Rejected Pieces matrix')
  assert.deepEqual(matrixState.topHeaders, ['Colour', '45 CM', '50 CM', '55 CM', '60 CM', '65 CM', '70 CM', '75 CM', '80 CM', 'Total'])
  assert.equal(matrixState.topFooters, 2, 'Every Top matrix must include a Total footer')
  assert.equal(matrixState.bottomTables, 1, 'Bottom must show its non-zero Rejected Pieces matrix only')
  assert.equal(matrixState.bottomHasRejectedTotal, true)
  assert.equal(matrixState.chips, 0, 'The pending breakdown must not use quantity chips')

  const filterState = await evaluate(`(() => {
    const visibleIds = () => [...document.querySelectorAll('.data-row:not(.filtered-out)')].map((row) => row.id)
    const setValue = (id, value) => {
      const input = document.getElementById(id)
      input.value = value
      input.dispatchEvent(new Event('input', { bubbles: true }))
    }
    const reset = () => document.getElementById('reset-filters').click()

    setValue('plan-filter', 'FP-2026-0156')
    const byPlan = visibleIds()
    reset()
    setValue('lot-filter', 'LOT-2610')
    const byLot = visibleIds()
    reset()
    setValue('item-filter', 'tank')
    const byItem = visibleIds()
    reset()

    return {
      byPlan,
      byLot,
      byItem,
      afterReset: visibleIds(),
      values: ['plan-filter', 'lot-filter', 'item-filter'].map((id) => document.getElementById(id).value),
    }
  })()`)

  assert.deepEqual(filterState.byPlan, ['row-156'])
  assert.deepEqual(filterState.byLot, ['row-161', 'row-168'])
  assert.deepEqual(filterState.byItem, ['row-156'])
  assert.deepEqual(filterState.afterReset, ['row-148', 'row-156', 'row-161', 'row-168'])
  assert.deepEqual(filterState.values, ['', '', ''])

  console.log('PASS: matrix presentation and separate Plan/Lot/Item filters')
} finally {
  socket.close()
  chrome.kill('SIGTERM')
  fs.rmSync(profilePath, { recursive: true, force: true })
}
