<template>
    <div ref="root">
        <table class="table table-sm table-bordered">
            <tr>
                <th v-for="x in items.attributes" :key="x" class="equal-width">
                    <div v-if='x != "Weight"'>{{ x }}</div>
                    <div v-else>{{ "Weight ( In Kg's )" }}</div>
                    <div style="display:flex;width:100%;">
                        <div style="width:100%;" :class="get_input_class(x, 1000)"></div>
                        <div v-if="items.items[0]?.[x]?.df?.hasOwnProperty('read_only')" style="padding-top:20px;padding-left: 5px;">
                            <div v-if="!items.items[0][x]['df']['read_only']">
                                <button class="btn btn-info" @click="fill_child_values(x, idx)">Fill</button>
                            </div>
                        </div>
                    </div>
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
let header_inputs = {}

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
                let input =createInput(row, i, val, false)
                if(i == 0 && !input.df.read_only){
                    if(!(row in header_inputs)){
                        header_inputs[row] = createInput(row, 1000, null, true)
                    }
                }
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

function createInput(attr, index, value, is_header){
    let parent_class = "." + get_input_class(attr, index);
    let fieldtype = 'Link'
    if(attr == 'Weight'){
        fieldtype = 'Float'
    }
    else if(attr == 'Accessory'){
        fieldtype = 'Data'
    }

    let el = root.value
    let df = {
        fieldtype: fieldtype,
        fieldname: attr+"_"+index,
        default: value,
        read_only: cur_frm.cutting_attrs.includes(attr) || attr == 'Accessory' || attr == cur_frm.doc.stiching_major_attribute_value
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
    else{
        df['options'] = 'Item Attribute Value'
        df['get_query'] = function(){
            return {
                filters: {
                    'attribute_name': 'Dia',
                }
            }
        }
    }
    
    let input =  frappe.ui.form.make_control({
        parent: $(el).find(parent_class),
        df:df ,
        doc: sample_doc.value,
        render_input: true,
    });

    if(!is_header){
        input.set_value(value)
        input['df']['onchange'] = ()=>{
        if(input.get_value() != input.df.default){
            cur_frm.dirty()
            }
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
                frappe.throw("Fill all the combinations")    
            }
            else{
                x.value.items[i][row] = value
            }
        })
    }
    return x.value
}

function fill_child_values(attr, index){
    let value = header_inputs[attr].get_value()
    for(let i = 0; i < items.value.items.length ; i++){
        items.value.items[i][attr].set_value(value)
    }
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
