<template>
    <div ref="root">
        <h3>Enter Box Quantity</h3>
        <table>
            <tr>
                <th v-for="(value, index) in primary_values" :key="index"> {{ value }}</th>
            </tr>
            <tr>
                <td v-for="(value, index) in primary_values" :key="index">
                    <input type="number" v-model="box_qty[value]" @blur="make_dirty()" :disabled="disables" class="form-control" />
                </td>
            </tr>
        </table>
    </div>
</template>

<script setup>
import {ref, onMounted} from 'vue';

const root = ref(null);
const primary_values = ref([])
let box_qty = ref({})
let disables = ref(false)

onMounted(()=> {
    frappe.call({
        method: "production_api.production_api.doctype.goods_received_note.goods_received_note.get_primary_values",
        args: {
            lot: cur_frm.doc.lot
        },
        callback: function(response) {
            if(cur_frm.doc.docstatus != 0){
                disables.value = true
            }
            primary_values.value = response.message || [];
            primary_values.value.forEach(value => {
                if (!(value in box_qty.value)) {
                    box_qty.value[value] = 0;
                }
            });
        }
    })
})

function make_dirty() {
    if(!cur_frm.is_dirty()){
        cur_frm.dirty();
    }
}

function get_items(){
    return box_qty.value;
}

function load_data(data){
    let items = JSON.parse(JSON.stringify(data));
    Object.keys(items).forEach(key => {
        console.log(items[key])
        box_qty.value[key] = items[key];
    });
}

defineExpose({
    get_items,
    load_data,
});

</script>