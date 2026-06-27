<template>
    <div>
        <div v-if="items && items.length > 0">
            <div v-for="row in items" :key="row.lot + '::' + row.item">
                <h3>{{ row.lot }}-{{ row.item }}</h3>
                <table class="table table-sm table-sm-bordered bordered-table">
                    <thead class="dark-border">
                        <tr>
                            <th>{{ row.primary_attribute }}</th>
                            <th v-for="(val, size) in row.values" :key="size">{{ size }}</th>
                            <th>Total</th>
                        </tr>
                    </thead>
                    <tbody class="dark-border">
                        <tr>
                            <td>Balance</td>
                            <td v-for="(val, size) in row.values" :key="size">{{ val['qty'] }}</td>
                            <td>{{ row.total['total_qty'] }}</td>
                        </tr>
                        <!-- Legacy / no packing mode: per-size dispatch input (unchanged) -->
                        <tr v-if="!row._mode">
                            <td>Dispatch Qty</td>
                            <td v-for="(val, size) in row.values" :key="size">
                                <input v-if="docstatus == 0" type="number" v-model.number="row.values[size]['dispatch_qty']"
                                    class="form-control" @input="update_total(row); make_dirty()" />
                                <span v-else>{{ val['dispatch_qty'] }}</span>
                            </td>
                            <td>{{ row.total['total_dispatch'] }}</td>
                        </tr>
                        <!-- Mode + submitted: show the rolled-up dispatch read-only -->
                        <tr v-else-if="docstatus != 0">
                            <td>Dispatch Qty</td>
                            <td v-for="(val, size) in row.values" :key="size">{{ val['dispatch_qty'] }}</td>
                            <td>{{ row.total['total_dispatch'] }}</td>
                        </tr>
                    </tbody>
                </table>

                <!-- Size Ratio: enter boxes per colour (draft only) -->
                <table v-if="row._mode === 'Size Ratio Packing' && docstatus == 0"
                    class="table table-sm table-sm-bordered bordered-table">
                    <thead class="dark-border">
                        <tr>
                            <th>Colour</th>
                            <th>Boxes</th>
                            <th v-for="(val, size) in row.values" :key="size">{{ size }}</th>
                        </tr>
                    </thead>
                    <tbody class="dark-border">
                        <tr v-for="colour in row._colours" :key="colour">
                            <td>{{ colour }}</td>
                            <td><input type="number" min="0" v-model.number="row._colour_boxes[colour]"
                                class="form-control" @input="recompute(row)" /></td>
                            <td v-for="(val, size) in row.values" :key="size">
                                {{ round3((Number(row._colour_boxes[colour]) || 0) * (row._ratio[size] || 0) / row._combo) }}
                            </td>
                        </tr>
                        <tr>
                            <td><b>Dispatch</b></td>
                            <td><b>{{ total_boxes(row) }}</b></td>
                            <td v-for="(val, size) in row.values" :key="size"><b>{{ round3(val['dispatch_qty']) }}</b></td>
                        </tr>
                    </tbody>
                </table>

                <!-- Size Wise: enter free boxes per colour x size (draft only) -->
                <table v-else-if="row._mode === 'Size Wise Packing' && docstatus == 0"
                    class="table table-sm table-sm-bordered bordered-table">
                    <thead class="dark-border">
                        <tr>
                            <th>Colour \ Size</th>
                            <th v-for="(val, size) in row.values" :key="size">{{ size }}</th>
                            <th>Total</th>
                        </tr>
                    </thead>
                    <tbody class="dark-border">
                        <tr v-for="colour in row._colours" :key="colour">
                            <td>{{ colour }}</td>
                            <td v-for="(val, size) in row.values" :key="size">
                                <input type="number" min="0" v-model.number="row._colour_size[colour][size]"
                                    class="form-control" @input="recompute(row)" />
                            </td>
                            <td>{{ colour_total(row, colour) }}</td>
                        </tr>
                        <tr>
                            <td><b>Dispatch</b></td>
                            <td v-for="(val, size) in row.values" :key="size"><b>{{ val['dispatch_qty'] }}</b></td>
                            <td><b>{{ row.total['total_dispatch'] }}</b></td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref } from 'vue';

