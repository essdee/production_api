<template>
    <div ref="root" class="box-container">
        <div class="section">
            <h3 class="section-title">Total Order Quantity</h3>
            <table class="styled-table">
                <thead>
                    <tr>
                        <th>Size</th>
                        <th v-for="(value, index) in primary_values" :key="index"> {{ value }}</th>
                        <th>Total</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>Qty</td>
                        <td v-for="(value, index) in primary_values" :key="index">
                            <input type="number" v-model="box_qty[value]['qty']" 
                                @blur="make_dirty()" :disabled="disables" class="styled-input" />
                        </td>
                        <td>{{ total_qty }}</td>
                    </tr>
                    <tr>
                        <td>Ratio</td>
                        <td v-for="(value, index) in primary_values" :key="index">
                            <input type="number" v-model="box_qty[value]['ratio']" 
                                @blur="make_dirty()" :disabled="disables" class="styled-input" />
                        </td>
                        <td></td>
                    </tr>
                    <tr>
                        <td>Wholesale Price</td>
                        <td v-for="(value, index) in primary_values" :key="index">
                            <input type="number" v-model="box_qty[value]['wholesale']" 
                                @blur="make_dirty()" :disabled="disables" class="styled-input" />
                        </td>
                        <td></td>
                    </tr>
                    <tr>
                        <td>Retail Price</td>
                        <td v-for="(value, index) in primary_values" :key="index">
                            <input type="number" v-model="box_qty[value]['retail']" 
                                @blur="make_dirty()" :disabled="disables" class="styled-input" />
                        </td>
                        <td></td>
                    </tr>
                    <tr>
                        <td>MRP</td>
                        <td v-for="(value, index) in primary_values" :key="index">
                            <input type="number" v-model="box_qty[value]['mrp']" 
                                @blur="make_dirty()" :disabled="disables" class="styled-input" />
                        </td>
                        <td></td>
                    </tr>
                </tbody>
            </table>
        </div>
        <div v-if="Object.keys(lot_wise_detail).length > 0" style="padding-top: 15px;">
            <h3>Lotwise Ordered Detail </h3>
            <div v-for="(idx, lot) in lot_wise_detail" :key="idx" class="section1" style="padding-top: 15px;">
                <p>Lot: {{ lot }}</p>
                <table class="styled-table">
                    <thead>
                        <tr>
                            <th>Size</th>
                            <th v-for="(value, index) in primary_values" :key="index"> {{ value }}</th>
                            <th>Total</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>Qty</td>
                            <td v-for="(value, index) in primary_values" :key="index">
                                <input type="number" v-model="lot_wise_detail[lot][value]['qty']" 
                                    @blur="make_dirty()" :disabled="disables" class="styled-input" />
                            </td>
                            <td>{{ total_qty }}</td>
                        </tr>
                    </tbody>
                </table>
            </div>    
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
let total_qty = ref(0)
let lot_wise_detail = ref({})

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
                        "wholesale": 0,
                        "retail": 0,
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
    Object.keys(items['items']).forEach(key => {
        total_qty.value += items['items'][key]['qty'];
        box_qty.value[key] = items['items'][key];
    });
    lot_wise_detail.value = items['ordered'];
}

defineExpose({
    get_items,
    load_data,
});
</script>

<style scoped>
.box-container {
    padding: 10px 0;
    font-family: var(--font-stack);
}

.section {
    background: #fff;
    border: 1px solid #d1d8dd;
    border-radius: 4px;
    overflow: hidden;
}
.section1 {
    background: #fff;
    border: 1px solid #d1d8dd;
    border-radius: 4px;
    overflow: hidden;
    font-size: 15px;
    font-weight: 600;
    padding-left: 10px;
}
.section-title {
    font-size: 14px;
    font-weight: 700;
    margin: 0;
    padding: 12px 15px;
    color: #111827;
    background-color: #f7fafc;
    border-bottom: 1px solid #d1d8dd;
}

.styled-table {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 0;
    font-size: 13px;
    color: #1f2937;
}

.styled-table th {
    background-color: #f7fafc;
    color: #64748b;
    font-weight: 700;
    padding: 8px 12px;
    border-bottom: 1px solid #d1d8dd;
    border-right: 1px solid #d1d8dd;
    text-align: center;
}

.styled-table th:last-child {
    border-right: none;
}

.styled-table td {
    padding: 8px 12px;
    border-bottom: 1px solid #d1d8dd;
    border-right: 1px solid #d1d8dd;
    text-align: center;
    vertical-align: middle;
}

.styled-table td:last-child {
    border-right: none;
}

.styled-table tr:last-child td {
    border-bottom: none;
}

.styled-table tr:hover {
    background-color: #f9fafb;
}

.styled-input {
    width: 100%;
    max-width: 80px;
    height: 28px;
    padding: 4px 8px;
    font-size: 13px;
    border: 1px solid #d1d8dd;
    border-radius: 4px;
    text-align: center;
    background-color: #fff;
    color: #111827;
    transition: border-color 0.1s ease;
    outline: none;
}

.styled-input:focus {
    border-color: #1b8dff;
    background-color: #fff;
}

.styled-input:disabled {
    background-color: #f3f3f3;
    cursor: not-allowed;
    border-color: #d1d8dd;
}

/* Chrome, Safari, Edge, Opera */
input::-webkit-outer-spin-button,
input::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

/* Firefox */
input[type=number] {
  -moz-appearance: textfield;
  appearance: none;
}
</style>
