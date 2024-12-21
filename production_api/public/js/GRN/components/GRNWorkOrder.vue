<template>
	<div ref="root" class="frappe-control">
		<p>Pending Items</p>
		<table class="table table-sm table-bordered">
			<tr v-for="(i, item_index) in items" :key="item_index">
				<td v-if="i.primary_attribute">
					<table class="table table-sm table-bordered" v-if="i.items && i.items.length > 0">
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
					<table class="table table-sm table-bordered" v-if="i.items && i.items.length > 0">
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
							<td v-for="attr in i.attributes" :key="attr">
								{{ j.attributes[attr] }}
							</td>
							<td>
								{{ j.values["default"].qty}}
								<span v-if="j.default_uom">{{ " " + j.default_uom }}</span>
								<span v-if="j.values['default'].secondary_qty">
									<br />({{ j.values["default"].secondary_qty}}
									<span v-if="j.secondary_uom">{{" " + j.secondary_uom}}</span>)
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
		<p>Delivered Items</p>
		<table class="table table-sm table-bordered">
			<tr v-for="(i, item_index) in items1" :key="item_index">
				<td v-if="i.primary_attribute">
					<table class="table table-sm table-bordered" v-if="i.items && i.items.length > 0">
						<thead>
							<tr>
								<!-- <th>S.No.</th> -->
								<th>Item</th>
								<th>Lot</th>
								<th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
								<th>Type</th>
								<th v-for="attr in i.primary_attribute_values" :key="attr">{{ attr }}</th>
								<th v-if="docstatus == 0">Edit</th>
							</tr>
						</thead>
						<tbody>
							<template v-for="(j, item1_index) in i.items" :key='item1_index'>
								<template v-if="j.created">
									<tr v-for='m in j.types' :key='m'>
										<!-- <td>{{ item1_index + 1 }}</td> -->
										<td>{{ j.name }}</td>
										<td>{{ j.lot }}</td>
										<td v-for="attr in i.attributes" :key="attr">{{ j.attributes[attr] }}</td>
										<td>{{m}}</td>
										<template v-for="attr in Object.keys(j.values)" :key='attr'>
											<template v-for="v in j.values[attr]['val']" :key='v'>
												<td v-if='v["received_type"] == m'>{{v["received_quantity"]}}</td>
											</template>
										</template>
										<td v-if="docstatus == 0">
											<div class="pull-right cursor-pointer" @click="delete_delivered_item(item_index, item1_index, m)"
												v-html="frappe.utils.icon('delete', 'md', 'mr-1')"></div>	
											<div class="pull-right cursor-pointer" @click="edit_delivered_item(item_index, item1_index, m)"
												v-html="frappe.utils.icon('edit', 'md', 'mr-1')"></div>
										</td>
									</tr>
								</template>  
							</template>
						</tbody>
					</table>
				</td>
				<td v-else>
					<table class="table table-sm table-bordered" v-if="i.items && i.items.length > 0 ">
						<thead>
							<tr>
								<!-- <th>S.No.</th> -->
								<th>Item</th>
								<th>Lot</th>
								<th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
								<th>Type</th>
								<th>Quantity</th>
								<th v-if="docstatus == 0">Edit</th>
							</tr>
						</thead>
						<tbody>
							<template v-for="(j, item1_index) in i.items" :key='item1_index'>
								<template v-if="i.created && j.created">
									<tr v-for='m in j.types' :key='m'>
										<!-- <td>{{ item1_index + 1 }}</td> -->
										<td>{{ j.name }}</td>
										<td>{{ j.lot }}</td>
										<td v-for="attr in i.attributes" :key="attr">{{ j.attributes[attr] }}</td>
										<td>{{m}}</td>
										<template v-for="attr in Object.keys(j.values)">
											<template v-for="v in j.values[attr]['val']" :key='v'>
												<td v-if="v['received_type'] == m">{{v["received_quantity"]}}</td>
											</template>
										</template>
										<td v-if="docstatus == 0">
											<div class="pull-right cursor-pointer" @click="delete_delivered_item(item_index, item1_index, m)"
												v-html="frappe.utils.icon('delete', 'md', 'mr-1')"></div>	
											<div class="pull-right cursor-pointer" @click="edit_delivered_item(item_index, item1_index, m)"
												v-html="frappe.utils.icon('edit', 'md', 'mr-1')"></div>
										</td>
									</tr>
								</template>  
							</template>
						</tbody>
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
			<div v-if="show_button" style="display: flex; gap: 10px;">
				<button class="btn btn-success" @click="add_item()">Add Item</button>
				<button class="btn btn-success" @click="make_clean()">Close</button>
			</div>
			<div v-if="show_button2" style="display: flex; gap: 10px;">
				<button class="btn btn-success" @click="update_item()">Update Item</button>
				<button class="btn btn-success" @click="make_clean()">Close</button>
			</div>
		</div>
	</div>
</template>

<script setup>
import EventBus from "../../bus";

