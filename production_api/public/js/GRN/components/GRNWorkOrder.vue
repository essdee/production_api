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
							<th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
							<th v-for="attr in i.primary_attribute_values" :key="attr">{{ attr }}</th>
							<th v-if="docstatus == 0">Edit</th>
						</tr>
						<tr v-for="(j, item1_index) in i.items" :key="item1_index">
							<td>{{ item1_index + 1 }}</td>
							<td>{{ j.name }}</td>
							<td v-for="attr in i.attributes" :key="attr">
								{{ j.attributes[attr] }}
								<span v-if="attr == 'Colour' && j.is_set_item && j.attributes[j.set_attr] != j.major_attr_value && j.attributes[attr]">({{ j.item_keys['major_colour'] }})</span>
								<span v-else-if="attr == 'Colour' && !j.is_set_item && j.attributes[attr] != j.item_keys['major_colour'] && j.attributes[attr]">({{ j.item_keys['major_colour'] }})</span>
							</td>
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
							<th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
							<th>Pending Quantity</th>
							<th v-if="docstatus == 0">Edit</th>
						</tr>
						<tr v-for="(j, item1_index) in i.items" :key="item1_index">
							<td>{{ item1_index + 1 }}</td>
							<td>{{ j.name }}</td>
							<td v-for="attr in i.attributes" :key="attr"> 
								{{ j.attributes[attr] }} 
							</td>
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
			<div class="row">
				<div ref="secondaryUomHtml" class="secondary-uom-html col-md-5"></div>
			</div>
			<div>
				<div ref="secondaryQtyHtml" class="secondary_qty row pl-4" style="display: flex; gap: 10px"></div>
			</div>
			<div v-if="show_button" style="display: flex; gap: 10px">
				<button class="btn btn-success" @click="add_item()">Add Item</button>
				<button class="btn btn-success" @click="make_clean()">Close</button>
			</div>
		</div>
		<p>Delivered Items</p>
		<table class="table table-sm table-bordered" v-if="check_received_qty">
			<tr v-for="(i, item_index) in items" :key="item_index">
				<td v-if="i.primary_attribute">
					<div v-if="edit_item_uom">Secondary UOM : {{edit_item_uom}}</div>
					<table class="table table-sm table-bordered" v-if="i.items && i.items.length > 0" >
						<tr>
							<th>S.No</th>
							<th>Item</th>
							<th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
							<th>Type</th>
							<th v-for="attr in i.primary_attribute_values" :key="attr">{{ attr }}</th>
							<th v-if="docstatus == 0">Edit</th>
						</tr>
						<template v-for="(j, item1_index) in i.items" :key="item1_index">
							<tr v-for="(type, idx) in j.types" :key="idx">
								<td>{{ get_index(item1_index)}}</td>
								<td>{{ j.name }}</td>
								<td v-for="attr in i.attributes" :key="attr">
									{{ j.attributes[attr] }}
									<span v-if="attr == 'Colour' && j.is_set_item && j.attributes[j.set_attr] != j.major_attr_value && j.attributes[attr]">({{ j.item_keys['major_colour'] }})</span>
									<span v-else-if="attr == 'Colour' && !j.is_set_item && j.attributes[attr] != j.item_keys['major_colour'] && j.attributes[attr]">({{ j.item_keys['major_colour'] }})</span>
								</td>
								<td>{{ type }}</td>
								<td v-for="attr in j.values" :key="attr">
									<div v-if="attr.types">
										<div v-for="t in typeof(attr.types) == 'string' ? Object.keys(JSON.parse(attr.types)) : Object.keys(attr.types)" :key='t'>
											<div v-if="edit_index == item_index && edit_index1 == item1_index && edit_type == t && t == type">
												<div v-if="typeof(attr.types) == 'string'">
													<input class="form-control" type="number" :value="JSON.parse(attr.types)[t]" @input="get_input($event.target.value,item_index, item1_index, type, attr.primary_attr)">
												</div>
												<div v-else>
													<input class="form-control" type="number" :value="attr.types[t]" @input="get_input($event.target.value,item_index, item1_index, type, attr.primary_attr)">
												</div>
												<div v-if="edit_item_uom">
													<div v-if="typeof(attr.secondary_qty_json) == 'string'">
														<input class="form-control" type="number" :value="JSON.parse(attr.secondary_qty_json)[t]" @input="get_secondary_input($event.target.value,item_index, item1_index, type, attr.primary_attr)">
													</div>
													<div v-else>
														<input class="form-control" type="number" :value="attr.secondary_qty_json[t]" @input="get_secondary_input($event.target.value,item_index, item1_index, type, attr.primary_attr)">
													</div>
												</div>
											</div>
											<div v-else>
												<div v-if="t == type">
													<div v-if='typeof(attr.types) == "string"'>
														{{JSON.parse(attr.types)[t]}}<div></div>
														<span v-if="typeof(attr.secondary_qty_json) == 'string'">
															<span v-if="JSON.parse(attr.secondary_qty_json)[t] > 0 && attr.secondary_uom">
																({{JSON.parse(attr.secondary_qty_json)[t]}} {{attr.secondary_uom}})											
															</span>
														</span>	
														<span v-else>
															<span v-if="attr.secondary_qty_json[t] > 0 && attr.secondary_uom">
																({{attr.secondary_qty_json[t]}} {{attr.secondary_uom}})											
															</span>
														</span>
													</div>
													<div v-else>
														{{attr.types[t]}}<div></div>
														<span v-if="attr.secondary_qty_json[t] > 0 && attr.secondary_uom">
															({{attr.secondary_qty_json[t]}} {{attr.secondary_uom}})											
														</span>
													</div>	
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
							<th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
							<th>Quantity</th>
							<th v-if="docstatus == 0">Edit</th>
						</tr>
						<tr v-for="(j, item1_index) in i.items" :key="item1_index">
							<td>{{ j.name }}</td>
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
let loop_index = 0
let i = 0;
const is_edited = ref(false);
const docstatus = ref(0);
const items = ref([]);
const supplier = ref(null);
const against = ref(null);
const against_id = ref(null);
let _skip_watch = false;
const attribute_values = ref([]);
const secondaryUomHtml = ref(null);
const secondaryQtyHtml = ref(null);
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
let secondary_uom = null
const controlRefsSecondary = ref({
  	quantities: [],
});

