<template>
	<div ref="root">
		<!-- Non-set item: Colour × Size grid -->
		<div v-if="!isSetItem && dataLoaded">
			<table class="table table-sm table-bordered" v-if="colours.length > 0 && sizes.length > 0">
				<thead>
					<tr>
						<th>Colour</th>
						<th v-for="size in sizes" :key="size">{{ size }}</th>
						<th class="text-right">Total</th>
					</tr>
				</thead>
				<tbody>
					<tr v-for="(item, idx) in items" :key="idx">
						<td class="align-middle font-weight-bold">{{ item.colour }}</td>
						<td v-for="size in sizes" :key="size">
							<input
								type="number"
								class="form-control form-control-sm text-right"
								style="width: 80px;"
								v-model.number="item.quantities[size]"
								:disabled="readOnly"
								min="0"
								@input="make_dirty"
							/>
						</td>
						<td class="align-middle text-right font-weight-bold">{{ rowTotal(item) }}</td>
					</tr>
				</tbody>
				<tfoot>
					<tr>
						<th>Total</th>
						<th class="text-right" v-for="size in sizes" :key="size">{{ colTotal(size) }}</th>
						<th class="text-right">{{ grandTotal }}</th>
					</tr>
				</tfoot>
			</table>
			<p v-else class="text-muted">No colours or sizes available. Please check the Cutting Order Detail.</p>
		</div>

		<!-- Set item: Colour × Part × Size grid (pre-populated) -->
		<div v-if="isSetItem && dataLoaded">
			<table class="table table-sm table-bordered" v-if="items.length > 0 && sizes.length > 0">
				<thead>
					<tr>
						<th>S.No</th>
						<th>Colour</th>
						<th>Part</th>
						<th v-for="size in sizes" :key="size">{{ size }}</th>
						<th class="text-right">Total</th>
					</tr>
				</thead>
				<tbody>
					<tr v-for="(item, idx) in items" :key="idx">
						<td class="align-middle">{{ idx + 1 }}</td>
						<td class="align-middle font-weight-bold">
							{{ item.colour }}
							<span v-if="item.major_colour && item.colour !== item.major_colour"
								class="text-muted" style="font-size: 0.85em;">
								({{ item.major_colour }})
							</span>
						</td>
						<td class="align-middle">{{ item.part }}</td>
						<td v-for="size in sizes" :key="size">
							<input
								type="number"
								class="form-control form-control-sm text-right"
								style="width: 80px;"
								v-model.number="item.quantities[size]"
								:disabled="readOnly"
								min="0"
								@input="make_dirty"
							/>
						</td>
						<td class="align-middle text-right font-weight-bold">{{ rowTotal(item) }}</td>
					</tr>
				</tbody>
				<tfoot>
					<tr>
						<th colspan="3">Total</th>
						<th class="text-right" v-for="size in sizes" :key="size">{{ colTotal(size) }}</th>
						<th class="text-right">{{ grandTotal }}</th>
					</tr>
				</tfoot>
			</table>
			<p v-else class="text-muted">No data available. Please check the Cutting Order Detail.</p>
		</div>

		<div v-if="!dataLoaded" class="text-muted">Select a Cutting Order Detail to load items.</div>
	</div>
</template>

<script setup>
import { ref, computed } from 'vue';

const root = ref(null);
const isSetItem = ref(false);
const dataLoaded = ref(false);
const readOnly = ref(false);
const sizes = ref([]);
const colours = ref([]);
const parts = ref([]);
const items = ref([]);

function rowTotal(item) {
	return Object.values(item.quantities || {}).reduce((a, b) => (a || 0) + (b || 0), 0);
}

function colTotal(size) {
	return items.value.reduce((sum, item) => sum + (item.quantities[size] || 0), 0);
}

const grandTotal = computed(() => {
	return items.value.reduce((sum, item) => sum + rowTotal(item), 0);
});

function make_dirty() {
	if (cur_frm && !cur_frm.is_dirty()) {
		cur_frm.dirty();
	}
}

function load_data(data) {
	if (!data) {
		dataLoaded.value = false;
		return;
	}
	isSetItem.value = data.is_set_item || false;
	sizes.value = data.sizes || [];
	colours.value = data.colours || [];
	parts.value = data.parts || [];
	items.value = (data.items || []).map(item => ({
		colour: item.colour || '',
		part: item.part || '',
		major_colour: item.major_colour || '',
		quantities: { ...item.quantities },
	}));
	dataLoaded.value = true;
}

function get_data() {
	return {
		is_set_item: isSetItem.value,
		sizes: sizes.value,
		colours: colours.value,
		parts: parts.value,
		items: items.value.map(item => {
			let obj = { colour: item.colour, quantities: { ...item.quantities } };
			if (isSetItem.value) {
				obj.part = item.part || '';
				obj.major_colour = item.major_colour || '';
			}
			return obj;
		}),
	};
}

function set_read_only(val) {
	readOnly.value = val;
}

defineExpose({
	load_data,
	get_data,
	set_read_only,
});
</script>

<style scoped>
input[type="number"] {
	-moz-appearance: textfield;
}
input[type="number"]::-webkit-outer-spin-button,
input[type="number"]::-webkit-inner-spin-button {
	-webkit-appearance: none;
	margin: 0;
}
.font-weight-bold {
	font-weight: 600;
}
</style>