import { ref, onMounted, computed, watch } from "vue";
const root = ref(null);
let i = 0;
const is_edited = ref(false)
const docstatus = ref(0);
const items = ref([]);
const items1 = ref([])
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
const received_type_value = ref(null)
const show_button = ref(false);
const show_button2 = ref(false);
let types = null;
let qty_parameters = [];
let indexes = [];

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
	create_attributes(
		attribute_values.value,
		qty_attributes.value,
		cur_item.value,
		cur_lot.value,
		index,
		index1,
		null,
	);
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

function edit_delivered_item(index, index1, received_type){
	let el = root.value;
	controlRefs.value.quantities = [];
	received_type_value.value = received_type
	edit_index.value = index;
	edit_index1.value = index1;
	attribute_values.value = [];
	qty_attributes.value = [];
	cur_item.value = null;
	cur_lot.value = null;
	show_button2.value = true;
	$(el).find(".qty-parameters").html("");
	let row = items.value[index].items[index1];
	let row2 = items1.value[index].items[index1];
	let data1 = row.values;
	let data2 = row.attributes;
	cur_item.value = row.name;
	cur_lot.value = row.lot;
	let data3 = row2.values;
	Object.keys(data3).forEach((key) => {
		data3[key]['val'].forEach((dict,idx)=> {
			if(dict['received_type'] == received_type){
				qty_attributes.value.push({ [key]: dict['received_quantity'] });	
			}
		})
	});
	Object.keys(data2).forEach((key) => {
		const attr = data2[key];
		attribute_values.value.push({ [key]: attr });
	});
	create_attributes(
		attribute_values.value,
		qty_attributes.value,
		cur_item.value,
		cur_lot.value,
		index,
		index1,
		received_type,
	);
}

function delete_delivered_item(index, index1, received_type){
	is_edited.value = true
	Object.keys(items1.value[index].items[index1]['values']).forEach((key) => {
		let vals = items1.value[index].items[index1]['values'][key]['val']
		let arrs = []
		for(let i = 0 ; i < vals.length ; i++){
			if(vals[i]['received_type'] == received_type){
				items.value[index].items[index1]['values'][key]['qty'] += vals[i]['received_quantity']
			}
			else{
				arrs.push(vals[i])
			}
		}
		let types = items1.value[index].items[index1]['types']
		types = types.filter(item => item !== received_type);
		items1.value[index].items[index1]['values'][key]['val'] = arrs
		items1.value[index].items[index1]['types'] = types
	})
}

function create_attributes(attributes, quantities, item, lot, idx, idx1, type_value) {
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
			reqd: true
	}
	if(type_value){
		df['read_only'] = true
	}
	types = frappe.ui.form.make_control({
		parent: $(el).find(".type-parameters"),
		df: df,
		doc: sample_doc.value,
		render_input: true,
	});
	if(type_value){
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
			qty_parameters[idx].set_value(row[key])
			qty_parameters[idx].refresh()
			controlRefs.value.quantities.push(qty_parameters[idx]);
		});
	});
}

function update_item(){
	is_edited.value = true
	cur_frm.dirty()
	let data = getControlValues(controlRefs.value.quantities);
	let x = 0;
	controlRefs.value.quantities = [];
	let type_selected = types.get_value();
    
	if(items1.value[edit_index.value].items[edit_index1.value]['types'].indexOf(type_selected) == -1){
		items1.value[edit_index.value].items[edit_index1.value]['types'].push(type_selected)
	}
	if(items1.value[edit_index.value]['primary_attribute']){
		Object.keys(items1.value[edit_index.value].items[edit_index1.value].values).forEach((row, index) => {
			items1.value[edit_index.value].items[edit_index1.value]["values"][row]['val'].forEach((dict,idx)=> {
				if(dict['received_type'] == type_selected){
					items.value[edit_index.value].items[edit_index1.value]["values"][row]['qty'] += items1.value[edit_index.value].items[edit_index1.value]["values"][row]['val'][idx]['received_quantity']
					items.value[edit_index.value].items[edit_index1.value]["values"][row]['qty'] -= data[x]
					items1.value[edit_index.value].items[edit_index1.value]["values"][row]['val'][idx]['received_quantity'] = data[x]
					bool = false
				}
			})
			x = x + 1;
		});
	}
	else{
		items.value[edit_index.value].items[edit_index1.value]['values']['default']['qty'] += items1.value[edit_index.value].items[edit_index1.value]['values']['default']['received']
		items.value[edit_index.value].items[edit_index1.value]['values']['default']['qty'] -= data[x]
		items1.value[edit_index.value].items[edit_index1.value]['values']['default']['received'] = data[x]
		items1.value[edit_index.value].items[edit_index1.value]['values']['default']['val'].forEach((dict,idx) => {
			if(dict['received_type'] == received_type_value){
				items1.value[edit_index.value].items[edit_index1.value]['values']['default']['val'][idx]['received_quantity'] += data[x]
			}
		})
	}	
	make_clean()
}

