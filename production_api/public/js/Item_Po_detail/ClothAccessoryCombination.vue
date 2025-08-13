<template>
    <div ref="root">
        <table class="table table-sm table-bordered" v-if='items && items.items && items.items.length > 0'>
            <tr>
                <th v-for="(x, idx) in items.attributes" :key="x">
                    <div>{{ x }}</div>
                    <div style="display:flex;width:100%;">
                        <div v-if="idx == idx1" style="width:100%;" :class="get_input_class(x, 1000, 'accessory_colour')"></div>
                        <div v-if='idx == idx2' style="width:100%;" :class="get_input_class(x, 1000, 'cloth_type')"></div>
                        <div v-if="idx == idx1 || idx == idx2" style="padding-left: 5px;">
                            <button class="btn btn-info" @click="fill_child_values(x, idx)">Fill</button>
                        </div>
                    </div>
                </th>
            </tr>
            <tr v-for="(item, index) in items.items" :key="index">
                <td>{{item.accessory}}</td>
                <td v-if="items.is_set_item">{{item[items.set_attr]}}</td>
                <td>
                    {{item.major_colour}}
                    <span v-if="item.major_attr_value">({{item.major_attr_value}})</span>
                </td>
                <td>
                    <div :class="get_input_class(item.major_colour, index, 'accessory_colour')"></div>
                </td>
                <td>
                    <div :class="get_input_class(item.major_colour, index, 'cloth_type')"></div>
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
let idx1 = 0
let idx2 = 0

function load_data(item){
    if(cur_frm.doc.is_set_item){
        idx1 = 3
        idx2 = 4
    }
    else{
        idx1 = 2
        idx2 = 3
    }
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
            let val = items.value.items[i]['accessory_colour']
            let major_colour = items.value.items[i]['major_colour']
            let input1 = createInput(major_colour, i, val,"accessory_colour", false)
            items.value.items[i]['accessory_colour'] = input1
            let val2 = items.value.items[i]['cloth_type']
            let input2 = createInput(major_colour, i, val2,"cloth_type", false)
            items.value.items[i]['cloth_type'] = input2
            if(i == 0){
                header_inputs["Accessory Colour"] = createInput("Accessory Colour", 1000, null, "accessory_colour", true)
                header_inputs["Cloth"] = createInput("Cloth", 1000, null, "cloth_type", true)
            }
        }
    }
}

function remove_attributes(){
    for(let i = 0; i < items.value.items.length ; i++){
        let major_colour = items.value.items[i]['major_colour']
        let el = root.value
        let parent_class = "." + get_input_class(major_colour, i, "accessory_colour");
        $(el).find(parent_class).empty();
        let parent_class2 = "." + get_input_class(major_colour, i, "cloth_type");
        $(el).find(parent_class2).empty();
    }
}

function createInput(major_colour, index, value, type, is_header){
    let parent_class = "." + get_input_class(major_colour, index, type);
    let fieldtype = 'Link'
    if(type == 'cloth_type'){
        fieldtype = 'Select'
    }

    let el = root.value
    let df = {
        fieldtype: fieldtype,
        fieldname: major_colour+"_"+index,
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
        if(typeof(items.value.select_list) == 'string'){
            items.value.select_list = JSON.parse(items.value.select_list)
        }
        df['options'] = items.value.select_list
    }
    
    let input =  frappe.ui.form.make_control({
        parent: $(el).find(parent_class),
        df:df ,
        doc: sample_doc.value,
        render_input: true,
    });
    $(el).find(".control-label").remove();
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

function get_input_class(attribute, index, type){
    attribute = attribute.replaceAll(" ","-")
    return attribute+"-"+index+"-"+type;
}

function get_data(){
    if(!items.value.items){
        return null
    }
    const x = ref(items.value)
    let cloth_list = []
    for(let i = 0; i < cur_frm.doc.cloth_detail.length; i++ ){
        cloth_list.push(cur_frm.doc.cloth_detail[i]['name1'])
    }
    for (let i = 0; i < x.value.items.length; i++) {
        let input = x.value.items[i]['accessory_colour']
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
            x.value.items[i]['accessory_colour'] = value
        }
        let input2 = x.value.items[i]['cloth_type']
        let value2 = null
        if(typeof(input2) == 'object'){
            value2 = input2.get_value()
        }
        else {
            value2 = input2
        }
        if(!cloth_list.includes(value2)){
            frappe.throw("Some Cloths not in the Accessory Select List")
        }
        if(value2 == null || value2 == ""){
            frappe.throw("Fill all the combinations")    
        }
        else{
            x.value.items[i]['cloth_type'] = value2
        }
    }
    return x.value
}

function fill_child_values(attr, index){
    let value = header_inputs[attr].get_value()
    for(let i = 0; i < items.value.items.length ; i++){
        if(index == idx1){
            items.value.items[i].accessory_colour.set_value(value)
        }
        if(index == idx2){
            items.value.items[i].cloth_type.set_value(value)
        }
    }
}

defineExpose({
    load_data,
    set_attributes,
    get_data,
});
</script>
