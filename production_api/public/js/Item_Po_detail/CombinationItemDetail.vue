<template>
    <div ref="root">
        <table class="table table-sm table-bordered">
            <tr>
                <th v-for="x in items.attributes" :key="x">{{ x }}</th>
            </tr>
            <tr v-for="(item, index) in items.values" :key="index">
                <td v-for="(value, key) in item.val" :key="key">
                    <div :class="get_input_class(key, index)"></div>
                </td>
            </tr>
        </table>
    </div>
</template>
<script setup>
import {ref} from 'vue';

const items = ref([])
const root = ref(null)
const sample_doc = ref({})

function load_data(item){
    items.value = item;
}

function set_attributes() {
    remove_attributes()
    if (items.value) {
        for(let i = 0; i < items.value.values.length ; i++){
            Object.keys(items.value.values[i]['val']).forEach(row => {
                let val = items.value.values[i]['val'][row]
                let input =createInput(row, i, val)
                items.value.values[i]['val'][row] = input 
            })
        }
    }
}

function remove_attributes(){
    for(let i = 0; i < items.value.values.length ; i++){
        Object.keys(items.value.values[i]['val']).forEach(row => {
            let el = root.value
            let parent_class = "." + get_input_class(row, i);
            $(el).find(parent_class).empty();
        })
    }
}

function createInput(attr, index, value){
    let parent_class = "." + get_input_class(attr, index);
    let el = root.value
    let df = {
        fieldtype: 'Link',
        fieldname: attr+"_"+index,
        options: 'Item Attribute Value',
        get_query : function(){
            return {
                query:'production_api.essdee_production.doctype.item_production_detail.item_production_detail.get_attribute_detail_values',
                filters: {
                    'mapping': cur_frm.set_packing_attr_map_value,
                }
            }
        },
        default: value,
    }

    if (attr == cur_frm.doc.stiching_major_attribute_value){
        df['read_only'] = true
    }   
    let input =  frappe.ui.form.make_control({
        parent: $(el).find(parent_class),
        df:df ,
        doc: sample_doc.value,
        render_input: true,
    });

    input.set_value(value)
    
    input['df']['onchange'] = ()=>{
       if(input.get_value() != input.df.default){
           cur_frm.dirty()
        }
    }
    return input
}
function get_input_class(attribute, index){
    attribute = attribute.replaceAll(" ","-")
    return attribute+"-"+index;
}
function get_data(){
    const x = ref(items.value)
    for (let i = 0; i < x.value.values.length; i++) {
        Object.keys(x.value.values[i]['val']).forEach(row => {
            let input = x.value.values[i]['val'][row]
            let value = null
            if(typeof(input) == 'object'){
                value = input.get_value()
            }
            else{
                value = input
            }
            if(value == null || value == ""){
                frappe.throw("Fill all the combinations")
            }
            x.value.values[i]['val'][row] = value
        })
    }
    return x.value
}
defineExpose({
    load_data,
    set_attributes,
    get_data,
});
</script>
