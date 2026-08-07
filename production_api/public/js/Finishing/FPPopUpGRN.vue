<template>
    <div ref="root">
        <!-- Dynamic Size Ratio Packing: every row is an auditable GRN packing batch. -->
        <table v-if="mode === 'Size Ratio Packing'" class="table table-sm table-sm-bordered bordered-table">
            <thead class="dark-border">
                <tr>
                    <th>Colour</th>
                    <th>Boxes</th>
                    <th v-for="(size, i) in primary_values" :key="i">{{ size }}</th>
                    <th>Pcs/Box (Required: {{ combo }})</th>
                    <th>Total Pcs</th>
                    <th></th>
                </tr>
            </thead>
            <tbody class="dark-border">
                <tr v-for="(batch, bi) in ratio_batches" :key="batch.key">
                    <td>
                        <select v-model="batch.colour" class="form-control">
                            <option value="">Select</option>
                            <option v-for="colour in colours" :key="colour" :value="colour">{{ colour }}</option>
                        </select>
                    </td>
                    <td><input type="number" min="0" step="1" v-model.number="batch.box_quantity" class="form-control" /></td>
                    <td v-for="(size, i) in primary_values" :key="i">
                        <input type="number" min="0" step="1" v-model.number="batch.ratio[size]" class="form-control" />
                    </td>
                    <td>
                        <b :class="batch_pieces_per_box(batch) === combo ? 'text-success' : 'text-danger'">
                            {{ batch_pieces_per_box(batch) }} / {{ combo }}
                        </b>
                    </td>
                    <td><b>{{ batch_total_pieces(batch) }}</b></td>
                    <td>
                        <button class="btn btn-xs btn-default" @click="copy_batch(batch)">Copy</button>
                        <button class="btn btn-xs btn-danger" @click="remove_batch(bi)" :disabled="ratio_batches.length === 1">×</button>
                    </td>
                </tr>
                <tr>
                    <td><b>Total</b></td>
                    <td><b>{{ total_boxes }}</b></td>
                    <td v-for="(size, i) in primary_values" :key="i"><b>{{ round3(box_qty[size]) }}</b></td>
                    <td></td>
                    <td><b>{{ round3(grn_total) }}</b></td>
                    <td><button class="btn btn-xs btn-primary" @click="add_batch()">Add Ratio</button></td>
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
const ratio_batches = reactive([])
let batch_sequence = 0

function make_batch(source = null) {
    const row = {
        key: ++batch_sequence,
        colour: source
            ? source.colour
            : (colours.value.length === 1 ? colours.value[0] : ''),
        box_quantity: source ? source.box_quantity : 0,
        ratio: {},
    }
    primary_values.value.forEach(size => {
        row.ratio[size] = source
            ? (Number(source.ratio[size]) || 0)
            : (Number(ratio.value[size]) || 0)
    })
    return row
}

function add_batch(source = null) { ratio_batches.push(make_batch(source)) }
function copy_batch(batch) { add_batch(batch) }
function remove_batch(index) { if (ratio_batches.length > 1) ratio_batches.splice(index, 1) }
function batch_pieces_per_box(batch) {
    return primary_values.value.reduce((sum, size) => sum + (Number(batch.ratio[size]) || 0), 0)
}
function batch_total_pieces(batch) {
    return (Number(batch.box_quantity) || 0) * batch_pieces_per_box(batch)
}

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
    if (!ratio_batches.length) add_batch()
    ratio_batches.forEach(batch => {
        primary_values.value.forEach(size => {
            if (!(size in batch.ratio)) batch.ratio[size] = 0
        })
    })
}, { immediate: true })

watch(() => config.value.colours, () => {
    ensure_colour_state()
    if (colours.value.length === 1) {
        ratio_batches.forEach(batch => {
            if (!batch.colour) batch.colour = colours.value[0]
        })
    }
}, { immediate: true })

const combo = computed(() => Number(config.value.packing_combo) || 1)
const ratios_valid = computed(() =>
    mode.value !== 'Size Ratio Packing'
    || ratio_batches.every(batch => batch_pieces_per_box(batch) === combo.value))
const colours_valid = computed(() =>
    mode.value !== 'Size Ratio Packing'
    || ratio_batches.every(batch => colours.value.includes(batch.colour)))

function round3(x) { return Math.round((Number(x) || 0) * 1000) / 1000 }

// GRN payload AND display, in BOXES. Size Ratio splits the boxes entered across sizes by the ratio
// (boxes x ratio / combo); these sum back to the boxes entered. Size Wise (combo=1) passes the count
// through; legacy = typed. The existing pipeline reads these as boxes (x combo = pieces) UNCHANGED.
const box_qty = computed(() => {
    const out = {}
    primary_values.value.forEach(size => { out[size] = 0 })
    if (mode.value === 'Size Ratio Packing') {
        ratio_batches.forEach(batch => {
            const boxes = Number(batch.box_quantity) || 0
            primary_values.value.forEach(size => {
                out[size] += boxes * (Number(batch.ratio[size]) || 0)
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
    mode.value === 'Size Ratio Packing'
        ? ratio_batches.reduce((sum, batch) => sum + (Number(batch.box_quantity) || 0), 0)
        : colours.value.reduce((sum, colour) => sum + (Number(colour_boxes[colour]) || 0), 0))

const packing_batches = computed(() => ratio_batches.map(batch => ({
    colour: batch.colour,
    box_quantity: Number(batch.box_quantity) || 0,
    ratio: Object.fromEntries(primary_values.value.map(size => [size, Number(batch.ratio[size]) || 0])),
})))

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
    packing_batches,
    ratios_valid,
    colours_valid,
    expected_pieces_per_box: combo,
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