let received_type = null;
const show_button = ref(false);
const show_button2 = ref(false);
let types = null;
let qty_parameters = [];
let secondary_qty_parameters = [];
let indexes = [];
let edit_type = ref(null)
let edit_item_uom = ref(null)
let delivered_edited = ref(false)

function get_input(value, idx1, idx2, type, attr){
	if(value.length == 0){
		value = 0
	}
	else{
		value = parseFloat(value)
	}
	cur_frm.dirty()
	is_edited.value = true
	let x = items.value[idx1]['items'][idx2]['values'][attr]['types']
	if(typeof(x) == 'string'){
		x = JSON.parse(x)	
	}
	let type_qty = parseFloat(x[type])
	x[type] = value
	items.value[idx1]['items'][idx2]['values'][attr]['types'] = JSON.stringify(x)
	items.value[idx1].items[idx2].values[attr]['received'] -= parseFloat(type_qty)
	items.value[idx1].items[idx2].values[attr]['qty'] += parseFloat(type_qty)
	items.value[idx1].items[idx2].values[attr]['received'] += parseFloat(value)
	items.value[idx1].items[idx2].values[attr]['qty'] -= parseFloat(value)
}

function get_secondary_input(value, idx1, idx2, type, attr){
	if(value.length == 0){
		value = 0
	}
	else{
		value = parseFloat(value)
	}
	cur_frm.dirty()
	is_edited.value = true
	let secondary_json = items.value[idx1]['items'][idx2]['values'][attr]['secondary_qty_json']
	if(typeof(secondary_json) == "string"){
		secondary_json = JSON.parse(secondary_json)
	}
	secondary_json[type] = value
	items.value[idx1]['items'][idx2]['values'][attr]['secondary_qty_json'] = JSON.stringify(secondary_json)
	items.value[idx1]['items'][idx2]['values'][attr]['secondary_uom'] = edit_item_uom.value
}

function get_index(idx){
	if(idx == 0 && loop_index != 1){
		loop_index = 0
	}
	loop_index = loop_index + 1;
	return loop_index
}
const check_received_qty = computed(()=> {
	let x = false
	if(items.value){
		a: for (let i = 0; i < items.value.length; i++) {
			for (let idx = 0; idx < items.value[i]['items'].length; idx++) {
				const row = items.value[i]['items'][idx];
				for (const key of Object.keys(row.values)) {
					if (row.values[key]['received'] > 0) {
						x = true;
						break a;
					}
				}
			}
		}
	}
	return x
})

async function edit_item(index, index1) {
	make_clean()
	let el = root.value;
	controlRefs.value.quantities = [];
	controlRefsSecondary.value.quantities = [];
	edit_index.value = index;
	edit_index1.value = index1;
	attribute_values.value = [];
	qty_attributes.value = [];
	cur_item.value = null;
	cur_lot.value = null;
	show_button.value = true;
	let suom = await frappe.db.get_value("Item",items.value[index]['items'][0]['name'],"secondary_unit_of_measure")
	edit_item_uom.value = suom.message.secondary_unit_of_measure
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

async function edit_delivered_item(index, index1, type) {
	make_clean()
	edit_type.value = type
	edit_index.value = index
	edit_index1.value = index1
	let suom =await frappe.db.get_value("Item",items.value[index]['items'][0]['name'],"secondary_unit_of_measure")
	edit_item_uom.value = suom.message.secondary_unit_of_measure
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
			let qty = parseFloat(received_types[type])
			delete received_types[type]
			items.value[edit_index.value].items[edit_index1.value].values[row]['types'] = received_types
			items.value[edit_index.value].items[edit_index1.value].values[row]['received'] -= qty
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
		items.value[edit_index.value].items[edit_index1.value].values['default']['received'] -= qty
		items.value[edit_index.value].items[edit_index1.value].values['default']['qty'] += qty
	}
}

