<template>
  	<div ref="root" class="frappe-control">
		<p>Pending Items</p>
		<table class="table table-sm table-bordered">
			<tr v-for="(i, item_index) in items" :key="item_index">
				<td v-if="i.primary_attribute">
					<table class="table table-sm table-bordered" v-if="i.items && i.items.length > 0" >
						<tr>
							<th>S.No.</th>
							<th>Item</th>
							<th>Lot</th>
							<th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
							<th v-for="attr in i.primary_attribute_values" :key="attr">{{ attr }}</th>
							<th v-if="docstatus == 0">Edit</th>
						</tr>
						<tr v-for="(j, item1_index) in i.items" :key="item1_index">
							<td>{{ item1_index + 1 }}</td>
							<td>{{ j.name }}</td>
							<td>{{ j.lot }}</td>
							<td v-for="attr in i.attributes" :key="attr">{{ j.attributes[attr] }}</td>
							<td v-for="attr in j.values" :key="attr">
								<div v-if="attr.qty">
									{{ attr.qty}}<span v-if="j.default_uom">{{ " " + j.default_uom }}</span>
									<span v-if="attr.secondary_qty">
										({{ attr.secondary_qty }}<span v-if="j.secondary_uom">{{" " + j.secondary_uom}}</span>)
									</span>
								</div>
								<div v-else class="text-center">---</div>
							</td>
							<td v-if="docstatus == 0">
								<div class="pull-right cursor-pointer" @click="edit_item(item_index, item1_index)"
									v-html="frappe.utils.icon('edit', 'md', 'mr-1')"></div>
							</td>
						</tr>
					</table>
				</td>
				<td v-else>
					<table class="table table-sm table-bordered" v-if="i.items && i.items.length > 0" >
						<tr>
							<th>S.No.</th>
							<th>Item</th>
							<th>Lot</th>
							<th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
							<th>Pending Quantity</th>
							<th v-if="docstatus == 0">Edit</th>
						</tr>
						<tr v-for="(j, item1_index) in i.items" :key="item1_index">
							<td>{{ item1_index + 1 }}</td>
							<td>{{ j.name }}</td>
							<td>{{ j.lot }}</td>
							<td v-for="attr in i.attributes" :key="attr"> {{ j.attributes[attr] }} </td>
							<td>
								{{ j.values["default"].qty }}<span v-if="j.default_uom">{{ " " + j.default_uom }}</span>
								<span v-if="j.values['default'].secondary_qty"><br />
									({{ j.values["default"].secondary_qty }} <span v-if="j.secondary_uom">{{ " " + j.secondary_uom }}</span>)
								</span>
							</td>
							<td v-if="docstatus == 0">
								<div class="pull-right cursor-pointer" @click="edit_item(item_index, item1_index)"
									v-html="frappe.utils.icon('edit', 'md', 'mr-1')"></div>
							</td>
						</tr>
					</table>
				</td>
			</tr>
		</table>
		<div class="html-container">
			<div class="row">
				<div class="lot-name col-md-5"></div>
				<div class="item-name col-md-5"></div>
			</div>
			<div class="row">
				<div class="attributes col-md-5"></div>
				<div class="attributes-right col-md-5"></div>
			</div>
			<div class="row">
				<div class="type-parameters col-md-5"></div>
			</div>
			<div>
				<div class="qty-parameters row p-4" style="display: flex; gap: 10px"></div>
			</div>
			<div v-if="show_button" style="display: flex; gap: 10px">
				<button class="btn btn-success" @click="add_item()">Add Item</button>
				<button class="btn btn-success" @click="make_clean()">Close</button>
			</div>
			<div v-if="show_button2" style="display: flex; gap: 10px">
				<button class="btn btn-success" @click="update_item()">Update Item</button>
				<button class="btn btn-success" @click="make_clean()">Close</button>
			</div>
		</div>
		<p>Delivered Items</p>
		<table class="table table-sm table-bordered" v-if="check_received_qty">
			<tr v-for="(i, item_index) in items" :key="item_index">
				<td v-if="i.primary_attribute">
					<table class="table table-sm table-bordered" v-if="i.items && i.items.length > 0" >
						<tr>
							<th>Item</th>
							<th>Lot</th>
							<th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
							<th>Type</th>
							<th v-for="attr in i.primary_attribute_values" :key="attr">{{ attr }}</th>
							<th>Edit</th>
						</tr>
						<template v-for="(j, item1_index) in i.items" :key="item1_index">
							<tr v-for="type in j.types" :key="type">
								<td>{{ j.name }}</td>
								<td>{{ j.lot }}</td>
								<td v-for="attr in i.attributes" :key="attr">{{ j.attributes[attr] }}</td>
								<td>{{ type }}</td>
								<td v-for="attr in j.values" :key="attr">
									<div v-if="attr.types">
										<div v-if='typeof(attr.types) == "string"'>
											<div v-for="t in Object.keys(JSON.parse(attr.types))" :key='t'>
												<div v-if="t == type">
													{{JSON.parse(attr.types)[t]}}											
												</div>
											</div>
										</div>
										<div v-else>
											<div v-for="t in Object.keys(attr.types)" :key='t'>
												<div v-if="t == type">
													{{attr.types[t]}}											
												</div>
											</div>	
										</div>	
									</div>
									<div v-else class="text-center">---</div>
								</td>
								<td v-if="docstatus == 0">
									<div class="d-flex justify-content-between">
										<div class="cursor-pointer" @click="edit_delivered_item(item_index, item1_index, type)" 
											v-html="frappe.utils.icon('edit', 'md', 'mr-1')"></div>
										<div class="cursor-pointer" @click="delete_delivered_item(item_index, item1_index, type)" 
											v-html="frappe.utils.icon('delete', 'md', 'mr-1')"></div>
									</div>
								</td>
							</tr>
						</template>
					</table>
				</td>
				<td v-else>
					<table class="table table-sm table-bordered" v-if="i.items && i.items.length > 0" >
						<tr>
							<th>Item</th>
							<th>Lot</th>
							<th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
							<th>Quantity</th>
							<th>Edit</th>
						</tr>
						<tr v-for="(j, item1_index) in i.items" :key="item1_index">
							<td>{{ j.name }}</td>
							<td>{{ j.lot }}</td>
							<td v-for="attr in i.attributes" :key="attr">{{ j.attributes[attr] }}</td>
							<td>
								<div v-if="j.values['default']['types']">
									<div v-if='typeof(j.values["default"]["types"]) == "string"'>
										<div v-for="type in Object.keys(JSON.parse(j.values['default']['types']))" :key='type'>
											{{type}}-{{JSON.parse(j.values['default']['types'])[type]}}
										</div>
									</div>
									<div v-else>
										<div v-for="type in Object.keys(j.values['default']['types'])" :key='type'>
											{{type}}-{{j.values['default']['types'][type]}}
										</div>	
									</div>	
								</div>
								<div v-else class="text-center">---</div>
							</td>
							<td v-if="docstatus == 0">
								<div class="d-flex justify-content-between">
									<div class="cursor-pointer" @click="edit_delivered_item(item_index, item1_index, type)" 
										v-html="frappe.utils.icon('edit', 'md', 'mr-1')"></div>
									<div class="cursor-pointer" @click="delete_delivered_item(item_index, item1_index, type)" 
										v-html="frappe.utils.icon('delete', 'md', 'mr-1')"></div>
								</div>
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
const is_edited = ref(false);
const docstatus = ref(0);
const items = ref([]);
const supplier = ref(null);
const against = ref(null);
const against_id = ref(null);
let _skip_watch = false;
const attribute_values = ref([]);
const qty_attributes = ref([]);
const edit_index = ref(-1);
const edit_index1 = ref(-1);
const cur_item = ref(null);
const cur_lot = ref(null);
let lot_input = null;
let item_input = null;
const sample_doc = ref({});
const controlRefs = ref({
  	quantities: [],
});
let received_type = null;
const show_button = ref(false);
const show_button2 = ref(false);
let types = null;
let qty_parameters = [];
let indexes = [];

