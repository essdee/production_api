<template>
    <div ref="root">
        <table class="table table-sm table-bordered">
            <tr>
                <th v-for="x in items.attributes" :key="x" class="equal-width">
                    <div v-if='x != "Weight"'>{{ x }}</div>
                    <div v-else>{{ "Weight ( In Kg's )" }}</div>
                </th>
            </tr>
            <tr v-for="(item, index) in items.items" :key="index">
                <td v-for="(value, key) in item" :key="key" class="equal-width">
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
            Object.keys(items.value.items[i]).forEach(row => {
                let val = items.value.items[i][row]
                let input =createInput(row, i, val)
                items.value.items[i][row] = input 
            })
        }
    }
}

function remove_attributes(){
    for(let i = 0; i < items.value.items.length ; i++){
        Object.keys(items.value.items[i]).forEach(row => {
            let el = root.value
            let parent_class = "." + get_input_class(row, i);
            $(el).find(parent_class).empty();
        })
    }
}

function createInput(attr, index, value){
    let parent_class = "." + get_input_class(attr, index);
    let fieldtype = 'Link'
    if (attr == "Dia"){
        fieldtype = "Link"
    }
    else if(attr == 'Weight'){
        fieldtype = 'Float'
    }
    else if(attr == 'Cloth'){
        fieldtype = 'Select'
    }
    else if(attr == 'Required GSM'){
        fieldtype = "Int"
    }

    let el = root.value
    let df = {
        fieldtype: fieldtype,
        fieldname: attr+"_"+index,
        default: value,
    }
    if (fieldtype == 'Link' && attr != 'Dia'){
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
    else if(fieldtype == 'Link'){
        df['options'] = 'Item Attribute Value'
        df['get_query'] = function(){
            return {
                filters: {
                    'attribute_name': 'Dia',
                }
            }
        }
    }
    else if(fieldtype == 'Select'){
        df['options'] = items.value.select_list
    }
    
    if (cur_frm.cutting_attrs.includes(attr)){
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
    if(!items.value.items){
        return null
    }
    let field = 'Required GSM'
    if(items.value.combination_type == 'Cloth'){
        let cloths = []
        for(let i = 0 ; i < cur_frm.doc.cloth_detail.length; i++){
            cloths.push(cur_frm.doc.cloth_detail[i].name1)
        }
        if(!cur_frm.is_new()){
            for(let i = 0 ; i < items.value['items'].length ; i++){
                let c = items.value['items'][i]['Cloth'].get_value()
                if(!cloths.includes(c)){
                    frappe.throw("Some Cloth items not in the select list")
                }
            }
        }
    }
    let ind = -1
    for(let i = 0 ; i < items.value.attributes.length; i++){
        if(items.value.attributes[i] == field){
            ind = i;
            break
        }
    }
    const x = ref(items.value)
    for (let i = 0; i < x.value.items.length; i++) {
        Object.keys(x.value.items[i]).forEach((row, index) => {
            let input = x.value.items[i][row]
            let value = null
            if(typeof(input) == 'object'){
                value = input.get_value()
            }
            else {
                value = input
            }
            if(value == null || value == ""){
                if(index != ind){
                    frappe.throw("Fill all the combinations")    
                }
                x.value.items[i][row] = null
            }
            else{
                x.value.items[i][row] = value
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

<style scoped>
table {
    table-layout: fixed;
    width: 100%; /* Ensures the table takes full width */
}

.equal-width {
    word-wrap: break-word; /* Prevent overflow of long text */
}

</style>
