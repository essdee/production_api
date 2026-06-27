<template>
    <div ref="root">
        <!-- Packed / Balance summary (per size) -->
        <table class="table table-sm table-sm-bordered bordered-table">
            <thead class="dark-border">
                <tr>
                    <th>Size</th>
                    <th v-for="(value, index) in primary_values" :key="index"> {{ value }}</th>
                    <th>Total</th>
                </tr>
            </thead>
            <tbody class="dark-border">
                <tr>
                    <td>Packed</td>
                    <td v-for="(value, index) in primary_values" :key="index">{{ packed_qty[value]['packed'] }}</td>
                    <td>{{ props.packed }}</td>
                </tr>
                <tr>
                    <td>Balance</td>
                    <td v-for="(value, index) in primary_values" :key="index">{{ round3(balance(value)) }}</td>
                    <td>{{ round3(props.packed - props.dispatched) }}</td>
                </tr>
            </tbody>
        </table>

        <!-- Size Ratio: enter boxes per colour to dispatch -->
        <table v-if="mode === 'Size Ratio Packing'" class="table table-sm table-sm-bordered bordered-table">
            <thead class="dark-border">
                <tr>
                    <th>Colour</th>
                    <th>Boxes</th>
                    <th v-for="(size, i) in primary_values" :key="i">{{ size }}</th>
                </tr>
            </thead>
            <tbody class="dark-border">
                <tr v-for="(colour, ci) in colours" :key="ci">
                    <td>{{ colour }}</td>
                    <td><input type="number" min="0" v-model.number="colour_boxes[colour]" class="form-control" /></td>
                    <td v-for="(size, i) in primary_values" :key="i">
                        {{ round3((Number(colour_boxes[colour]) || 0) * (ratio[size] || 0) / combo) }}
                    </td>
                </tr>
                <tr>
                    <td><b>Dispatch</b></td>
                    <td><b>{{ total_boxes }}</b></td>
                    <td v-for="(size, i) in primary_values" :key="i">
                        <b :style="over(size) ? 'color:red' : ''">{{ round3(dispatch_by_size[size]) }}</b>
                    </td>
                </tr>
            </tbody>
        </table>

        <!-- Size Wise: enter free boxes per colour x size -->
        <table v-else-if="mode === 'Size Wise Packing'" class="table table-sm table-sm-bordered bordered-table">
            <thead class="dark-border">
                <tr>
                    <th>Colour \ Size</th>
                    <th v-for="(size, i) in primary_values" :key="i">{{ size }}</th>
                    <th>Total</th>
                </tr>
            </thead>
            <tbody class="dark-border">
                <tr v-for="(colour, ci) in colours" :key="ci">
                    <td>{{ colour }}</td>
                    <td v-for="(size, i) in primary_values" :key="i">
                        <input type="number" min="0" v-model.number="colour_size[colour][size]" class="form-control" />
                    </td>
                    <td>{{ colour_total(colour) }}</td>
                </tr>
                <tr>
                    <td><b>Dispatch</b></td>
                    <td v-for="(size, i) in primary_values" :key="i">
                        <b :style="over(size) ? 'color:red' : ''">{{ round3(dispatch_by_size[size]) }}</b>
                    </td>
                    <td><b>{{ round3(dispatch_grand_total) }}</b></td>
                </tr>
            </tbody>
        </table>

        <!-- Legacy: per-size dispatch input -->
        <table v-else class="table table-sm table-sm-bordered bordered-table">
            <thead class="dark-border">
                <tr>
                    <th>Size</th>
                    <th v-for="(value, index) in primary_values" :key="index">{{ value }}</th>
                    <th>Total</th>
                </tr>
            </thead>
            <tbody class="dark-border">
                <tr>
                    <td>Dispatch Qty</td>
                    <td v-for="(value, index) in primary_values" :key="index">
                        <input type="number" v-model.number="packed_qty[value]['cur_dispatch']" class="form-control" />
                    </td>
                    <td>{{ dispatch_grand_total }}</td>
                </tr>
            </tbody>
        </table>
    </div>
</template>

<script setup>
import { ref, reactive, watch, computed } from 'vue';

const root = ref(null);
const primary_values = ref([])
let packed_qty = ref({})
const props = defineProps(['packed_qty', 'primary_values', 'packed', 'dispatched', 'packing_config'])

function round3(x) { return Math.round((Number(x) || 0) * 1000) / 1000 }