const check_received_qty = computed(()=> {
	let x = false
	if(items.value){
		a: for (let i = 0; i < items.value.length; i++) {
			for (let idx = 0; idx < items.value[i]['items'].length; idx++) {
				const row = items.value[i]['items'][idx];
				for (const key of Object.keys(row.values)) {
					if (row.values[key]['received_quantity'] > 0) {
						x = true;
						break a;
					}
				}
			}
		}
	}
	return x
})

function get_index(idx) {
	if (!indexes.includes(idx)) {
		indexes.push(idx);
		i = 0;
	}
	i = i + 1;
	return i;
}

function edit_item(index, index1) {
	let el = root.value;
	controlRefs.value.quantities = [];
	edit_index.value = index;
	edit_index1.value = index1;
	attribute_values.value = [];
	qty_attributes.value = [];
	cur_item.value = null;
	cur_lot.value = null;
	show_button.value = true;
	$(el).find(".qty-parameters").html("");
	let row = items.value[index].items[index1];
	let data1 = row.values;
	let data2 = row.attributes;
	cur_item.value = row.name;
	cur_lot.value = row.lot;
	Object.keys(data1).forEach((key) => {
		const qty = data1[key].qty;
		qty_attributes.value.push({ [key]: qty });
	});
	Object.keys(data2).forEach((key) => {
		const attr = data2[key];
		attribute_values.value.push({ [key]: attr });
	});
	create_attributes( attribute_values.value, qty_attributes.value, cur_item.value, cur_lot.value, index, index1, null);
}

