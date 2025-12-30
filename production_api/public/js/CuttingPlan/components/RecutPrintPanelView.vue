<template>
    <div>
        <div class="row" v-if="items && Object.keys(items).length > 0">
            <h3>{{type_value}} Summary</h3>
            <table class='table table-sm table-bordered'>
                <tr>
                    <th>S.No</th>
                    <th>Cloth Type</th>
                    <th>Colour</th>
                    <th>Dia</th>
                    <th>Shade</th>
                    <th>Weight in Kg's</th>
                    <th>No of Rolls</th>
                    <th v-if="type_value=='Print Panel'">Panel Count</th>
                </tr>
                <tr v-for="(item,idx) in Object.keys(items)" :key='idx'>
                    <td>{{idx + 1}}</td>
                    <td>{{items[item].cloth_type}}</td>
                    <td>{{items[item].colour}}</td>
                    <td>{{items[item].dia}}</td>
                    <td>{{items[item].shade}}</td>
                    <td>{{items[item].weight}}</td>
                    <td>{{items[item].no_of_rolls}}</td>
                    <td v-if="type_value=='Print Panel'">{{ items[item].panel_count }}</td>
                </tr>
            </table>
        </div>
    </div>
</template>

<script setup>

import { ref } from 'vue';
let items = ref([]);
let type_value = ref(null)

function load_data(type){
    type_value.value = type
    frappe.call({
        method: "production_api.production_api.doctype.cutting_plan.cutting_plan.get_recut_print_panel_details",
        args: {
            cutting_plan: cur_frm.doc.name,
            type: type_value.value,
        },
        callback: function(r){
            items.value = r.message;
        }
    })
}

defineExpose({
    load_data,
})

</script>