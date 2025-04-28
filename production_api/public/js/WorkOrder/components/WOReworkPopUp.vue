<template>
	<div>
        <div v-for="received_type in Object.keys(items)" :key="received_type">
            <table class="table table-sm table-bordered">
                <template v-for="(i, item_index) in items[received_type]" :key="item_index">
                    <tr>
                        <td>
                            <h3>
                                {{ received_type }} 
                                <input type="checkbox" @input="update_group($event.target.checked, item_index, received_type)"/>
                            </h3>
                        </td>
                    </tr>
                    <tr>
                        <td v-if="i.primary_attribute">
                            <table class="table table-sm table-bordered" v-if="i.items && i.items.length > 0">
                                <tr>
                                    <th>S.No</th>
                                    <th>Item</th>
                                    <th>Lot</th>
                                    <th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
                                    <th v-for="attr in i.primary_attribute_values" :key="attr"> {{ attr }} </th>
                                </tr>
                                <tr v-for="(j, item1_index) in i.items" :key="item1_index">
                                    <td>
                                        <div style="display:flex;">
                                            <div>
                                                {{ item1_index + 1 }}
                                            </div>
                                            <div>
                                                <input type="checkbox" v-model="indexes[received_type][item_index][item1_index]" 
                                                    @input="update_row($event.target.checked, item_index, item1_index, received_type)" 
                                                    style="margin-top:3px;margin-left:3px;"/>
                                            </div>
                                        </div>
                                    </td>
                                    <td>{{ j.name }}</td>
                                    <td>{{ j.lot }}</td>
                                    <td v-for="attr in i.attributes" :key="attr"> 
                                        {{ j.attributes[attr] }} 
                                        <span v-if="attr == i.pack_attr && j.attributes[attr] != j.item_keys['major_colour']">({{ j.item_keys['major_colour'] }})</span>
                                    </td>
                                    <td v-for="attr in j.values" :key="attr">
                                        {{ attr.qty}} <span v-if="j.default_uom">{{ " " + j.default_uom }}</span>
                                        <form>
                                            <input class="form-control" type="number" v-model.number="attr.rework_quantity" min="0" step="0.001"/>
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
                                    <th>Quantity</th>
                                    <th>Rework Quantity</th>
                                </tr>
                                <tr v-for="(j, item1_index) in i.items" :key="item1_index">
                                    <td>{{ item1_index + 1 }}</td>
                                    <td>{{ j.name }}</td>
                                    <td>{{ j.lot }}</td>
                                    <td v-for="attr in i.attributes" :key="attr"> {{ j.attributes[attr] }} </td>
                                    <td>
                                        {{ j.values["default"].qty}} <span v-if="j.default_uom">{{ " " + j.default_uom }}</span>
                                    </td>
                                    <td>
                                        <form>
                                            <input class="form-control pt-2" type="number"
                                                v-model.number="j.values['default']['rework_quantity']"
                                                min="0" step="0.001"/>
                                        </form>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </template>    
            </table>
        </div>    
	</div>	
</template>
	
<script setup>
import { reactive, ref, onMounted } from 'vue';

let items = ref({})

let indexes = {}
function get_items(){
    Object.keys(items.value).forEach((received_type) => {
        for(let i = 0 ; i < items.value[received_type].length ; i++){
            for(let j = 0 ; j < items.value[received_type][i].items.length ; j++){
                Object.keys(items.value[received_type][i].items[j].values).forEach(key => {
                    if(items.value[received_type][i].items[j].values[key].rework_quantity == "" || items.value[received_type][i].items[j].values[key].rework_quantity == null){
                        items.value[received_type][i].items[j].values[key].rework_quantity = 0
                    }
                    if(items.value[received_type][i].items[j].values[key].rework_quantity > items.value[received_type][i].items[j].values[key].qty){
                        frappe.throw(`Rework quantity was higher than required`)
                    }
                })
            }
        }
    })
	return items.value
}

function load_data(item){
    items.value = item
    Object.keys(items.value).forEach((key) => {
        indexes[key] = []
        for(let i = 0 ; i < items.value[key].length ; i++){
            indexes[key].push([])
            for(let j = 0 ; j < items.value[key][i].items.length ; j++){
                indexes[key][i].push(false)
            }
        }
    })
}

function update_row(val, index1, index2, received_type){
    Object.keys(items.value[received_type][index1].items[index2].values).forEach(key => {
        if(val){
            items.value[received_type][index1].items[index2].values[key].rework_quantity = items.value[received_type][index1].items[index2].values[key].qty
        }
        else{
            items.value[received_type][index1].items[index2].values[key].rework_quantity = 0
        }
    })
    indexes[received_type][index1][index2] = val
}

function update_group(val, index, received_type){
    for(let i = 0 ; i < items.value[received_type][index].items.length ; i++){
        Object.keys(items.value[received_type][index].items[i].values).forEach(key => {
            if(val){
                items.value[received_type][index].items[i].values[key].rework_quantity = items.value[received_type][index].items[i].values[key].qty
            }
            else{
                items.value[received_type][index].items[i].values[key].rework_quantity = 0
            }
        })
        indexes[received_type][index][i] = val
    }
}

defineExpose({
    load_data,
    get_items,
})

</script>
	