async function add_item() {
	is_edited.value = true
	let type_selected = types.get_value();
	if(type_selected == null || type_selected == ""){
		frappe.msgprint("Enter The Type")
		make_clean()
		return
	}
    cur_frm.dirty()
    if(items1.value.length == 0){
        items1.value = JSON.parse(JSON.stringify(items.value)); 
        await get_items_structure()
    }
	let data = getControlValues(controlRefs.value.quantities);
	let x = 0;
	controlRefs.value.quantities = [];
    
	if(items1.value[edit_index.value].items[edit_index1.value]['types'].indexOf(type_selected) == -1){
		items1.value[edit_index.value].items[edit_index1.value]['types'].push(type_selected)
	}
	if(items1.value[edit_index.value]['primary_attribute']){
		Object.keys(items1.value[edit_index.value].items[edit_index1.value].values).forEach((row, index) => {
			let bool = true
			items1.value[edit_index.value].items[edit_index1.value]["values"][row]['val'].forEach((dict,idx)=> {
				if(dict['received_type'] == type_selected){
					items.value[edit_index.value].items[edit_index1.value]["values"][row]['qty'] -= data[x]
					// if( items.value[edit_index.value].items[edit_index1.value]["values"][row]['qty'] < 0 ){
					// 	frappe.throw(`For ${items1.value[edit_index.value]['primary_attribute']} ${row}, Quantity ${data[x]} is not applicable`)
					// }
					items1.value[edit_index.value].items[edit_index1.value]["values"][row]['val'][idx]['received_quantity'] += data[x]
					bool = false
				}
			})
			if(bool){
				items.value[edit_index.value].items[edit_index1.value]["values"][row]['qty'] -= data[x]
				// if(items.value[edit_index.value].items[edit_index1.value]["values"][row]['qty'] < 0 ){
				// 	frappe.throw(`For ${items1.value[edit_index.value]['primary_attribute']} ${row}, Quantity ${data[x]} is not applicable`)
				// }
				items1.value[edit_index.value].items[edit_index1.value]["values"][row]['val'].push({
					'received_type':type_selected,
					'received_quantity':data[x]
				})
			}
			x = x + 1;
		});
	}
	else{
		items.value[edit_index.value].items[edit_index1.value]['values']['default']['qty'] -= data[x]
		// if(items.value[edit_index.value].items[edit_index1.value]['values']['default']['qty'] < 0 ){
		// 	frappe.throw(`Quantity ${data[x]} is not applicable`)
		// }
		items1.value[edit_index.value].items[edit_index1.value]['values']['default']['received'] += data[x]
		let m = true
		items1.value[edit_index.value].items[edit_index1.value]['values']['default']['val'].forEach((dict,idx) => {
			if(dict['received_type'] == null){
				m = false
				items1.value[edit_index.value].items[edit_index1.value]['values']['default']['val'][idx] = {
					"received_type":type_selected,
					"received_quantity":data[x],
				}
			}
		})
		if(m){
			items1.value[edit_index.value].items[edit_index1.value]['values']['default']['val'].forEach((dict,idx) => {
				if(dict['received_type'] == type_selected){
					m = false
					items1.value[edit_index.value].items[edit_index1.value]['values']['default']['val'][idx]['received_quantity'] += data[x]
				}
			})	
		}
		if(m){
			items1.value[edit_index.value].items[edit_index1.value]['values']['default']['val'].push({
				"received_type":type_selected,
				"received_quantity":data[x],
			})
		}
	}
	
	items1.value[edit_index.value]["created"] = 1;
	items1.value[edit_index.value].items[edit_index1.value]["created"] = 1;
	make_clean()
}

function make_clean(){
	let el = root.value;
	$(el).find(".qty-parameters").html("");
	$(el).find(".type-parameters").html("");
	$(el).find(".attributes").html("");
	$(el).find(".attributes-right").html("");
	$(el).find(".lot-name").html("");
	$(el).find(".item-name").html("");
	show_button.value = false;
	show_button2.value = false;
	types.set_value(null)
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
		if (data.hasOwnProperty("delivered_items")) {
			items1.value = data["delivered_items"];
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
			is_grn:true,
		},
		callback:async function (r) {
			if (r.message) {
				items.value = JSON.parse(JSON.stringify(r.message));
				items1.value = JSON.parse(JSON.stringify(r.message))
				await get_items_structure()
			}
		},
	});
}

async function get_items_structure(){
	for(let i = 0 ; i < items1.value.length; i++){
		for(let j = 0 ; j < items1.value[i]['items'].length; j++){
			items1.value[i]['items'][j]['types'] = []
			Object.keys(items1.value[i].items[j].values).forEach((key, val)=> {
				items1.value[i].items[j].values[key]['val'] = []
			})
		}
	}
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
				if(items.value[i].items[j].values[k].received == null || items.value[i].items[j].values[k].received == "") {
					items.value[i].items[j].values[k].received = 0;
				}
				if(items.value[i].items[j].values[k].received_quantity == null || items.value[i].items[j].values[k].received_quantity == "") {
					items.value[i].items[j].values[k].received_quantity = 0;
				}
				if (items.value[i].items[j].values[k].secondary_received == null ||items.value[i].items[j].values[k].secondary_received == "") {
					items.value[i].items[j].values[k].secondary_received = 0;
				}
			}
		}
	}
	if(items1.value.length == 0){
		items1.value = JSON.parse(JSON.stringify(items.value))
	}
	return [items.value, items1.value, is_edited.value];
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
