<template>
	<div>
		<button v-if="docstatus == 0" class="btn btn-success pull-right" @click="fill_quantity()">Fill Quantity</button>
		<div v-if="!is_rework && deliverables_item">
			<table class="table table-sm table-bordered">
				<tr v-for="(i, item_index) in deliverables_item" :key="item_index">
					<td v-if="i.primary_attribute">
						<div v-if="docstatus == 0">
							<input type="checkbox" v-model="indexes[item_index]" @click="get_check_value(item_index, null)"/>Update Secondary
							<div v-if="uoms[item_index] && indexes[item_index]">
								Secondary UOM: {{uoms[item_index]}}
							</div>
						</div>	
						<table class="table table-sm table-bordered" v-if="i.items && i.items.length > 0">
							<tr>
								<th>S.No.</th>
								<th>Item</th>
								<th>Lot</th>
								<th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
								<th v-for="attr in i.primary_attribute_values" :key="attr"> {{ attr }} </th>
								<th>Total Qty</th>
								<th>Comments</th>
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
									<div v-if="docstatus == 0">
										{{ attr.qty}} <span v-if="j.default_uom">{{ " " + j.default_uom }}</span>
										<form>
											<input class="form-control" type="number" v-model.number="attr.delivered_quantity" 
												min="0" step="0.001" @blur="make_dirty()"/>
										</form>
										<div v-if="indexes[item_index]">
											<input class="form-control pt-2" type="number" v-model.number="attr.secondary_qty" 
												min="0" step="0.001" @blur="make_dirty()"/>
										</div>
										<div v-else-if="attr.secondary_qty > 0 && attr.secondary_uom">
											({{attr.secondary_qty}} {{attr.secondary_uom}})
										</div>
									</div>
									<div v-else>
										<div v-if='attr.delivered_quantity > 0'>
											{{ attr.delivered_quantity}} <span v-if="j.default_uom">{{ " " + j.default_uom }}</span>
											<div v-if="attr.secondary_qty > 0 && attr.secondary_uom">
												({{attr.secondary_qty}} {{attr.secondary_uom}})
											</div>
										</div>
										<div v-else> -- </div>
									</div>
								</td>
								<td><strong>{{j.sum_qty}} <span v-if="j.default_uom">{{ " " + j.default_uom }}</span></strong></td>
								<td>
									<div v-if="docstatus == 0">
										<input type="text" v-model="j.comments" class="form-control" @blur="make_dirty()"/>
									</div>
									<div v-else>
										{{j.comments}}
									</div>
								</td>
							</tr>
						</table>
					</td>
					<td v-else>
						<div v-if="docstatus == 0">
							<input type="checkbox" v-model="indexes[item_index]" @click="get_check_value(item_index, null)"/>Update Secondary
							<div v-if="uoms[item_index] && indexes[item_index]">
								Secondary UOM: {{uoms[item_index]}}
							</div>
						</div>	
						<table class="table table-sm table-bordered" v-if="i.items && i.items.length > 0">
							<tr>
								<th>S.No.</th>
								<th>Item</th>
								<th>Lot</th>
								<th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
								<th v-if="docstatus == 0">Pending Quantity</th>
								<th v-if="docstatus == 0">Quantity</th>
								<th v-if="docstatus == 0">Secondary Qty</th>
								<th v-if="docstatus == 1">Delivered Quantity</th>
								<th>Comments</th>
							</tr>
							<tr v-for="(j, item1_index) in i.items" :key="item1_index">
								<td>{{ item1_index + 1 }}</td>
								<td>{{ j.name }}</td>
								<td>{{ j.lot }}</td>
								<td v-for="attr in i.attributes" :key="attr"> {{ j.attributes[attr] }} </td>
								<td v-if="docstatus == 0">
									{{ j.values["default"].qty}} <span v-if="j.default_uom">{{ " " + j.default_uom }}</span>
								</td>
								<td v-if="docstatus == 0">
									<input class="form-control pt-2" type="number" v-model.number="j.values['default']['delivered_quantity']"
										min="0" step="0.001" @blur="make_dirty()"/>
								</td>
								<td v-if="docstatus == 0">
									<div v-if="indexes[item_index]">
										<input class="form-control" type="number" v-model.number="j.values['default'].secondary_qty" 
											min="0" step="0.001" @blur="make_dirty()"/>
									</div>
									<div v-else-if="j.values['default'].secondary_uom && j.values['default'].secondary_qty > 0">
										{{j.values['default'].secondary_qty}} {{j.values['default'].secondary_uom}}
									</div>
								</td>
								<td v-if="docstatus == 1">
									<div v-if='j.values["default"].delivered_quantity > 0'>
										{{ j.values["default"].delivered_quantity}}
										<span v-if="j.default_uom">{{ " " + j.default_uom }}</span>
										<div v-if="j.values['default'].secondary_uom && j.values['default'].secondary_qty > 0">
											({{j.values['default'].secondary_qty}} {{j.values['default'].secondary_uom}})
										</div>
									</div>
									<div v-else> -- </div>
								</td>
								<td>
									<div v-if="docstatus == 0">
										<input type="text" v-model="j.values['default'].comments" class="form-control" @blur="make_dirty()"/>
									</div>
									<div>
										{{j.values['default'].comments}}
									</div>
								</td>
							</tr>
						</table>
					</td>
				</tr>
			</table>
		</div>	
		<div v-else-if="deliverables_item">
			<div v-for="received_type in Object.keys(deliverables_item)" :key="received_type">
				<h3>{{received_type}}</h3>
				<table class="table table-sm table-bordered">
					<tr v-for="(i, item_index) in deliverables_item[received_type]" :key="item_index">
						<td v-if="i.primary_attribute">
							<div v-if="docstatus == 0">
								<input type="checkbox" v-model="indexes[received_type][item_index]" @click="get_check_value(item_index, received_type)"/>Update Secondary
								<div v-if="uoms[received_type][item_index] && indexes[received_type][item_index]">
									Secondary UOM: {{uoms[received_type][item_index]}}
								</div>
							</div>	
							<table class="table table-sm table-bordered" v-if="i.items && i.items.length > 0">
								<tr>
									<th>S.No.</th>
									<th>Item</th>
									<th>Lot</th>
									<th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
									<th v-for="attr in i.primary_attribute_values" :key="attr"> {{ attr }} </th>
									<th>Comments</th>
								</tr>
								<tr v-for="(j, item1_index) in i.items" :key="item1_index">
									<td>{{ item1_index + 1 }}</td>
									<td>{{ j.name }}</td>
									<td>{{ j.lot }}</td>
									<td v-for="attr in i.attributes" :key="attr"> {{ j.attributes[attr] }} </td>
									<td v-for="attr in j.values" :key="attr">
										<div v-if="docstatus == 0">
											{{ attr.qty}} <span v-if="j.default_uom">{{ " " + j.default_uom }}</span>
											<input class="form-control" type="number" v-model.number="attr.delivered_quantity" 
												min="0" step="0.001" @blur="make_dirty()"/>
											<div v-if="indexes[received_type][item_index]">
												<input class="form-control pt-2" type="number" v-model.number="attr.secondary_qty" 
													min="0" step="0.001" @blur="make_dirty()"/>
											</div>
											<div v-else-if="attr.secondary_qty > 0 && attr.secondary_uom">
												({{attr.secondary_qty}} {{attr.secondary_uom}})
											</div>
										</div>
										<div v-else>
											<div v-if='attr.delivered_quantity > 0'>
												{{ attr.delivered_quantity}}
												<span v-if="j.default_uom">{{ " " + j.default_uom }}</span>
												<div v-if="attr.secondary_qty > 0 && attr.secondary_uom">
													({{attr.secondary_qty}} {{attr.secondary_uom}})
												</div>
											</div>
											<div v-else> -- </div>
										</div>
									</td>
									<td>
										<div v-if="docstatus == 0">
											<input type="text" v-model="j.comments" class="form-control" @blur="make_dirty()"/>
										</div>
										<div v-else>
											{{j.comments}}
										</div>
									</td>
								</tr>
							</table>
						</td>
					</tr>
				</table>
			</div>
		</div>
	</div>	
