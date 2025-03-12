<template>
	<div>
		<button v-if="docstatus == 0" class="btn btn-success pull-right" @click="fill_quantity()">Fill Quantity</button>
		<table v-if="docstatus !== 0" class="table table-sm table-bordered">
			<tr v-for="(i, item_index) in deliverables_item" :key="item_index">
				<td v-if="i.primary_attribute">
					<table class="table table-sm table-bordered" v-if="i.items && i.items.length > 0">
						<tr>
							<th>S.No.</th>
							<th>Item</th>
							<th>Lot</th>
							<th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
							<th v-for="attr in i.primary_attribute_values" :key="attr"> {{ attr }} </th>
						</tr>
						<tr v-for="(j, item1_index) in i.items" :key="item1_index">
							<td>{{ item1_index + 1 }}</td>
							<td>{{ j.name }}</td>
							<td>{{ j.lot }}</td>
							<td v-for="attr in i.attributes" :key="attr"> 
								{{ j.attributes[attr] }} 
								<span v-if="attr == 'Colour' && j.is_set_item && j.attributes[j.set_attr] != j.major_attr_value && j.attributes[attr]">({{ j.item_keys['major_colour'] }})</span>
								<span v-else-if="attr == 'Colour' && !j.is_set_item && j.attributes[attr] != j.item_keys['major_colour'] && j.attributes[attr]">({{ j.item_keys['major_colour'] }})</span>
							</td>
							<td v-for="attr in j.values" :key="attr">
								<div v-if='attr.delivered_quantity > 0'>
									{{ attr.delivered_quantity}}
									<span v-if="j.default_uom">{{ " " + j.default_uom }}</span>
									<div v-if="attr.secondary_qty > 0 && attr.secondary_uom">
										({{attr.secondary_qty}} {{attr.secondary_uom}})
									</div>
								</div>
								<div v-else> -- </div>
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
							<th>Delivered Quantity</th>
						</tr>
						<tr v-for="(j, item1_index) in i.items" :key="item1_index">
							<td>{{ item1_index + 1 }}</td>
							<td>{{ j.name }}</td>
							<td>{{ j.lot }}</td>
							<td v-for="attr in i.attributes" :key="attr"> {{ j.attributes[attr] }} </td>
							<td>
								<div v-if='j.values["default"].delivered_quantity > 0'>
									{{ j.values["default"].delivered_quantity}}
									<span v-if="j.default_uom">{{ " " + j.default_uom }}</span>
									<div v-if="j.values['default'].secondary_uom && j.values['default'].secondary_qty > 0">
										({{j.values['default'].secondary_qty}} {{j.values['default'].secondary_uom}})
									</div>
								</div>
								<div v-else> -- </div>
							</td>
						</tr>
					</table>
				</td>
			</tr>
		</table>
		<table v-else class="table table-sm table-bordered">
			<tr v-for="(i, item_index) in deliverables_item" :key="item_index">
				<td v-if="i.primary_attribute">
					<input type="checkbox" v-model="indexes[item_index]" @click="get_check_value(item_index)"/>Update Secondary
					<div v-if="uoms[item_index] && indexes[item_index]">
						Secondary UOM: {{uoms[item_index]}}
					</div>
					<table class="table table-sm table-bordered" v-if="i.items && i.items.length > 0">
						<tr>
							<th>S.No.</th>
							<th>Item</th>
							<th>Lot</th>
							<th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
							<th v-for="attr in i.primary_attribute_values" :key="attr"> {{ attr }} </th>
						</tr>
						<tr v-for="(j, item1_index) in i.items" :key="item1_index">
							<td>{{ item1_index + 1 }}</td>
							<td>{{ j.name }}</td>
							<td>{{ j.lot }}</td>
							<td v-for="attr in i.attributes" :key="attr"> 
								{{ j.attributes[attr] }} 
								<span v-if="attr == i.pack_attr && j.attributes[attr] != j.item_keys['major_colour']">({{ j.item_keys['major_colour'] }})</span>
							</td>
							<td v-for="attr in j.values" :key="attr">
								{{ attr.qty}} <span v-if="j.default_uom">{{ " " + j.default_uom }}</span>
								<form>
									<input class="form-control" type="number"
										v-model.number="attr.delivered_quantity" min="0"
										step="0.001" @blur="make_dirty()"/>
								</form>
								<div v-if="indexes[item_index]">
									<input class="form-control pt-2" type="number"
										v-model.number="attr.secondary_qty" min="0"
										step="0.001" @blur="make_dirty()"/>
								</div>
								<div v-else-if="attr.secondary_qty > 0 && attr.secondary_uom">
									({{attr.secondary_qty}} {{attr.secondary_uom}})
								</div>
							</td>
						</tr>
					</table>
				</td>
				<td v-else>
					<input type="checkbox" v-model="indexes[item_index]" @click="get_check_value(item_index)"/>Update Secondary
					<div v-if="uoms[item_index] && indexes[item_index]">
						Secondary UOM: {{uoms[item_index]}}
					</div>
					<table class="table table-sm table-bordered" v-if="i.items && i.items.length > 0">
						<tr>
							<th>S.No.</th>
							<th>Item</th>
							<th>Lot</th>
							<th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
							<th>Pending Quantity</th>
							<th>Quantity</th>
							<th>Secondary Qty</th>
						</tr>
						<tr v-for="(j, item1_index) in i.items" :key="item1_index">
							<td>{{ item1_index + 1 }}</td>
							<td>{{ j.name }}</td>
							<td>{{ j.lot }}</td>
							<td v-for="attr in i.attributes" :key="attr"> {{ j.attributes[attr] }} </td>
							<td>
								{{ j.values["default"].qty}}
								<span v-if="j.default_uom">{{ " " + j.default_uom }}</span>
							</td>
							<td>
								<form>
									<input class="form-control pt-2" type="number"
										v-model.number="j.values['default']['delivered_quantity']"
										min="0" step="0.001" @blur="make_dirty()"/>
								</form>
							</td>
							<td>
								<div v-if="indexes[item_index]">
									<input class="form-control" type="number"
										v-model.number="j.values['default'].secondary_qty" min="0"
										step="0.001" @blur="make_dirty()"/>
								</div>
								<div v-else-if="j.values['default'].secondary_uom && j.values['default'].secondary_qty > 0">
									{{j.values['default'].secondary_qty}} {{j.values['default'].secondary_uom}}
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
import { reactive, ref, onMounted } from 'vue';

