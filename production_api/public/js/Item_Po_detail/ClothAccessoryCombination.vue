<template>
    <div ref="root">
        <table class="table table-sm table-bordered">
            <tr>
                <th v-for="x in items.attributes" :key="x">
                    <div v-if='x != "Weight"'>{{ x }}</div>
                    <div v-else>{{ "Weight ( In Kg's )" }}</div>
                </th>
            </tr>
            <tr v-for="(item, index) in items.items" :key="index">
                <td>{{item.major_attr_value}}</td>
                <td v-for="(value, key) in item.accessories" :key="key">
                    <div :class="get_input_class(key, index, 'colour')"></div>
                    <div :class="get_input_class(key, index,'cloth_type')"></div>
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
    if(typeof(item) == 'string'){
        items.value = JSON.parse(item);
    }
    else{
        items.value = item
    }
}

function set_attributes() {
    if(!items.value.items){
        return
    }
    remove_attributes()
    if (items.value) {
        for(let i = 0; i < items.value.items.length ; i++){
            Object.keys(items.value.items[i]['accessories']).forEach(row => {
                let val = items.value.items[i]['accessories'][row]['colour']
                let input1 =createInput(row, i, val,"colour")
                items.value.items[i]['accessories'][row]['colour'] = input1
                let val2 = items.value.items[i]['accessories'][row]['cloth_type']
                let input2 =createInput(row, i, val2,"cloth_type")
                items.value.items[i]['accessories'][row]['cloth_type'] = input2
            })
        }
    }
}

function remove_attributes(){
    for(let i = 0; i < items.value.items.length ; i++){
        Object.keys(items.value.items[i]['accessories']).forEach(row => {
            let el = root.value
            let parent_class = "." + get_input_class(row, i, "colour");
            $(el).find(parent_class).empty();
            let parent_class2 = "." + get_input_class(row, i, "cloth_type");
            $(el).find(parent_class2).empty();
        })
    }
}

function createInput(attr, index, value, type){
    let parent_class = "." + get_input_class(attr, index, type);
    let fieldtype = 'Link'
    if(type == 'cloth_type'){
        fieldtype = 'Select'
    }

    let el = root.value
    let df = {
        fieldtype: fieldtype,
        fieldname: attr+"_"+index,
        default: value,
    }
    if (fieldtype == 'Link'){
        df['options'] = 'Item Attribute Value'
        df['get_query'] = function(){
            return {
                query:'production_api.essdee_production.doctype.item_production_detail.item_production_detail.get_attribute_detail_values',
                filters: {
                    'mapping': cur_frm.set_packing_attr_map_value,
                }
            }
        }
    }
    else{
        df['options'] = items.value.select_list
    }
    
    let input =  frappe.ui.form.make_control({
        parent: $(el).find(parent_class),
        df:df ,
        doc: sample_doc.value,
        render_input: true,
    });
    $(el).find(".control-label").remove();
    input.set_value(value)
    input['df']['onchange'] = ()=>{
       if(input.get_value() != input.df.default){
           cur_frm.dirty()
        }
    }
    return input
}

function get_input_class(attribute, index, type){
    attribute = attribute.replaceAll(" ","-")
    return attribute+"-"+index+"-"+type;
}

function get_data(){
    if(!items.value.items){
        return null
    }
    const x = ref(items.value)
    for (let i = 0; i < x.value.items.length; i++) {
        Object.keys(x.value.items[i]['accessories']).forEach((row, index) => {
            let input = x.value.items[i]['accessories'][row]['colour']
            let value = null
            if(typeof(input) == 'object'){
                value = input.get_value()
            }
            else {
                value = input
            }
            if(value == null || value == ""){
                frappe.throw("Fill all the combinations")    
            }
            else{
                x.value.items[i]['accessories'][row]['colour'] = value
            }
            let input2 = x.value.items[i]['accessories'][row]['cloth_type']
            let value2 = null
            if(typeof(input2) == 'object'){
                value2 = input2.get_value()
            }
            else {
                value2 = input2
            }
            if(value2 == null || value2 == ""){
                frappe.throw("Fill all the combinations")    
            }
            else{
                x.value.items[i]['accessories'][row]['cloth_type'] = value2
            }
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
