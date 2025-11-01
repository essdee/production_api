<template>
    <div>
        <div v-for="(itemData, item, itemIdx) in items" :key="item">
            <table border="1" style="margin-bottom: 20px; border-collapse: collapse;">
                <thead>
                    <tr>
                    <th>S.No</th>
                    <th>Item</th>
                    <th>Colour</th>
                    <th>Qty</th>
                    <th>Fabric</th>
                    <th>Fabric Colour</th>
                    <th>Reqd Avg GSM</th>
                    <th>Reqd Pcs Weight</th>
                    <th>Reqd Total Weight</th>
                    <th>Actual Avg GSM</th>
                    <th>Actual Pcs Weight</th>
                    <th>Actual Requirement</th>
                    </tr>
                </thead>
                <tbody>
                    <template v-for="(colourData, colour, colourIdx) in itemData" :key="colour">
                        <tr v-for="(catData, cat, catIdx) in colourData['categories']" :key="cat">
                            <td v-if="catIdx === 0" :rowspan="Object.keys(colourData['categories']).length">
                                {{ colourIdx + 1 }}
                            </td>
                            <td v-if="catIdx === 0" :rowspan="Object.keys(colourData['categories']).length">
                                {{ item }}
                            </td>
                            <td v-if="catIdx === 0" :rowspan="Object.keys(colourData['categories']).length">
                                {{ colour }}
                            </td>
                            <td v-if="catIdx === 0" :rowspan="Object.keys(colourData['categories']).length">
                                {{ colourData['qty'] }}
                            </td>
                            <td>{{ cat }}</td>
                            <td>{{ catData.colour }}</td>
                            <td>
                                <input type="number" step="0.01" v-model="catData['reqd_gsm']" 
                                    class="form-control" @blur="make_dirty()"/>
                            </td>
                            <td>
                                <input type="number" step="0.01" v-model="catData.reqd_weight" 
                                    class="form-control" @blur="calculate_reqd_total(colour, cat, $event)"/>
                            </td>
                            <td>{{ catData.reqd_total }}</td>
                            <td>
                                <input type="number" step="0.01" v-model="catData['actual_gsm']" 
                                    class="form-control" @blur="make_dirty()"/>
                            </td>
                            <td>
                                <input type="number" step="0.01" v-model="catData.actual_weight" 
                                    class="form-control" @blur="calculate_actual_requirement(colour, cat, $event)"/>
                            </td>
                            <td>{{ catData.actual_reqd }}</td>
                        </tr>
                    </template>
                </tbody>
            </table>
        </div>
    </div>
</template>
  
<script setup>
import { ref } from "vue"

let items = ref({})

function load_data(data) {
    items.value = data
    if (Object.keys(data).length === 0) {
        frappe.call({
            method: "production_api.essdee_production.doctype.lot.lot.get_cad_detail",
            args: {
                ipd: cur_frm.doc.production_detail,
                lot: cur_frm.doc.name
            },
            callback: function (r) {
                items.value = r.message
            }
        })
    }
}

function calculate_actual_requirement(colour, category, event){
    make_dirty()
    let weight = event.target.value
    let qty = items.value[cur_frm.doc.item][colour]['qty']
    items.value[cur_frm.doc.item][colour]['categories'][category]['actual_reqd'] = (weight * qty).toFixed(3)
}

function calculate_reqd_total(colour, category, event){
    make_dirty()
    let weight = event.target.value
    let qty = items.value[cur_frm.doc.item][colour]['qty']
    items.value[cur_frm.doc.item][colour]['categories'][category]['reqd_total'] = (weight * qty).toFixed(3)
}

function make_dirty(){
    if(!cur_frm.is_dirty()){
        cur_frm.dirty()
    }
}

function get_data(){
    return items.value
}

defineExpose({
    load_data,
    get_data,
})
</script>

<style scoped>

table{
    width: 100%;
}
table td, th{
    text-align: center;
}

</style>
  