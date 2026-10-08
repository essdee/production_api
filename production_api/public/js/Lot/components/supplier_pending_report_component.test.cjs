const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')

const Vue = require('../../../../../../frappe/node_modules/vue')
const { compileTemplate, parse } = require('../../../../../../frappe/node_modules/@vue/compiler-sfc')
const { renderToString } = require('../../../../../../frappe/node_modules/@vue/server-renderer')

const componentPath = path.join(__dirname, 'SupplierPendingReport.vue')
const { descriptor } = parse(fs.readFileSync(componentPath, 'utf8'), { filename: componentPath })
const compiled = compileTemplate({
    source: descriptor.template.content,
    filename: componentPath,
    id: 'supplier-pending-report',
    compilerOptions: { mode: 'function' },
})

if (compiled.errors.length) throw compiled.errors[0]

const render = new Function('Vue', compiled.code)(Vue)

test('report header does not repeat the selected Supplier and Process filters', async () => {
    const app = Vue.createSSRApp({
        setup() {
            return {
                root: null,
                reportContent: null,
                loading: false,
                copying: false,
                hasFetched: true,
                hasRows: true,
                report: {
                    supplier: 'SUP-001',
                    supplier_name: 'Mahavin Exports',
                    process: 'Stitching',
                    items: [],
                },
                showReport() {},
                copyReport() {},
            }
        },
        render,
    })

    const html = await renderToString(app)

    assert.equal((html.match(/Mahavin Exports/g) || []).length, 1)
    assert.doesNotMatch(html, /Process <strong>Stitching<\/strong>/)
})
