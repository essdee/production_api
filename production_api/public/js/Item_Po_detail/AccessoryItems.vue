<template>
    <div ref='root'>
        <table v-if="Object.keys(items).length > 0" class='table table-sm table-bordered'>
            <tr>
                <th>Acceesory</th>
                <th>Delete</th>
            </tr>
            <tr v-for="(item,val) in items" :key='item'>
                <td>{{val}}</td>
                <td @click="delete_item(val)"
                  v-html="frappe.utils.icon('delete', 'md')"></td>
            </tr>
        </table>
        <div class="row">
            <div class="accessory-item col-md-5"></div>
        </div>
        <button class="btn btn-success" v-if="show_button2" @click="add_item()">Add Item</button>
        <button class="btn btn-success" v-if="show_button1" @click="create_inputs()">Add Accessory Item</button>
        <div class="pb-5"></div>
    </div>
</template>

<script setup>
import {ref, onMounted} from 'vue';

let root = ref(null)
let items = ref({})
let sample_doc = ref({})
let accessoy_item = null
let cloth_types = null
let show_button1 = ref(true)
let show_button2 = ref(false)

function create_inputs(){
    let el = root.value
    $(el).find(".accessory-item").html("")
    accessoy_item = frappe.ui.form.make_control({
        parent:$(el).find(".accessory-item"),
        df: {
            fieldname:'cloth_accessory',
            fieldtype:"Data",
            label:"Accessory",
            reqd:true,
        },
        doc: sample_doc.value,
        render_input: true,
    })
    show_button1.value = false
    show_button2.value = true
}

function delete_item(key){
    cur_frm.dirty()
    delete items.value[key]
}
function add_item(){
    let el = root.value
    items.value[accessoy_item.get_value()] = null
    accessoy_item.set_value(null)
    $(el).find(".cloth-type").html("")
    $(el).find(".accessory-item").html("")
    show_button1.value = true
    show_button2.value = false
    cur_frm.dirty()
}

function load_data(item){
    items.value = item
}

function get_items(){
    return items.value
}

onMounted(()=> {
    let attr_list = []
    for(let i = 0; i < cur_frm.doc.cloth_detail.length; i++){
        attr_list.push(cur_frm.doc.cloth_detail[i]['name1'])
    }
    cloth_types = attr_list
})

defineExpose({
    load_data,
    get_items,
})
</script>
