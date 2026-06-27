<template>
    <div ref="root">
        <!-- Size Ratio Packing: enter boxes per colour; expand via the size ratio -->
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
                    <td><b>Total</b></td>
                    <td><b>{{ total_boxes }}</b></td>
                    <td v-for="(size, i) in primary_values" :key="i"><b>{{ round3(box_qty[size]) }}</b></td>
                </tr>
            </tbody>
        </table>

        <!-- Size Wise Packing: enter free pieces per colour x size -->
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
                    <td><b>Total</b></td>
                    <td v-for="(size, i) in primary_values" :key="i"><b>{{ round3(box_qty[size]) }}</b></td>
                    <td><b>{{ round3(grn_total) }}</b></td>
                </tr>
            </tbody>
        </table>

        <!-- Legacy: flat per-size entry -->
        <table v-else class="table table-sm table-sm-bordered bordered-table">
            <thead class="dark-border">
                <tr>
                    <th>Size</th>
                    <th v-for="(value, index) in primary_values" :key="index"> {{ value }}</th>
                    <th>Total</th>
                </tr>
            </thead>
            <tbody class="dark-border">
                <tr>
                    <td>Quantity</td>
                    <td v-for="(value, index) in primary_values" :key="index">
                        <input type="number" v-model="flat_qty[value]" class="form-control" />
                    </td>
                    <td>{{ grn_total }}</td>
                </tr>
            </tbody>
        </table>
    </div>
</template>

<script setup>
import { ref, reactive, watch, computed } from 'vue';

const root = ref(null);
const primary_values = ref([])
const flat_qty = ref({})

const props = defineProps(['primary_values', 'box_qty', 'packing_config'])

const config = computed(() => props.packing_config || {})
const mode = computed(() => {
    const c = config.value
    return (c.based_on_other_attribute_mapping && c.packing_mode) ? c.packing_mode : null
})
const colours = computed(() => config.value.colours || [])
const ratio = computed(() => {
    const r = {}
    ;(config.value.packing_size_details || []).forEach(d => { r[d.attribute_value] = d.quantity })
    return r
})

// Per-colour entry state for the two size-wise modes.
const colour_boxes = reactive({})        // Size Ratio: { colour: boxes }
const colour_size = reactive({})         // Size Wise:  { colour: { size: pieces } }

function ensure_colour_state() {
    colours.value.forEach(colour => {
        if (!(colour in colour_boxes)) colour_boxes[colour] = 0
        if (!colour_size[colour]) colour_size[colour] = {}
        primary_values.value.forEach(size => {
            if (!(size in colour_size[colour])) colour_size[colour][size] = 0
        })
    })
}

watch(() => props.box_qty, (box) => {
    flat_qty.value = box || {}
}, { immediate: true })

watch(() => props.primary_values, (primary) => {
    primary_values.value = primary || []
    ensure_colour_state()
}, { immediate: true })

watch(() => config.value.colours, () => ensure_colour_state(), { immediate: true })

const combo = computed(() => Number(config.value.packing_combo) || 1)

function round3(x) { return Math.round((Number(x) || 0) * 1000) / 1000 }

// GRN payload AND display, in BOXES. Size Ratio splits the boxes entered across sizes by the ratio
// (boxes x ratio / combo); these sum back to the boxes entered. Size Wise (combo=1) passes the count
// through; legacy = typed. The existing pipeline reads these as boxes (x combo = pieces) UNCHANGED.
const box_qty = computed(() => {
    const out = {}
    primary_values.value.forEach(size => { out[size] = 0 })
    if (mode.value === 'Size Ratio Packing') {
        const c = combo.value
        colours.value.forEach(colour => {
            const boxes = Number(colour_boxes[colour]) || 0
            primary_values.value.forEach(size => {
                out[size] += boxes * (ratio.value[size] || 0) / c
            })
        })
    } else if (mode.value === 'Size Wise Packing') {
        colours.value.forEach(colour => {
            primary_values.value.forEach(size => {
                out[size] += Number((colour_size[colour] || {})[size]) || 0
            })
        })
    } else {
        primary_values.value.forEach(size => {
            out[size] = Number(flat_qty.value[size]) || 0
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

const grn_total = computed(() => {
    if (!primary_values.value.length) return 0
    const bq = box_qty.value
    return primary_values.value.reduce((sum, size) => sum + (Number(bq[size]) || 0), 0)
})

defineExpose({
    box_qty,
});

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
