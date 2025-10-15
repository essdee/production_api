<template>
    <div>
        <div v-if="items && items.length > 0">
            <div v-for="row in items">
                <h3>{{ row.lot }}-{{ row.item }}</h3>
                <table class="table table-sm table-sm-bordered bordered-table">
                    <thead class="dark-border">
                        <tr>
                            <th>{{ row.primary_attribute }}</th>
                            <th v-for="(val, size) in row.values">{{ size }}</th>
                        </tr>
                    </thead>
                    <tbody class="dark-border">
                        <tr>
                            <td>Quantity</td>
                            <td v-for="size in row.values">{{ size['qty'] }}</td>
                        </tr>
                        <tr>
                            <td>Dispatch Qty</td>
                            <td v-for="(val, size) in row.values">
                                <div v-if="docstatus == 0">
                                    <input type="number" v-model="row.values[size]['dispatch_qty']" class="form-control" @blur="make_dirty()" />
                                </div>
                                <div v-else>
                                    {{ val['dispatch_qty'] }}
                                </div>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>      
    </div>
</template>

<script setup>
import {ref} from 'vue';

let items = ref([])
let docstatus = cur_frm.doc.docstatus

function load_data(data){
    items.value = data    
}

function get_data(){
    return items.value
}

function make_dirty(){
    if(!cur_frm.is_dirty()){
        cur_frm.dirty()
    }
}

defineExpose({
    load_data,
    get_data,
})

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