function getControlValues(refs) {
	const values = [];
	refs.forEach((control) => {
		const value = control.get_value();
		values.push(value);
		control.set_value(0);
	});
	return values;
}

function edit_delivered_item(index, index1, type) {
	edit_index.value = index
	edit_index1.value = index1
	let primary_values = Object.keys(items.value[index].items[index1].values)
	let dict = items.value[index].items[index1].values[primary_values[0]]['types']
	if(typeof(dict) == 'string'){
		dict = JSON.parse(dict)
	}
	let el = root.value;
	$(el).find(".type-parameters").html("");
	received_type = frappe.ui.form.make_control({
		parent: $(el).find(".type-parameters"),
		df: {
			fieldtype: "Link",
			fieldname: "types",
			label: "Type",
			options: "GRN Item Type",
			read_only:true,
			onchange: () => {
				const selectedValue = received_type.get_value();
				show_button2.value = true
				qty_attributes.value = [];
				let data1 = items.value[index].items[index1].values
				Object.keys(data1).forEach((key) => {
					let x = data1[key]['types']
					if(typeof(x) == 'string'){
						x = JSON.parse(x)
					}
					const qty = x[selectedValue];
					qty_attributes.value.push({ [key]: qty });
				});
				if (selectedValue && selectedValue !== "" && selectedValue !== null) {
					handleQtyParameters(qty_attributes.value, selectedValue);
				} 
				else {
					show_button2.value = false
					$(el).find(".qty-parameters").html("");
				}
			},
			reqd: true,
		},
		doc: sample_doc.value,
		render_input: true,
	});
	received_type.set_value(type)
}

function delete_delivered_item(index, index1, type){
	is_edited.value = true
	edit_index.value = index
	edit_index1.value = index1 
	let primary = items.value[edit_index.value].items[edit_index1.value]['primary_attribute']
	let types = items.value[edit_index.value].items[edit_index1.value].types
	let new_types = []

	for(let i = 0 ; i < types.length ; i++){
		if (types[i] != type){
			new_types.push(types[i])
		}
	}
	items.value[edit_index.value].items[edit_index1.value].types = new_types
	if(primary){
		Object.keys(items.value[edit_index.value].items[edit_index1.value].values).forEach(row => {
			let received_types = items.value[edit_index.value].items[edit_index1.value].values[row]['types']
			if(typeof(received_types) == 'string'){
				received_types = JSON.parse(received_types)
			}
			let qty = received_types[type]
			delete received_types[type]
			items.value[edit_index.value].items[edit_index1.value].values[row]['types'] = received_types
			items.value[edit_index.value].items[edit_index1.value].values[row]['received_quantity'] -= qty
			items.value[edit_index.value].items[edit_index1.value].values[row]['qty'] += qty
		})
	}
	else{
		let received_types = items.value[edit_index.value].items[edit_index1.value].values['default']['types']
		if(typeof(received_types) == 'string'){
			received_types = JSON.parse(received_types)
		}
		let qty = received_types[type]
		delete received_types[type]
		items.value[edit_index.value].items[edit_index1.value].values['default']['types'] = received_types
		items.value[edit_index.value].items[edit_index1.value].values['default']['received_quantity'] -= qty
		items.value[edit_index.value].items[edit_index1.value].values['default']['qty'] += qty	}
}

