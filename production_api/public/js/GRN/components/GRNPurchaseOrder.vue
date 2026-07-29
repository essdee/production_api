<template>
	<div ref="root" class="frappe-control">
		<table v-if="docstatus !== 0" class="table table-sm table-bordered">
			<tr v-for="(i, item_index) in items" :key="item_index">
				<td v-if="i.primary_attribute">
					<table class="table table-sm table-bordered" v-if="i.items && i.items.length > 0">
						<tr>
							<th>S.No.</th>
							<th>Item</th>
							<th>Lot</th>
							<th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
							<th v-for="attr in i.primary_attribute_values" :key="attr">{{ attr }}</th>
							<th>Comments</th>
						</tr>
						<tr v-for="(j, item1_index) in i.items" :key="item1_index">
							<td>{{ item1_index + 1 }}</td>
							<td>{{ j.name }}</td>
							<td>{{ j.lot }}</td>
							<td v-for="attr in i.attributes" :key="attr">
								{{ j.attributes[attr] }}
							</td>
							<td v-for="attr in i.primary_attribute_values" :key="attr">
								<!-- MULTI-LOT MODE: per-lot breakdown -->
								<template v-if="has_lots">
									<div v-if="j.values[attr] && (j.values[attr].lot_rows?.length || j.values[attr].received)">
										<div v-for="(lr, lidx) in (j.values[attr].lot_rows || [])" :key="lidx">
											{{ lr.lot }}: {{ lr.received }}<span v-if="j.default_uom">{{ " " + j.default_uom }}</span>
										</div>
										<div v-if="!j.values[attr].lot_rows">{{ j.values[attr].received }} {{ j.default_uom }}</div>
									</div>
									<div v-else class="text-center">---</div>
								</template>
								<!-- LEGACY MODE (no linked lots): today's single received rendering, unchanged -->
								<template v-else>
									<div v-if="j.values[attr]?.received">
										{{ j.values[attr] ? j.values[attr].received : 0 }}
										<span v-if="j.default_uom">{{" " + j.default_uom}}</span>
										<span v-if="j.values[attr]?.secondary_qty">
											({{ j.values[attr] ? j.values[attr].secondary_received : 0 }}
											<span v-if="j.secondary_uom">{{" " + j.secondary_uom}}</span>)
										</span>
									</div>
									<div v-else class="text-center">---</div>
								</template>
							</td>
							<td>{{ j.comments }}</td>
						</tr>
					</table>
				</td>
				<td v-else>
					<table class="table table-sm table-bordered" v-if="i.items && i.items.length > 0">
						<tr>
							<th>S.No.</th>
							<th>Item</th>
							<th>Lot</th>
							<th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
							<th>Received Quantity</th>
							<th>Comments</th>
						</tr>
						<tr v-for="(j, item1_index) in i.items" :key="item1_index">
							<td>{{ item1_index + 1 }}</td>
							<td>{{ j.name }}</td>
							<td>{{ j.lot }}</td>
							<td v-for="attr in i.attributes" :key="attr">
								{{ j.attributes[attr] }}
							</td>
							<td>
								<!-- MULTI-LOT MODE: per-lot breakdown -->
								<template v-if="has_lots">
									<div v-for="(lr, lidx) in (j.values['default'].lot_rows || [])" :key="lidx">
										{{ lr.lot }}: {{ lr.received }}<span v-if="j.default_uom">{{ " " + j.default_uom }}</span>
									</div>
									<div v-if="!j.values['default'].lot_rows">{{ j.values['default'].received }} {{ j.default_uom }}</div>
								</template>
								<!-- LEGACY MODE: today's single received rendering, unchanged -->
								<template v-else>
									{{ j.values["default"].received}}
									<span v-if="j.default_uom">{{ " " + j.default_uom }}</span>
									<span v-if="j.values['default'].secondary_received">
										<br />({{ j.values["default"].secondary_received}}
										<span v-if="j.secondary_uom">{{" " + j.secondary_uom}}</span>)
									</span>
								</template>
							</td>
							<td>{{ j.comments }}</td>
						</tr>
					</table>
				</td>
			</tr>
		</table>
		<table v-else-if="against_id" class="table table-sm table-bordered">
			<tr v-for="(i, item_index) in items" :key="item_index">
				<td v-if="i.primary_attribute">
					<table class="table table-sm table-bordered" v-if="i.items && i.items.length > 0">
						<tr>
							<th>S.No.</th>
							<th>Item</th>
							<th>Lot</th>
							<th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
							<th v-for="attr in i.primary_attribute_values" :key="attr">{{ attr }}</th>
							<th>Comments</th>
						</tr>
						<tr v-for="(j, item1_index) in i.items" :key="item1_index">
							<td>{{ item1_index + 1 }}</td>
							<td>{{ j.name }}</td>
							<td>{{ j.lot }}</td>
							<td v-for="attr in i.attributes" :key="attr">
								{{ j.attributes[attr] }}
							</td>
							<td v-for="attr in i.primary_attribute_values" :key="attr">
								<div v-if="j.values[attr] && j.values[attr].ref_docname">
									<!-- MULTI-LOT MODE: lot split editor -->
									<template v-if="has_lots">
										<div class="text-muted" style="font-size:11px;">
											Pending: {{ j.values[attr].pending_qty }} {{ j.default_uom }}
										</div>
										<div v-for="(lr, lidx) in (j.values[attr].lot_rows || [])" :key="lidx"
											style="display:flex; gap:4px; margin-bottom:2px;">
											<select class="form-control" v-model="lr.lot" @change="mark_dirty()">
												<option value="">-- lot --</option>
												<option v-for="lot in po_lots" :key="lot" :value="lot">{{ lot }}</option>
											</select>
											<input class="form-control" type="number" step="0.001" min="0"
												v-model.number="lr.received"
												@blur="update_received_qty(lr, 'received')" />
											<button type="button" class="btn btn-xs btn-danger"
												v-if="j.values[attr].lot_rows && j.values[attr].lot_rows.length > 1"
												@click="remove_lot_row(j.values[attr], lidx)">&times;</button>
										</div>
										<button type="button" class="btn btn-xs btn-default"
											@click="add_lot_row(j.values[attr], j.lot)">+ Lot</button>
									</template>
									<!-- LEGACY MODE (no linked lots): today's single received input, unchanged -->
									<template v-else>
										{{ j.values[attr].qty }}<span v-if="j.default_uom">{{ " " + j.default_uom }}</span>
										<form>
											<input class="form-control" type="number" v-model.number="j.values[attr].received"
												@blur="update_received_qty(j.values[attr], 'received')" min="0" step="0.001"/>
										</form>
									</template>
								</div>
								<div v-else class="text-center">---</div>
							</td>
							<td>
								<input class="form-control" type="text" v-model="j.comments" />
							</td>
						</tr>
					</table>
				</td>
				<td v-else>
					<table class="table table-sm table-bordered" v-if="i.items && i.items.length > 0">
						<tr>
							<th>S.No.</th>
							<th>Item</th>
							<th>Lot</th>
							<th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
							<th>Pending Quantity</th>
							<th>Received Quantity</th>
							<th>Comments</th>
						</tr>
						<tr v-for="(j, item1_index) in i.items" :key="item1_index">
							<td>{{ item1_index + 1 }}</td>
							<td>{{ j.name }}</td>
							<td>{{ j.lot }}</td>
							<td v-for="attr in i.attributes" :key="attr">
								{{ j.attributes[attr] }}
							</td>
							<td>
								{{ j.values["default"].pending_qty}}
								<span v-if="j.default_uom">{{ " " + j.default_uom }}</span>
								<span v-if="j.values['default'].secondary_qty">
									<br />({{ j.values["default"].secondary_qty}}
									<span v-if="j.secondary_uom">{{" " + j.secondary_uom}}</span>)
								</span>
							</td>
							<td>
								<!-- MULTI-LOT MODE: lot split editor -->
								<template v-if="has_lots">
									<div v-for="(lr, lidx) in (j.values['default'].lot_rows || [])" :key="lidx"
										style="display:flex; gap:4px; margin-bottom:2px;">
										<select class="form-control" v-model="lr.lot" @change="mark_dirty()">
											<option value="">-- lot --</option>
											<option v-for="lot in po_lots" :key="lot" :value="lot">{{ lot }}</option>
										</select>
										<input class="form-control" type="number" step="0.001" min="0"
											v-model.number="lr.received"
											@blur="update_received_qty(lr, 'received')" />
										<button type="button" class="btn btn-xs btn-danger"
											v-if="j.values['default'].lot_rows && j.values['default'].lot_rows.length > 1"
											@click="remove_lot_row(j.values['default'], lidx)">&times;</button>
									</div>
									<button type="button" class="btn btn-xs btn-default"
										@click="add_lot_row(j.values['default'], j.lot)">+ Lot</button>
								</template>
								<!-- LEGACY MODE: today's single received input, unchanged -->
								<template v-else>
									<form>
										<input class="form-control" type="number"
											v-model.number="j.values['default'].received" step="0.001"
											@blur="update_received_qty(j.values['default'], 'received')" min="0"/>
									</form>
								</template>
							</td>
							<td>
								<input class="form-control" type="text" v-model="j.comments" />
							</td>
						</tr>
					</table>
				</td>
			</tr>
		</table>
	</div>
