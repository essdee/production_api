<template>
    <div ref="root">
        <table v-if="docstatus !== 0" class="table table-sm table-bordered">
			<tr v-for="(i, item_index) in items" :key="item_index">
				<td v-if="i.primary_attribute">
					<table class="table table-sm table-bordered" v-if="i.items && i.items.length > 0" >
						<tr>
							<th>S.No.</th>
							<th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
							<th v-for="attr in i.primary_attribute_values" :key="attr">{{ attr }}</th>
						</tr>
						<tr v-for="(j, item1_index) in i.items" :key="item1_index">
							<td>{{ item1_index + 1 }}</td>
							<td v-for="attr in i.attributes" :key="attr">
                                {{ j.attributes[attr] }}
                                <span v-if="attr == 'Colour' && j.is_set_item && j.attributes[j.set_attr] != j.major_attr_value">({{ j.item_keys['major_colour'] }})</span>
                            </td>
							<td v-for="attr in j.values" :key="attr">
								<div v-if="attr.qty">
									{{ attr.qty}}
								</div>
								<div v-else class="text-center">---</div>
							</td>
						</tr>
					</table>
				</td>
			</tr>
		</table>
        <table v-else class="table table-sm table-bordered">
			<tr v-for="(i, item_index) in items" :key="item_index">
                <table class="table table-sm table-bordered" v-if="i.items && i.items.length > 0" >
                    <tr>
                        <th>S.No.</th>
                        <th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
                        <th v-for="attr in i.primary_attribute_values" :key="attr">{{ attr }}</th>
                    </tr>
                    <tr v-for="(j, item1_index) in i.items" :key="item1_index">
                        <td>{{ item1_index + 1 }}</td>
                        <td v-for="attr in i.attributes" :key="attr">
                            {{ j.attributes[attr] }}
                            <span v-if="attr == 'Colour' && j.is_set_item && j.attributes[j.set_attr] != j.major_attr_value">({{ j.item_keys['major_colour'] }})</span>
                        </td>
                        <td v-for="attr in Object.keys(j.values)" :key="attr">
                            <form>
                                <input class="form-control" type="number" v-model.number="j.values[attr]['qty']" min="0" @blur="update_doc()"/>
                            </form>
                        </td>
                    </tr>
                </table>
			</tr>
        </table>
    </div>  
</template>

<script setup>
import {ref, onMounted} from 'vue';

let items = ref(null)
let show_title = ref(false)
let docstatus = ref(0)
function load_data(item){
    docstatus.value = cur_frm.doc.docstatus
    items.value = item;
    if(item.length > 0){
        show_title.value = true
    }
}

function update_doc(){
    cur_frm.dirty()
}
function get_items(){
    return items.value
}
function update_docstatus(){
    docstatus.value = 1
}

defineExpose({
    load_data,
    get_items,
    update_docstatus,
})
</script>
