<template>
    <div ref="root" class="box-container">
        <div class="section">
            <h3 class="section-title">Total Order Quantity</h3>
            <table class="styled-table">
                <thead>
                    <tr>
                        <th>Size</th>
                        <th v-for="(value, index) in primary_values" :key="index"> {{ value }}</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>Qty</td>
                        <td v-for="(value, index) in primary_values" :key="index">
                            <input type="number" v-model="box_qty[value]['qty']" 
                                @blur="make_dirty()" :disabled="disables" class="styled-input" />
                        </td>
                    </tr>
                    <tr>
                        <td>Ratio</td>
                        <td v-for="(value, index) in primary_values" :key="index">
                            <input type="number" v-model="box_qty[value]['ratio']" 
                                @blur="make_dirty()" :disabled="disables" class="styled-input" />
                        </td>
                    </tr>
                    <tr>
                        <td>MRP</td>
                        <td v-for="(value, index) in primary_values" :key="index">
                            <input type="number" v-model="box_qty[value]['mrp']" 
                                @blur="make_dirty()" class="styled-input" />
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>
</template>

<script setup>
import {ref, onMounted} from 'vue';

const root = ref(null);
const primary_values = ref([])
const emit = defineEmits(["values_update"])
let box_qty = ref({})
let disables = ref(false)

onMounted(()=> {
    frappe.call({
        method: "production_api.production_api.doctype.production_order.production_order.get_primary_values",
        args: {
            item: cur_frm.doc.item
        },
        callback: function(response) {
            if(cur_frm.doc.docstatus != 0){
                disables.value = true
            }
            primary_values.value = response.message || [];
            primary_values.value.forEach(value => {
                if (!(value in box_qty.value)) {
                    box_qty.value[value] = {
                        "qty": 0,
                        "ratio": 0,
                        "mrp": 0,
                    };
                }
            });
        }
    })
})

function make_dirty() {
    if(!cur_frm.is_dirty()){
        cur_frm.dirty();
    }
    cur_frm.doc['item_details'] = JSON.stringify(box_qty.value);
}

function get_items(){
    return box_qty.value;
}

function load_data(data){
    let items = JSON.parse(JSON.stringify(data));
    Object.keys(items).forEach(key => {
        box_qty.value[key] = items[key];
    });
}

defineExpose({
    get_items,
    load_data,
});
</script>

<style scoped>
.box-container {
    margin-top: 20px;
    font-family: Arial, sans-serif;
}

.section {
    margin-bottom: 30px;
}

.section-title {
    font-size: 18px;
    font-weight: 600;
    margin: 15px 0;
    color: #333;
}

.styled-table {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 20px;
    font-size: 14px;
    background: #fff;
    box-shadow: 0 2px 5px rgba(0,0,0,0.08);
    border-radius: 8px;
    overflow: hidden;
}

.styled-table th,
.styled-table td {
    border: 1px solid #e0e0e0;
    padding: 3px;
    text-align: center;
}

.styled-table thead {
    background: #f5f5f5;
    font-weight: bold;
}

.styled-input {
    width: 70px;
    padding: 3px 4px;
    font-size: 14px;
    border: 1px solid #ccc;
    border-radius: 6px;
    text-align: center;
    transition: 0.2s ease;
}

.styled-input:focus {
    border-color: #3b82f6;
    outline: none;
    box-shadow: 0 0 4px rgba(59, 130, 246, 0.4);
}

.styled-input:disabled {
    background: #f0f0f0;
    cursor: not-allowed;
}
</style>