</template>
	
<script setup>
import { ref } from 'vue';

const docstatus = ref(cur_frm.doc.docstatus);
const deliverables_item = ref(null);
let indexes = ref(null)
let uoms = ref(null)
let is_rework = cur_frm.doc.is_rework

function update_status() {
	docstatus.value = cur_frm.doc.docstatus;
}

async function get_check_value(index, received_type){
	if(!received_type){
		item_name = deliverables_item.value[index]['items'][0]['name']
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
	else{
		item_name = deliverables_item.value[received_type][index]['items'][0]['name']
		let item_detail = await frappe.db.get_value("Item", item_name, "secondary_unit_of_measure")
		if(item_detail.message.secondary_unit_of_measure){
			uoms.value[received_type][index] = item_detail.message.secondary_unit_of_measure
		}
		else{
			frappe.msgprint("No Secondary Unit for this item")
			indexes.value[received_type][index] = false
			return
		}
	}
}

function make_dirty(){
	cur_frm.dirty();
}

function fill_quantity(){
	cur_frm.dirty()
	if(is_rework){
		Object.keys(deliverables_item.value).forEach((received_type)=> {
			for(let i = 0 ; i < deliverables_item.value[received_type].length ; i++){
				deliverables_item.value[received_type][i]['items'].forEach((row,idx) => {
					Object.keys(row['values']).forEach(key => {
						deliverables_item.value[received_type][i]['items'][idx]['values'][key]['delivered_quantity'] = row['values'][key]['qty']
					})
				})
			}
		})
	}
	else{
		for(let i = 0 ; i < deliverables_item.value.length ; i++){
			deliverables_item.value[i]['items'].forEach((row,idx) => {
				Object.keys(row['values']).forEach(key => {
					deliverables_item.value[i]['items'][idx]['values'][key]['delivered_quantity'] = row['values'][key]['qty']
				})
			})
		}
	}
	
}
function get_items(){
	if(is_rework){
		Object.keys(deliverables_item.value).forEach((received_type)=> {
			for(let i = 0 ; i < deliverables_item.value[received_type].length ; i++){
				for(let j = 0 ; j < deliverables_item.value[received_type][i].items.length ; j++){
					Object.keys(deliverables_item.value[received_type][i].items[j].values).forEach(key => {
						if(deliverables_item.value[received_type][i].items[j].values[key].delivered_quantity == "" || deliverables_item.value[received_type][i].items[j].values[key].delivered_quantity == null){
							deliverables_item.value[received_type][i].items[j].values[key].delivered_quantity = 0
						}
						if(uoms.value[received_type][i]){
							deliverables_item.value[received_type][i].items[j].values[key]['secondary_uom'] = uoms.value[received_type][i]
						}
					})
				}
			}	
		})
	}
	else{
		for(let i = 0 ; i < deliverables_item.value.length ; i++){
			for(let j = 0 ; j < deliverables_item.value[i].items.length ; j++){
				Object.keys(deliverables_item.value[i].items[j].values).forEach(key => {
					if(deliverables_item.value[i].items[j].values[key].delivered_quantity == "" || deliverables_item.value[i].items[j].values[key].delivered_quantity == null){
						deliverables_item.value[i].items[j].values[key].delivered_quantity = 0
					}
					if(uoms.value[i]){
						deliverables_item.value[i].items[j].values[key]['secondary_uom'] = uoms.value[i]
					}
				})
			}
		}
	}
	return deliverables_item.value
}

function load_data(item){
	deliverables_item.value = item
	if(!is_rework){
		indexes.value = []
		uoms.value = []
		for(let i = 0 ; i < deliverables_item.value.length ; i++){
			indexes.value.push(false)
			uoms.value.push(null)
			for(let j = 0 ; j < deliverables_item.value[i].items.length ; j++){
				let total = 0
				Object.keys(deliverables_item.value[i].items[j].values).forEach(key => {
					if(deliverables_item.value[i].items[j].values[key].delivered_quantity > 0){
						total += deliverables_item.value[i].items[j].values[key].delivered_quantity
					}
				})
				deliverables_item.value[i].items[j]['sum_qty'] = total
			}
		}
	}
	else{
		indexes.value = {}
		uoms.value = {}
		Object.keys(deliverables_item.value).forEach((received_type)=> {
			indexes.value[received_type] = []
			uoms.value[received_type] = []
			for(let i = 0 ; i < deliverables_item.value[received_type].length ; i++){
				indexes.value[received_type].push(false)
				uoms.value[received_type].push(null)
			}	
		})
	}
}

defineExpose({
	deliverables_item,
	get_items,
	update_status,
	load_data
})

</script>
	