const props = defineProps(['items']);
const docstatus = ref(cur_frm.doc.docstatus);
const deliverables_item = reactive([...props.items]);
let indexes = ref([])
let uoms = ref([])

function update_status() {
	docstatus.value = cur_frm.doc.docstatus;
}

onMounted(async()=> {
	for(let i = 0 ; i < deliverables_item.length ; i++){
		indexes.value.push(false)
		uoms.value.push(null)
	}
})

async function get_check_value(index){
	item_name = deliverables_item[index]['items'][0]['name']
	let item_detail = await frappe.db.get_value("Item", item_name, "secondary_unit_of_measure")
	if(item_detail.message.secondary_unit_of_measure){
		uoms.value[index] = item_detail.message.secondary_unit_of_measure
	}
	else{
		frappe.msgprint("No Secondary Unit for this item")
		indexes.value[index] = false
		return
	}
}

function make_dirty(){
	cur_frm.dirty();
}

function fill_quantity(){
	cur_frm.dirty()
	for(let i = 0 ; i < deliverables_item.length ; i++){
		deliverables_item[i]['items'].forEach((row,idx) => {
			Object.keys(row['values']).forEach(key => {
				deliverables_item[i]['items'][idx]['values'][key]['delivered_quantity'] = row['values'][key]['qty']
			})
		})
	}
}
function get_items(){
	for(let i = 0 ; i < deliverables_item.length ; i++){
		for(let j = 0 ; j < deliverables_item[i].items.length ; j++){
			Object.keys(deliverables_item[i].items[j].values).forEach(key => {
				if(deliverables_item[i].items[j].values[key].delivered_quantity == "" || deliverables_item[i].items[j].values[key].delivered_quantity == null){
					deliverables_item[i].items[j].values[key].delivered_quantity = 0
				}
				if(uoms.value[i]){
					deliverables_item[i].items[j].values[key]['secondary_uom'] = uoms.value[i]
				}
			})
		}
	}
	return deliverables_item
}

defineExpose({
	deliverables_item,
	get_items,
	update_status,
})

</script>
<style scoped>
.table-container {
	padding: 16px;
}
.styled-table {
	width: 100%;
	border-collapse: collapse;
	border: 1px solid #ccc;
}
.styled-table th,
.styled-table td {
	padding: 8px;
	border: 1px solid #ccc;
}
.styled-table thead tr {
	background-color: #696969;
	color: #fff;
}
.styled-table tbody tr:hover {
	background-color: #f5f5f5;
}
.editable-input {
		width: 100%;
		padding: 4px;
		border: 1px solid #ccc;
		border-radius: 4px;
		box-sizing: border-box;
}
</style>
	