const config = computed(() => props.packing_config || {})
const mode = computed(() => {
    const c = config.value
    return (c.based_on_other_attribute_mapping && c.packing_mode) ? c.packing_mode : null
})
const colours = computed(() => config.value.colours || [])
const combo = computed(() => Number(config.value.packing_combo) || 1)
const ratio = computed(() => {
    const r = {}
    ;(config.value.packing_size_details || []).forEach(d => { r[d.attribute_value] = d.quantity })
    return r
})

const colour_boxes = reactive({})        // Size Ratio: { colour: boxes }
const colour_size = reactive({})         // Size Wise:  { colour: { size: boxes } }

function ensure_colour_state() {
    colours.value.forEach(colour => {
        if (!(colour in colour_boxes)) colour_boxes[colour] = 0
        if (!colour_size[colour]) colour_size[colour] = {}
        primary_values.value.forEach(size => {
            if (!(size in colour_size[colour])) colour_size[colour][size] = 0
        })
    })
}

watch(() => props.packed_qty, (packed) => {
    packed_qty.value = packed || {}
}, { immediate: true })

watch(() => props.primary_values, (primary) => {
    primary_values.value = primary || []
    ensure_colour_state()
}, { immediate: true })

watch(() => config.value.colours, () => ensure_colour_state(), { immediate: true })

function balance(size) {
    const row = packed_qty.value[size] || {}
    return (Number(row.packed) || 0) - (Number(row.dispatched) || 0)
}
function over(size) {
    return (Number(dispatch_by_size.value[size]) || 0) > balance(size) + 1e-6
}

// Per-size dispatch (cur_dispatch): Size Ratio = boxes split by ratio; Size Wise = entered boxes;
// legacy = the per-size input typed directly into packed_qty.
const dispatch_by_size = computed(() => {
    const out = {}
    primary_values.value.forEach(size => { out[size] = 0 })
    if (mode.value === 'Size Ratio Packing') {
        const c = combo.value
        colours.value.forEach(colour => {
            const boxes = Number(colour_boxes[colour]) || 0
            primary_values.value.forEach(size => { out[size] += boxes * (ratio.value[size] || 0) / c })
        })
    } else if (mode.value === 'Size Wise Packing') {
        colours.value.forEach(colour => {
            primary_values.value.forEach(size => { out[size] += Number((colour_size[colour] || {})[size]) || 0 })
        })
    } else {
        primary_values.value.forEach(size => { out[size] = Number((packed_qty.value[size] || {}).cur_dispatch) || 0 })
    }
    return out
})

// Push the rolled-up per-size dispatch into packed_qty.cur_dispatch so create_stock_entry (unchanged)
// reads the right size-only numbers. Only for the colour modes; legacy writes cur_dispatch directly.
watch(dispatch_by_size, (val) => {
    if (!mode.value) return
    primary_values.value.forEach(size => {
        if (!packed_qty.value[size]) packed_qty.value[size] = { packed: 0, dispatched: 0, cur_dispatch: 0 }
        packed_qty.value[size].cur_dispatch = val[size] || 0
    })
}, { deep: true, immediate: true })

// Colour x size grid (print-only metadata): { colour: { size: boxes } }, non-zero entries only.
const colour_details = computed(() => {
    const out = {}
    if (mode.value === 'Size Ratio Packing') {
        const c = combo.value
        colours.value.forEach(colour => {
            const boxes = Number(colour_boxes[colour]) || 0
            if (boxes <= 0) return
            out[colour] = {}
            primary_values.value.forEach(size => { out[colour][size] = round3(boxes * (ratio.value[size] || 0) / c) })
        })
    } else if (mode.value === 'Size Wise Packing') {
        colours.value.forEach(colour => {
            const row = {}
            let any = false
            primary_values.value.forEach(size => {
                const v = Number((colour_size[colour] || {})[size]) || 0
                if (v) { row[size] = v; any = true }
            })
            if (any) out[colour] = row
        })
    }
    return out
})

const total_boxes = computed(() =>
    colours.value.reduce((sum, colour) => sum + (Number(colour_boxes[colour]) || 0), 0))

function colour_total(colour) {
    return primary_values.value.reduce(
        (sum, size) => sum + (Number((colour_size[colour] || {})[size]) || 0), 0)
}

const dispatch_grand_total = computed(() =>
    primary_values.value.reduce((sum, size) => sum + (Number(dispatch_by_size.value[size]) || 0), 0))

defineExpose({
    packed_qty,
    colour_details,
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
