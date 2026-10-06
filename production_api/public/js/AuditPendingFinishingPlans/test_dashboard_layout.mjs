import test from 'node:test'
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { createRequire } from 'node:module'
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const require = createRequire(import.meta.url)
const { parse: parseSfc } = require('../../../../../frappe/node_modules/@vue/compiler-sfc')
const { baseParse } = require('../../../../../frappe/node_modules/@vue/compiler-dom')
const chrome = '/usr/bin/google-chrome'
const componentPath = new URL('./AuditPendingFinishingPlans.vue', import.meta.url)
const componentSource = readFileSync(componentPath, 'utf8')
const parsedComponent = parseSfc(componentSource, { filename: 'AuditPendingFinishingPlans.vue' })
assert.equal(parsedComponent.errors.length, 0)
const templateAst = baseParse(parsedComponent.descriptor.template.content)


function collectTemplateDetails(node, details = { classes: [], text: [] }) {
    if (node.type === 1) {
        const classAttribute = node.props.find(prop => prop.type === 6 && prop.name === 'class')
        if (classAttribute?.value?.content) details.classes.push(...classAttribute.value.content.split(/\s+/))
    }
    if (node.type === 2 && node.content.trim()) details.text.push(node.content.trim())
    for (const child of node.children || []) collectTemplateDetails(child, details)
    return details
}

const templateDetails = collectTemplateDetails(templateAst)


test('omits the explanatory subtitle below the page title', () => {
    assert.ok(!templateDetails.text.some(text => text.includes('Plans sitting in Dispatched or Fully Dispatched for over')))
})


test('omits the duplicate KPI strip from the selected-plan panel', () => {
    assert.ok(!templateDetails.classes.includes('detail-kpis'))
})


test('omits the helper sentence below Pending Quantity', () => {
    assert.ok(!templateDetails.text.includes('Current balances; loose quantities are net after lot transfers.'))
})


test('labels plan, lot, and item identity in the master and detail panels', () => {
    assert.ok(templateDetails.text.includes('Finishing Plan / Lot / Item'))
    assert.equal(templateDetails.text.filter(text => text === 'Lot').length, 2)
    assert.equal(templateDetails.text.filter(text => text === 'Item').length, 2)
    assert.ok(templateDetails.classes.includes('plan-identity'))
    assert.ok(templateDetails.classes.includes('detail-identity'))
})


test('allows long item names to wrap instead of truncating them', { skip: !existsSync(chrome) }, () => {
    const css = componentSource.match(/<style scoped>([\s\S]*?)<\/style>/)?.[1]
    assert.ok(css, 'component CSS should be available')

    const workdir = mkdtempSync(join(tmpdir(), 'audit-dashboard-identity-'))
    const htmlPath = join(workdir, 'identity.html')
    try {
        writeFileSync(htmlPath, `<!doctype html>
            <html><head><style>${css}</style></head>
            <body><div style="width: 90px"><span class="identity-value identity-value--item">Extra Long Item Name That Must Remain Visible</span></div><script>
                const item = document.querySelector('.identity-value--item')
                const style = getComputedStyle(item)
                document.body.dataset.whiteSpace = style.whiteSpace
                document.body.dataset.textOverflow = style.textOverflow
                document.body.dataset.overflowWrap = style.overflowWrap
            </script></body></html>`)

        const rendered = execFileSync(chrome, [
            '--headless',
            '--disable-gpu',
            '--no-sandbox',
            '--dump-dom',
            '--window-size=800,600',
            `file://${htmlPath}`,
        ], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] })
        const body = rendered.match(/<body[^>]*data-white-space="([^"]+)"[^>]*data-text-overflow="([^"]+)"[^>]*data-overflow-wrap="([^"]+)"/)
        assert.ok(body, 'browser should report the rendered item-name styles')
        assert.equal(body[1], 'normal')
        assert.equal(body[2], 'clip')
        assert.equal(body[3], 'anywhere')
    } finally {
        rmSync(workdir, { recursive: true, force: true })
    }
})


test('uses the desktop viewport with only a 16px horizontal gutter', { skip: !existsSync(chrome) }, () => {
    const css = componentSource.match(/<style scoped>([\s\S]*?)<\/style>/)?.[1]
    assert.ok(css, 'component CSS should be available')

    const workdir = mkdtempSync(join(tmpdir(), 'audit-dashboard-layout-'))
    const htmlPath = join(workdir, 'layout.html')
    try {
        writeFileSync(htmlPath, `<!doctype html>
            <html><head><style>body { margin: 0; } ${css}</style></head>
            <body><main class="audit-dashboard"><div class="master-detail-layout"><section class="master-panel"></section><aside class="detail-panel"></aside></div></main><script>
                const dashboard = document.querySelector('.audit-dashboard')
                const rect = dashboard.getBoundingClientRect()
                const style = getComputedStyle(dashboard)
                const masterWidth = document.querySelector('.master-panel').getBoundingClientRect().width
                const detailWidth = document.querySelector('.detail-panel').getBoundingClientRect().width
                document.body.dataset.width = String(Math.round(rect.width))
                document.body.dataset.left = String(Math.round(rect.left))
                document.body.dataset.paddingLeft = style.paddingLeft
                document.body.dataset.paddingRight = style.paddingRight
                document.body.dataset.panelRatio = (masterWidth / detailWidth).toFixed(2)
            </script></body></html>`)

        const rendered = execFileSync(chrome, [
            '--headless',
            '--disable-gpu',
            '--no-sandbox',
            '--dump-dom',
            '--window-size=1840,900',
            `file://${htmlPath}`,
        ], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] })
        const body = rendered.match(/<body[^>]*data-width="(\d+)"[^>]*data-left="(\d+)"[^>]*data-padding-left="([^"]+)"[^>]*data-padding-right="([^"]+)"[^>]*data-panel-ratio="([^"]+)"/)
        assert.ok(body, 'browser should report the rendered dashboard geometry')
        assert.ok(Number(body[1]) >= 1800, `dashboard width was ${body[1]}px`)
        assert.ok(Number(body[1]) <= 1840, `dashboard overflowed at ${body[1]}px`)
        assert.ok(Number(body[2]) <= 1, `dashboard started ${body[2]}px from the viewport edge`)
        assert.equal(body[3], '16px')
        assert.equal(body[4], '16px')
        assert.ok(Math.abs(Number(body[5]) - 1.5) <= 0.02, `master/detail ratio was ${body[5]}`)
    } finally {
        rmSync(workdir, { recursive: true, force: true })
    }
})
