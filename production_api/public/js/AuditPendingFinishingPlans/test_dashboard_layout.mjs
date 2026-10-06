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
