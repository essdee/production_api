<template>
	<div>
		<table class="table table-sm table-bordered">
			<tr v-for="(i, item_index) in items" :key="item_index">
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
								<span v-if="attr == i.pack_attr && j.attributes[attr] != j.item_keys['major_colour']">({{ j.item_keys['major_colour'] }})</span>
							</td>
							<td v-for="attr in j.values" :key="attr">
								{{ attr.delivered_quantity}} <span v-if="j.default_uom">{{ " " + j.default_uom }}</span>
								<form>
									<input class="form-control" type="number"
										v-model.number="attr.return_quantity" min="0"
										step="0.001"/>
								</form>
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
							<th>Quantity</th>
						</tr>
						<tr v-for="(j, item1_index) in i.items" :key="item1_index">
							<td>{{ item1_index + 1 }}</td>
							<td>{{ j.name }}</td>
							<td>{{ j.lot }}</td>
							<td v-for="attr in i.attributes" :key="attr"> {{ j.attributes[attr] }} </td>
							<td>
								{{ j.values["default"].delivered_quantity}}
								<span v-if="j.default_uom">{{ " " + j.default_uom }}</span>
							</td>
							<td>
								<form>
									<input class="form-control pt-2" type="number"
										v-model.number="j.values['default']['return_quantity']"
										min="0" step="0.001"/>
								</form>
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

let items = ref([]);
function load_data(data){
    items.value = data
}

function get_items(){
	for(let i = 0 ; i < items.value.length ; i++){
		for(let j = 0 ; j < items.value[i].items.length ; j++){
			Object.keys(items.value[i].items[j].values).forEach(key => {
				if(items.value[i].items[j].values[key].delivered_quantity == "" || items.value[i].items[j].values[key].delivered_quantity == null){
					items.value[i].items[j].values[key].delivered_quantity = 0
				}
			})
		}
	}
	return items.value
}

defineExpose({
	load_data,
	get_items,
})

</script>
	