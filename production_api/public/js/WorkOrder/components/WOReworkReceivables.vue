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
                            <th>Total Cost</th>
                            <th>Edit</th>
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
                                <div>{{attr.qty}} <span v-if="j.default_uom">{{ j.default_uom}}</span></div>
                                <div>Pending Qty: <span>{{attr.pending_qty}}</span> </div>
                                Cost: {{attr.cost}}
                            </td>
                            <td>{{j.total_cost}}</td>
                            <td>
                                <div v-if="indexes[item_index][item1_index]">
                                    <input type="number" class="form-control" @blur="get_input($event)"/>
                                </div>
                                <div v-else>
                                    <div class="pull-right cursor-pointer" @click="edit_item(item_index, item1_index)"
                                        v-html="frappe.utils.icon('edit', 'md', 'mr-1')"></div>
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
import { ref } from 'vue';

const items = ref(null);
let indexes = ref([])
let edit_index1 = -1
let edit_index2 = -1

function make_dirty(){
	cur_frm.dirty();
}
function get_items(){
	return items.value
}
function get_input(event){
    let value = parseInt(event.target.value)
    let total = 0
    indexes.value[edit_index1][edit_index2] = false
    Object.keys(items.value[edit_index1].items[edit_index2].values).forEach(key => {
        total = total + value
        items.value[edit_index1].items[edit_index2].values[key].cost = value
    })
    items.value[edit_index1].items[edit_index2].total_cost = total
    edit_index1 = -1
    edit_index2 = -1
    make_dirty()
}
function edit_item(item_index, item1_index){
    edit_index1 = item_index
    edit_index2 = item1_index
    indexes.value[item_index][item1_index] = true
}

function load_data(item){
	items.value = item
    for(let i = 0 ; i < items.value.length ; i++){
        indexes.value.push([])
        for(let j = 0 ; j < items.value[i].items.length ; j++){
            let total = 0
            indexes.value[i].push(false)
            Object.keys(items.value[i].items[j].values).forEach(key => {
                total = total + items.value[i].items[j].values[key].cost
            })
            items.value[i].items[j].total_cost = total
        }
    }
}

defineExpose({
	get_items,
	load_data
})

</script>
	