function create_attributes( attributes, quantities, item, lot, idx, idx1, type_value) {
	let el = root.value;
	$(el).find(".lot-name").html("");
	let lot_input = frappe.ui.form.make_control({
		parent: $(el).find(".lot-name"),
		df: {
			fieldtype: "Data",
			fieldname: "lot",
			label: "Lot",
			default: lot,
			reqd: true,
		},
		doc: sample_doc.value,
		render_input: true,
	});
	lot_input.set_value(lot);
	lot_input.df.read_only = 1;
	lot_input.refresh();
	$(el).find(".item-name").html("");
	let item_input = frappe.ui.form.make_control({
		parent: $(el).find(".item-name"),
		df: {
			fieldtype: "Data",
			fieldname: "item",
			label: "Item",
			default: item,
			reqd: true,
		},
		doc: sample_doc.value,
		render_input: true,
	});
	item_input.set_value(item);
	item_input.df.read_only = 1;
	item_input.refresh();
	$(el).find(".attributes").html("");
	$(el).find(".attributes-right").html("");

	let attribute_parameters = [];
	attributes.forEach((row, id) => {
		let classname = "";
		Object.keys(row).forEach((key, index) => {
			if (id % 2 == 0) {
				classname += ".attributes";
			} 
			else {
				classname += ".attributes-right";
			}
			attribute_parameters[index] = frappe.ui.form.make_control({
				parent: $(el).find(classname),
				df: {
					fieldtype: "Data",
					fieldname: key + "_parameter",
					label: key,
					reqd: true,
				},
				doc: sample_doc.value,
				render_input: true,
			});
			attribute_parameters[index].set_value(row[key]);
			attribute_parameters[index].df.read_only = 1;
			attribute_parameters[index].refresh();
		});
	});
	$(el).find(".type-parameters").html("");

	let df = {
		fieldtype: "Link",
		fieldname: "types",
		label: "Type",
		options: "GRN Item Type",
		onchange: () => {
			const selectedValue = types.get_value();
			if (selectedValue && selectedValue !== "" && selectedValue !== null) {
				handleQtyParameters(quantities, selectedValue);
			} 
			else {
				$(el).find(".qty-parameters").html("");
			}
		},
		reqd: true,
	};
	if (type_value) {
		df["read_only"] = true;
	}
	types = frappe.ui.form.make_control({
		parent: $(el).find(".type-parameters"),
		df: df,
		doc: sample_doc.value,
		render_input: true,
	});
	if (type_value) {
		handleQtyParameters(quantities, type_value);
		types.set_value(type_value);
		types.refresh();
	}
}

function handleQtyParameters(quantities, value) {
	controlRefs.value.quantities = [];
	let el = root.value;
	$(el).find(".qty-parameters").html("");
	qty_parameters = [];
	quantities.forEach((row, idx) => {
		Object.keys(row).forEach((key, index) => {
			let x = key;
			if (key == "default") {
				key = "Qty";
			}
			qty_parameters[idx] = frappe.ui.form.make_control({
				parent: $(el).find(".qty-parameters"),
				df: {
					fieldtype: "Float",
					fieldname: key + "_" + value,
					label: key + " - " + row[x],
				},
				doc: sample_doc.value,
				render_input: true,
			});
			qty_parameters[idx].set_value(row[key]);
			qty_parameters[idx].refresh();
			controlRefs.value.quantities.push(qty_parameters[idx]);
		});
	});
}

async function add_item() {
	is_edited.value = true;
	let type_selected = types.get_value();
	if (type_selected == null || type_selected == "") {
		frappe.msgprint("Enter The Type");
		make_clean();
		return;
	}
	let type_list = items.value[edit_index.value].items[edit_index1.value]['types']
	if(!type_list){
		type_list = []
		items.value[edit_index.value].items[edit_index1.value]['types'] = []
	}
	let i = type_list.indexOf(type_selected)
	if(i == -1){
		items.value[edit_index.value].items[edit_index1.value]['types'].push(type_selected)
	}
	cur_frm.dirty();
	let data = getControlValues(controlRefs.value.quantities);
	let x = 0;
	controlRefs.value.quantities = [];
	let primary = items.value[edit_index.value].items[edit_index1.value]['primary_attribute']
	if(primary){
		Object.keys(items.value[edit_index.value].items[edit_index1.value].values).forEach(row => {
			items.value[edit_index.value].items[edit_index1.value].values[row]['received_quantity'] += data[x]
			let dict = items.value[edit_index.value].items[edit_index1.value].values[row]['types']
			if(!dict){
				dict = {}
			}
			if(typeof(dict) == 'string'){
				dict = JSON.parse(dict)
			}
			if (dict.hasOwnProperty(type_selected)){
				dict[type_selected] += data[x]
			}
			else{
				dict[type_selected] = data[x]
			}
			items.value[edit_index.value].items[edit_index1.value].values[row]['types'] = dict
			items.value[edit_index.value].items[edit_index1.value].values[row]['qty'] -= data[x]
			x = x + 1
		})
	}
	else{
		let dict = items.value[edit_index.value].items[edit_index1.value].values['default']['types']
		if(!dict){
			dict = {}
		}
		if(typeof(dict) == 'string'){
			dict = JSON.parse(dict)
		}
		if (dict.hasOwnProperty(type_selected)){
			dict[type_selected] += data[x]
		}
		else{
			dict[type_selected] = data[x]
		}
		items.value[edit_index.value].items[edit_index1.value].values['default']['types'] = dict
		items.value[edit_index.value].items[edit_index1.value].values['default']['qty'] -= data[x]
		items.value[edit_index.value].items[edit_index1.value].values['default']['received_quantity'] += data[x]
	}
	types.set_value(null)
  make_clean();
}

