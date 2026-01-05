<template>
    <div ref="root" class="box-container">
        <div class="section">
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
                             :disabled="true" class="styled-input" />
                        </td>
                        <td>{{ total_qty }}</td>
                    </tr>
                    <tr>
                        <td>Ratio</td>
                        <td v-for="(value, index) in primary_values" :key="index">
                            <input type="number" v-model="box_qty[value]['ratio']" 
                             :disabled="true" class="styled-input" />
                        </td>
                        <td></td>
                    </tr>
                    <tr>
                        <td>Wholesale Price</td>
                        <td v-for="(value, index) in primary_values" :key="index">
                            <input type="number" v-model="box_qty[value]['wholesale']" 
                             class="styled-input" />
                        </td>
                        <td></td>
                    </tr>
                    <tr>
                        <td>Retail Price</td>
                        <td v-for="(value, index) in primary_values" :key="index">
                            <input type="number" v-model="box_qty[value]['retail']" 
                             class="styled-input" />
                        </td>
                        <td></td>
                    </tr>
                    <tr>
                        <td>MRP</td>
                        <td v-for="(value, index) in primary_values" :key="index">
                            <input type="number" v-model="box_qty[value]['mrp']" 
                             class="styled-input" />
                        </td>
                        <td></td>
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
let total_qty = ref(0)

onMounted(()=> {
    frappe.call({
        method: "production_api.production_api.doctype.production_order.production_order.get_primary_values",
        args: {
            item: cur_frm.doc.item
        },
        callback: function(response) {
            primary_values.value = response.message || [];
        }
    })
})

function get_items(){
    return box_qty.value;
}

function load_data(data){
    let items = JSON.parse(JSON.stringify(data));
    Object.keys(items).forEach(key => {
        total_qty.value += items[key]['qty'];
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
    padding: 10px 0;
    font-family: var(--font-stack);
}

.section {
    background: #fff;
    border: 1px solid #d1d8dd;
    border-radius: 4px;
    overflow: hidden;
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