function create_attributes( attributes, quantities, item, lot, idx, idx1) {
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
	let default_uom = items.value[edit_index.value]['items'][edit_index1.value]['default_uom']
	let df = {
		fieldtype: "Link",
		fieldname: "types",
		label: "Type",
		options: "GRN Item Type",
		onchange: () => {
			const selectedValue = types.get_value();
			if (selectedValue && selectedValue !== "" && selectedValue !== null) {
				get_secondary(edit_item_uom.value)
				handleQtyParameters(quantities, selectedValue, default_uom);
			} 
			else {
				$(el).find(".qty-parameters").html("");
			}
		},
		reqd: true,
	};
	types = frappe.ui.form.make_control({
		parent: $(el).find(".type-parameters"),
		df: df,
		doc: sample_doc.value,
		render_input: true,
	});
}

function handleQtyParameters(quantities, value, default_uom) {
	controlRefs.value.quantities = [];
	controlRefsSecondary.value.quantities = [];
	let el = root.value;
	$(el).find(".qty-parameters").html("");
	$(secondaryQtyHtml.value).html("")
	qty_parameters = [];
	secondary_qty_parameter = [];
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
			qty_parameters[idx].refresh();
			controlRefs.value.quantities.push(qty_parameters[idx]);
			if(edit_item_uom.value){
				secondary_qty_parameters[idx] = frappe.ui.form.make_control({
					parent: secondaryQtyHtml.value,
					df: {
						fieldtype: "Float",
						fieldname: key + "_" + default_uom,
						label: key + "-" + row[x] +" "+ default_uom,
					},
					doc: sample_doc.value,
					render_input: true,
				});
				controlRefsSecondary.value.quantities.push(secondary_qty_parameters[idx]);
			}
		});
	});
}

function get_secondary(uom) {
	$(secondaryUomHtml.value).html("");
	if(uom){
		secondary_uom = frappe.ui.form.make_control({
			parent: secondaryUomHtml.value,
			df: {
				"fieldname": "secondary_uom",
				"fieldtype": "Data",
				"label": "Secondary UOM",
				"read_only": true,
			},
			doc: sample_doc.value,
			render_input: true
		});
		secondary_uom.set_value(uom);
		secondary_uom.refresh();
	}
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
			items.value[edit_index.value].items[edit_index1.value].values[row]['received'] += data[x]
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
			items.value[edit_index.value].items[edit_index1.value].values[row]['qty'] -= data[x]
			items.value[edit_index.value].items[edit_index1.value].values[row]['types'] = dict
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
		items.value[edit_index.value].items[edit_index1.value].values['default']['received'] += data[x]
		items.value[edit_index.value].items[edit_index1.value].values['default']['qty'] -= data[x]
	}
	types.set_value(null)
	let uom = edit_item_uom.value
	if(uom){
		let data1 = getControlValues(controlRefsSecondary.value.quantities);
		x = 0;
		controlRefsSecondary.value.quantities = [];
		
		if(primary){
			Object.keys(items.value[edit_index.value].items[edit_index1.value].values).forEach(row => {
				let dict = items.value[edit_index.value].items[edit_index1.value].values[row]['secondary_qty_json']
				if(!dict){
					dict = {}
				}
				if(typeof(dict) == 'string'){
					dict = JSON.parse(dict)
				}
				dict[type_selected] = data1[x]
				items.value[edit_index.value].items[edit_index1.value].values[row]['secondary_uom'] = uom
				items.value[edit_index.value].items[edit_index1.value].values[row]['secondary_qty_json'] = dict
				x = x + 1
			})
		}
		else{
			let dict = items.value[edit_index.value].items[edit_index1.value].values['default']['secondary_qty_json']
			if(!dict){
				dict = {}
			}
			if(typeof(dict) == 'string'){
				dict = JSON.parse(dict)
			}
			dict[type_selected] = data1[x]
			items.value[edit_index.value].items[edit_index1.value]['default']['secondary_qty'] = data1[x]
			items.value[edit_index.value].items[edit_index1.value]['default']['secondary_uom'] = uom
			items.value[edit_index.value].items[edit_index1.value].values['default']['secondary_qty_json'] = dict
			x = x + 1
		}
	}
  make_clean();
}

function make_clean() {
	let el = root.value;
	$(secondaryQtyHtml.value).html("")
	$(secondaryUomHtml.value).html("")
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
	edit_item_uom.value = null
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
				let x = JSON.stringify(r.message)
				if(typeof(x) == 'string'){
					x = JSON.parse(x)
				}
				items.value = x;
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
				if ( items.value[i].items[j].values[k].received == null || items.value[i].items[j].values[k].received == "" ) {
					items.value[i].items[j].values[k].received = 0;
				}
			}
		}
	}
	return [items.value, is_edited.value];
}

watch( items, (newVal, oldVal) => {
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
