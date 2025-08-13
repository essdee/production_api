<template>
	<div ref="root">
		<table class="table table-sm table-bordered">
            <div class="received-type col-md-4"></div>
			<template v-for="(i, item_index) in items" :key="item_index">
                <tr>
                    <input type="checkbox" @input="update_group($event.target.checked, item_index)"/> Select All Items
				</tr>
                <tr>
                    <td v-if="i.primary_attribute">
                        <table class="table table-sm table-bordered" v-if="i.items && i.items.length > 0">
                            <tr>
                                <th>S.No.</th>
                                <th>Item</th>
                                <th>Lot</th>
                                <th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
                                <th v-if="is_rework">Item Type</th>
                                <th v-for="attr in i.primary_attribute_values" :key="attr"> {{ attr }} </th>
                            </tr>
                            <tr v-for="(j, item1_index) in i.items" :key="item1_index">
                                <td>
                                    <div style="display:flex;">
                                        <div>
                                            {{ item1_index + 1 }}
                                        </div>
                                        <div>
                                            <input type="checkbox" v-model="indexes[item_index][item1_index]" 
                                                @input="update_row($event.target.checked, item_index, item1_index)" 
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
                                <td v-if="is_rework">
                                    {{j.item_type}}
                                </td>
                                <td v-for="attr in j.values" :key="attr">
                                    {{ attr.delivered_quantity}} <span v-if="j.default_uom">{{ " " + j.default_uom }}</span>
                                    <form>
                                        <input class="form-control" type="number" v-model.number="attr.return_quantity" min="0" step="0.001"/>
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
			</template>
		</table>
	</div>	
</template>
	
<script setup>
import { ref, onMounted } from 'vue';

let items = ref([]);
let is_rework = cur_frm.doc.is_rework
let indexes = []
let received_type = ref(null)
let sample_doc = ref({})
let root = ref(null)

function load_data(data){
    items.value = data
    for(let i = 0 ; i < items.value.length ; i++){
        indexes.push([])
        for(let j = 0 ; j < items.value[i].items.length ; j++){
            indexes[i].push(false)
        }
    }
}

function get_items(){
    if(!received_type.get_value()){
        frappe.msgprint("Enter the Return Type")
        return
    }
	for(let i = 0 ; i < items.value.length ; i++){
		for(let j = 0 ; j < items.value[i].items.length ; j++){
			Object.keys(items.value[i].items[j].values).forEach(key => {
				if(items.value[i].items[j].values[key].delivered_quantity == "" || items.value[i].items[j].values[key].delivered_quantity == null){
					items.value[i].items[j].values[key].delivered_quantity = 0
				}
			})
		}
	}
	return {
        "items": items.value,
        "received_type": received_type.get_value()
    }
}

function update_row(val, index1, index2){
    Object.keys(items.value[index1].items[index2].values).forEach(key => {
        if(val){
            items.value[index1].items[index2].values[key].return_quantity = items.value[index1].items[index2].values[key].delivered_quantity
        }
        else{
            items.value[index1].items[index2].values[key].return_quantity = 0
        }
    })
    indexes[index1][index2] = val
}

function update_group(val, index){
    for(let i = 0 ; i < items.value[index].items.length ; i++){
        Object.keys(items.value[index].items[i].values).forEach(key => {
            if(val){
                items.value[index].items[i].values[key].return_quantity = items.value[index].items[i].values[key].delivered_quantity
            }
            else{
                items.value[index].items[i].values[key].return_quantity = 0
            }
        })
        indexes[index][i] = val
    }
}

onMounted(()=> {
    let el = root.value
    $(el).find(".received-type").html("");
    received_type = frappe.ui.form.make_control({
        parent: $(el).find(".received-type"),
        df: {
            fieldname: "received_type",
            fieldtype: "Link",
            options: "GRN Item Type",
            label: "Return Type",
            reqd: true,
        },
        doc: sample_doc.value,
        render_input: true,
    })
})

defineExpose({
	load_data,
	get_items,
})

</script>
	