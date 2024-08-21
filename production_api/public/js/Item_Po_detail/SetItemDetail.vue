<template>
    <div ref="root">
        <table class="table table-sm table-bordered">
            <tr>
                <th>{{ items.major_attribute }}</th>
                <th v-for="x in items.set_attributes" :key="x">{{ x }}</th>
            </tr>
            <tr v-for="(item, index) in items.values" :key="index">
                <td class='pt-4'>{{ item.major_attribute }}</td>
                <td v-for="(value, key) in item.val" :key="key">
                <div :class="get_input_class(key, index)"></div>
                </td>
            </tr>
        </table>
    </div>
</template>
<script setup>
import {ref,reactive, onMounted, nextTick} from 'vue';
const items = ref([])
const root = ref(null)
const sample_doc = ref({})
function load_data(item){
    items.value = item; 
}

async function set_attributes() {
    await remove_attributes()
    if (items.value) {
        for(let i = 0; i < items.value.values.length ; i++){
            Object.keys(items.value.values[i]['val']).forEach(row => {
                let val = items.value.values[i]['val'][row]
                let input =  createInput(row, i)
                input.set_value(val)
                items.value.values[i]['val'][row] = input 
            })
        }
    }
}

async function remove_attributes(){
    for(let i = 0; i < items.value.values.length ; i++){
        Object.keys(items.value.values[i]['val']).forEach(row => {
            let el = root.value
            let parent_class = "." + get_input_class(row, i);
            $(el).find(parent_class).empty();
        })
    }
}
function createInput(attr, index){
    let parent_class = "." + get_input_class(attr, index);
    let el = root.value
    return frappe.ui.form.make_control({
        parent: $(el).find(parent_class),
        df: {
            fieldtype: 'Link',
            fieldname: attr+"_"+index,
            options: 'Item Attribute Value',
            get_query : function(){
                return {
                    query:'production_api.essdee_production.doctype.item_production_detail.item_production_detail.get_attribute_detail_values',
                    filters: {
                        'mapping': cur_frm.set_packing_attr_map,
                    }
                }
            },
        },
        doc: sample_doc.value,
        render_input: true,
    });
}
function get_input_class(attribute, index){
      return attribute+"-"+index;
}
function get_data(){
    for (let i = 0; i < items.value.values.length; i++) {
        Object.keys(items.value.values[i]['val']).forEach(row => {
            let input = items.value.values[i]['val'][row]
            let value = null
            if(typeof(input) == 'string'){
                value = input
            }
            else{
                value = input.get_value()
            }
            if(value == null || value == ""){
                frappe.throw("Fill all the combinations")
            }
            items.value.values[i]['val'][row] = value
        })
    }
    return items.value
}
defineExpose({
    load_data,
    set_attributes,
    get_data,
})
</script>