</template>

<script setup>
import EventBus from "../../bus";

import { ref, onMounted, computed, watch } from "vue";
const root = ref(null);
let i = 0;
const docstatus = ref(0);
const items = ref([]);
const supplier = ref(null);
const against = ref(null);
const against_id = ref(null);
let _skip_watch = false;
const attribute_values = ref([]);
const po_lots = ref([]);
const has_lots = computed(() => po_lots.value.length > 0);   // multi-lot mode gate

onMounted(() => {
	console.log("new-grn-item mounted");
	EventBus.$on("update_grn_details", (data) => {
		load_data(data);
	});
});

function load_data(data, skip_watch = false) {
  	if (data) {
		if (data.hasOwnProperty("supplier")) {
			supplier.value = data["supplier"];
		}
		if (data.hasOwnProperty("against")) {
			against.value = data["against"];
		}
		if (data.hasOwnProperty("against_id")) {
			against_id.value = data["against_id"];
		}
		if (data.hasOwnProperty("docstatus")) {
			docstatus.value = data["docstatus"];
		}
		if (data.hasOwnProperty("items")) {
			items.value = data["items"];
		}
		if (data.hasOwnProperty("against_id") && !skip_watch) {
			against_id_changed();
		}
		if (data.hasOwnProperty("items")) {
			_skip_watch = skip_watch;
		}
		// Always refresh the PO's linked-lot list when we know the PO — covers
		// both new GRNs (against_id picked in the form) and saved/submitted GRN
		// reopens (loaded with skip_watch, so against_id_changed doesn't run).
		if (data.hasOwnProperty("against_id") && against_id.value) {
			get_po_lots();
		}
	}
}

