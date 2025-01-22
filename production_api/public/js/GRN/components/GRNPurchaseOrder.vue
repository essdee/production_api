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
							<td v-for="attr in j.values" :key="attr">
								<div v-if="attr.received">
									{{ attr.received}}
									<span v-if="j.default_uom">{{" " + j.default_uom}}</span>
									<span v-if="attr.secondary_qty">
										({{ attr.secondary_received}}
										<span v-if="j.secondary_uom">{{" " + j.secondary_uom}}</span>)
									</span>
								</div>
								<div v-else class="text-center">---</div>
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
								{{ j.values["default"].received}}
								<span v-if="j.default_uom">{{ " " + j.default_uom }}</span>
								<span v-if="j.values['default'].secondary_received">
									<br />({{ j.values["default"].secondary_received}}
									<span v-if="j.secondary_uom">{{" " + j.secondary_uom}}</span>)
								</span>
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
							<td v-for="attr in j.values" :key="attr">
								<div v-if="attr.qty">
									{{ attr.qty}}<span v-if="j.default_uom">{{ " " + j.default_uom }}</span>
									<span v-if="attr.secondary_qty">
										({{ attr.secondary_qty}}
										<span v-if="j.secondary_uom">{{" " + j.secondary_uom}}</span>)
									</span>
									<form>
										<input class="form-control" type="number" v-model.number="attr.received"
											@blur="update_received_qty(attr, 'received')" min="0" step="0.001"/>
									</form>
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
								<form>
									<input class="form-control" type="number"
										v-model.number="j.values['default'].received" step="0.001"
										@blur="update_received_qty(j.values['default'], 'received')" min="0"/>
								</form>
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

onMounted(() => {
	console.log("new-grn-item mounted");
	EventBus.$on("update_grn_details", (data) => {
		load_data(data);
	});
});

function load_data(data, skip_watch = false) {
  	if (data) {
		// Only update the values which are present in the data object
		// let keys = ['supplier', 'against', 'against_id', 'docstatus', 'items']
		// for (let key in keys) {
		//     if (data.hasOwnProperty(key)) {
		//         this[key] = data[key];
		//     }
		// }
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
	}
}

function update_status() {
  	docstatus.value = cur_frm.doc.docstatus;
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
	} 
	else {
		clear_items();
	}
}

function get_items() {
  // Parse the received values to 0 if it is empty or null
	for (let i in items.value) {
		for (let j in items.value[i].items) {
			for (let k in items.value[i].items[j].values) {
				if(items.value[i].items[j].values[k].received == null || items.value[i].items[j].values[k].received == "") {
					items.value[i].items[j].values[k].received = 0;
				}
				if (items.value[i].items[j].values[k].secondary_received == null ||items.value[i].items[j].values[k].secondary_received == "") {
					items.value[i].items[j].values[k].secondary_received = 0;
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
