<template>
    <div>
        <button class="btn btn-success" @click="fetch_items()">Fetch Items</button>
        <div style="margin-top:20px;"></div>
        <div v-for="row in items">
            <h3>{{ row.lot }} - {{ row.warehouse_name }}</h3>
            <table class="table table-sm table-sm-bordered bordered-table">
                <thead class="dark-border">
                    <tr>
                        <th style="width:20px;">S.No</th>
                        <th style="width:20px;">Colour</th>
                        <th style="width:20px;" v-if="items.is_set_item">{{ row['set_attr'] }}</th>
                        <th style="width:150px;">Type</th>
                        <th v-for="size in row.primary_values" :key="size">{{ size }}</th>
                        <th>Total</th>
                    </tr>
                </thead>
                <tbody class="dark-border" v-for="(colour, idx) in Object.keys(row['old_lot_inward']['data'])" :key="colour">
                    <tr>
                        <td :rowspan="2">{{ idx + 1 }}</td>
                        <td :rowspan="2">{{ colour }}</td>
                        <td :rowspan="2" v-if="row.is_set_item">{{ row['old_lot_inward']['data'][colour]['part'] }}</td>
                        <td>Quantity</td>
                        <td v-for="size in row.primary_values" :key="size">
                            {{
                                row['old_lot_inward']['data'][colour]["values"][size]['balance'] ?? 0
                            }}
                        </td>
                        <td><strong>{{ row['old_lot_inward']['data'][colour]['colour_total']['balance'] ?? 0 }}</strong></td>
                    </tr>
                    <tr>
                        <td>Transfer</td>
                        <td v-for="size in row.primary_values" :key="size">
                            {{
                                row['old_lot_inward']['data'][colour]["values"][size]['transfer'] ?? 0
                            }}
                        </td>
                        <td><strong>{{ row['old_lot_inward']['data'][colour]['colour_total']['transfer'] ?? 0 }}</strong></td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>
</template>

<script setup>
import { ref } from 'vue';

let items = ref([])

function fetch_items(){
    frappe.call({
        method: "production_api.production_api.doctype.finishing_plan.finishing_plan.fetch_from_old_lot",
        args: {
            "lot": cur_frm.doc.lot,
            "item": cur_frm.doc.item,
        },
        freeze: true,
        freeze_message: "Fetching Old Lot Items",
        callback: function(r){
            items.value = r.message
        }
    })
}
</script>

<style scoped>
.bordered-table {
    width: 100%;
    border: 1px solid #ccc;
    border-collapse: collapse;
}

.bordered-table th,
.bordered-table td {
    border: 1px solid #ccc;
    padding: 6px 8px;
    text-align: center;
}

.bordered-table thead {
    background-color: #f8f9fa;
    font-weight: bold;
}

.dark-border{
    border: 2px solid black;
}
</style>