function update_item(){
	is_edited.value = true
	cur_frm.dirty()
	let data = getControlValues(controlRefs.value.quantities);
	let x = 0;
	show_button2.value = false
	let type = received_type.get_value()
	controlRefs.value.quantities = [];
	let primary = items.value[edit_index.value].items[edit_index1.value]['primary_attribute']
	if (primary){
		Object.keys(items.value[edit_index.value].items[edit_index1.value].values).forEach(row => {
			let dict = items.value[edit_index.value].items[edit_index1.value].values[row]['types']
			if(typeof(dict) == 'string'){
				dict = JSON.parse(dict)
			}
			items.value[edit_index.value].items[edit_index1.value].values[row]['qty'] += dict[type]
			items.value[edit_index.value].items[edit_index1.value].values[row]['received_quantity'] -= dict[type]
			items.value[edit_index.value].items[edit_index1.value].values[row]['qty'] -= data[x]
			items.value[edit_index.value].items[edit_index1.value].values[row]['received_quantity'] += data[x]
			dict[type] = data[x]
			items.value[edit_index.value].items[edit_index1.value].values[row]['types'] = dict
			x = x + 1
		})
	}
	else{
		let dict = items.value[edit_index.value].items[edit_index1.value].values['default']['types']
		if(typeof(dict) == 'string'){
			dict = JSON.parse(dict)
		}
		items.value[edit_index.value].items[edit_index1.value].values['default']['qty'] += dict[type]
		items.value[edit_index.value].items[edit_index1.value].values['default']['received_quantity'] -= dict[type]
		items.value[edit_index.value].items[edit_index1.value].values['default']['qty'] -= data[x]
		items.value[edit_index.value].items[edit_index1.value].values['default']['received_quantity'] += data[x]
		dict[type] = data[x]
		items.value[edit_index.value].items[edit_index1.value].values['default']['types'] = dict
	}
	make_clean()
}
function make_clean() {
	let el = root.value;
	$(el).find(".qty-parameters").html("");
	$(el).find(".type-parameters").html("");
	$(el).find(".attributes").html("");
	$(el).find(".attributes-right").html("");
	$(el).find(".lot-name").html("");
	$(el).find(".item-name").html("");
	show_button.value = false;
	show_button2.value = false;
	if(types){
		types.set_value(null);
	}
	if(received_type){
		received_type.set_value(null)
	}
}

onMounted(() => {
	console.log("new-grn-work-item mounted");
	EventBus.$on("update_grn_work_details", (data) => {
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

function get_work_order_items() {
	frappe.call({
		method:"production_api.production_api.doctype.work_order.work_order.get_work_order_items",
		args: {
			work_order: against_id.value,
			is_grn: true,
		},
		callback: async function (r) {
			if (r.message) {
				items.value = JSON.parse(JSON.stringify(r.message));
			}
		},
	});
}

function clear_items() {
  	items.value = [];
}

function against_id_changed() {
	if (against_id.value) {
		get_work_order_items();
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
				if ( items.value[i].items[j].values[k].received_quantity == null || items.value[i].items[j].values[k].received_quantity == "" ) {
					items.value[i].items[j].values[k].received_quantity = 0;
				}
			}
		}
	}
	return [items.value, is_edited.value];
}

watch(
	items, (newVal, oldVal) => {
		console.log("Item Updated", _skip_watch);
		if (_skip_watch) {
			_skip_watch = false;
			return;
		}
		EventBus.$emit("grn_updated", true);
	},{ deep: true }
);

defineExpose({
	items,
	load_data,
	update_status,
	get_items,
});
</script>