function update_status() {
  	docstatus.value = cur_frm.doc.docstatus;
}

function get_po_lots() {
	if (!against_id.value) return;
	frappe.call({
		method: "production_api.production_api.doctype.purchase_order.purchase_order.get_purchase_order_lots",
		args: { purchase_order: against_id.value },
		callback: (r) => {
			po_lots.value = r.message || [];
			// If the grid was already loaded before the lot list arrived, seed
			// lot_rows now so the split editor has rows to render.
			seed_lot_rows();
		},
	});
}

// Seed a single lot_rows entry on each real PO cell (one that carries a
// ref_docname) that doesn't have one yet — multi-lot mode only.
function seed_lot_rows() {
	if (!has_lots.value) return;
	for (const grp of items.value) {
		for (const it of (grp.items || [])) {
			for (const key in it.values) {
				const cell = it.values[key];
				if (!cell || !cell.ref_docname || cell.lot_rows) continue;
				const seed_lot = (po_lots.value.includes(it.lot)) ? it.lot : (po_lots.value[0] || it.lot || "");
				cell.lot_rows = [{ lot: seed_lot, received: null, secondary_received: null }];
			}
		}
	}
}

function get_purchase_order_items() {
	frappe.call({
		method:"production_api.production_api.doctype.purchase_order.purchase_order.get_purchase_order_items",
		args: {
			purchase_order: against_id.value,
		},
		callback: function (r) {
			if (r.message) {
				items.value = r.message;
				// Seed lot_rows for the fresh grid (no-op when not multi-lot).
				seed_lot_rows();
			}
		},
	});
}

function clear_items() {
  	items.value = [];
}

function against_id_changed() {

	if (against_id.value) {

        get_purchase_order_items();
        get_po_lots();
	}
	else {
		clear_items();
	}
}

function add_lot_row(cell, default_lot) {
	if (!cell.lot_rows) cell.lot_rows = [];
	cell.lot_rows.push({ lot: (po_lots.value[0] || default_lot || ""), received: null, secondary_received: null });
	mark_dirty();
}

function remove_lot_row(cell, idx) {
	cell.lot_rows.splice(idx, 1);
	mark_dirty();
}

function mark_dirty() {
	if (typeof cur_frm !== "undefined" && cur_frm) cur_frm.dirty();
	EventBus.$emit("grn_updated", true);
}

function get_items() {
  // Parse the received values to 0 if it is empty or null; normalize lot_rows.
	for (let i in items.value) {
		for (let j in items.value[i].items) {
			for (let k in items.value[i].items[j].values) {
				const cell = items.value[i].items[j].values[k];
				if (cell && cell.lot_rows) {
					// multi-lot mode: drop empty lot rows, coerce blanks to 0
					cell.lot_rows = cell.lot_rows.filter(lr => lr.lot && (lr.received || lr.secondary_received));
					for (const lr of cell.lot_rows) {
						lr.received = (lr.received == null || lr.received === "") ? 0 : lr.received;
						lr.secondary_received = (lr.secondary_received == null || lr.secondary_received === "") ? 0 : lr.secondary_received;
					}
					continue;
				}
				if (cell.received == null || cell.received == "") {
					cell.received = 0;
				}
				if (cell.secondary_received == null || cell.secondary_received == "") {
					cell.secondary_received = 0;
				}
			}
		}
	}
	return items.value;
}

function update_received_qty(item, key) {
	item[key] = parseFloat(parseFloat(item[key]).toFixed(3));
	cur_frm.dirty()
}

watch(
	items, (newVal, oldVal) => {
		console.log("Item Updated", _skip_watch);
		if (_skip_watch) {
		_skip_watch = false;
		return;
		}
		EventBus.$emit("grn_updated", true);
  	},
  	{ deep: true }
);

defineExpose({
	items,
	load_data,
	update_status,
	get_items,
});
</script>