let items = ref([])
let docstatus = cur_frm.doc.docstatus

function round3(x) { return Math.round((Number(x) || 0) * 1000) / 1000 }

function load_data(data) {
    items.value = data || []
    items.value.forEach(item => {
        const cfg = item.packing_config || {}
        item._mode = (cfg.based_on_other_attribute_mapping && cfg.packing_mode) ? cfg.packing_mode : null
        item._colours = cfg.colours || []
        item._combo = Number(cfg.packing_combo) || 1
        item._ratio = {}
        ;(cfg.packing_size_details || []).forEach(d => { item._ratio[d.attribute_value] = d.quantity })
        item._colour_boxes = {}
        item._colour_size = {}
        item._colours.forEach(c => {
            item._colour_boxes[c] = 0
            item._colour_size[c] = {}
            for (const size in item.values) item._colour_size[c][size] = 0
        })
        // Restore the previously-saved colour entries so the inputs aren't blank after reload.
        const savedGrid = item.colour_grid || {}
        if (item._mode === 'Size Ratio Packing') {
            for (const colour in savedGrid) {
                if (!(colour in item._colour_boxes)) continue
                let s = 0
                for (const size in savedGrid[colour]) s += Number(savedGrid[colour][size]) || 0
                item._colour_boxes[colour] = round3(s)
            }
        } else if (item._mode === 'Size Wise Packing') {
            for (const colour in savedGrid) {
                if (!item._colour_size[colour]) continue
                for (const size in savedGrid[colour]) item._colour_size[colour][size] = Number(savedGrid[colour][size]) || 0
            }
        }
        if (!item.colour_grid) item.colour_grid = {}
    })
}

function recompute(item) {
    if (item._mode === 'Size Ratio Packing') {
        const combo = item._combo || 1
        for (const size in item.values) {
            let boxes = 0
            item._colours.forEach(colour => {
                boxes += (Number(item._colour_boxes[colour]) || 0) * (item._ratio[size] || 0) / combo
            })
            item.values[size].dispatch_qty = round3(boxes)
        }
        const grid = {}
        item._colours.forEach(colour => {
            const b = Number(item._colour_boxes[colour]) || 0
            if (b <= 0) return
            grid[colour] = {}
            for (const size in item.values) grid[colour][size] = round3(b * (item._ratio[size] || 0) / combo)
        })
        item.colour_grid = grid
    } else if (item._mode === 'Size Wise Packing') {
        for (const size in item.values) {
            let q = 0
            item._colours.forEach(colour => { q += Number((item._colour_size[colour] || {})[size]) || 0 })
            item.values[size].dispatch_qty = q
        }
        const grid = {}
        item._colours.forEach(colour => {
            const r = {}
            let any = false
            for (const size in item.values) {
                const v = Number((item._colour_size[colour] || {})[size]) || 0
                if (v) { r[size] = v; any = true }
            }
            if (any) grid[colour] = r
        })
        item.colour_grid = grid
    }
    update_total(item)
    make_dirty()
}

function total_boxes(item) {
    return item._colours.reduce((s, c) => s + (Number(item._colour_boxes[c]) || 0), 0)
}

function colour_total(item, colour) {
    let t = 0
    for (const size in item.values) t += Number((item._colour_size[colour] || {})[size]) || 0
    return t
}

function update_total(row) {
    let total = 0;
    for (let size in row.values) {
        total += Number(row.values[size].dispatch_qty) || 0;
    }
    row.total.total_dispatch = total;
}

function get_data() {
    return items.value
}

function make_dirty() {
    if (!cur_frm.is_dirty()) {
        cur_frm.dirty()
    }
}

defineExpose({
    load_data,
    get_data,
})

</script>

<style scoped>
.bordered-table {
    width: 100%;
    border: 1px solid #ccc;
    border-collapse: collapse;
}

.bordered-table th,
.bordered-table td {
    border: 1px solid #ccc;
    padding: 6px 8px;
    text-align: center;
}

.bordered-table thead {
    background-color: #f8f9fa;
    font-weight: bold;
}

.dark-border{
    border: 2px solid black;
}
</style>
