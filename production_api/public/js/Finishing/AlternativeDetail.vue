<template>
    <div>
        <h2>Alternative Detail</h2>
        <div v-if="items && Object.keys(items).length > 0">
            <div v-for="lot in Object.keys(items)" :key="lot">
                <h3>{{ lot }} - {{ items[lot]['item'] }}</h3>
                <table class="table table-sm table-bordered">
                    <tr v-for="(i, item_index) in items[lot]['details']" :key="item_index">
                        <td>
                            <table class="table table-sm table-bordered" v-if="i.items && i.items.length > 0" >
                                <tr>
                                    <th>S.No.</th>
                                    <th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
                                    <th v-for="attr in i.primary_attribute_values" :key="attr">{{ attr }}</th>
                                    <th>Total</th>
                                </tr>
                                <tr v-for="(j, item1_index) in i.items" :key="item1_index">
                                    <td>{{ item1_index + 1 }}</td>
                                    <td v-for="attr in i.attributes" :key="attr">
                                        {{ j.attributes[attr] }}
                                        <span v-if="version == 'V2' || version == 'V3'">
                                            <span v-if="attr == 'Colour' && j.is_set_item && j.attributes[j.set_attr] != j.major_attr_value">({{ j.item_keys['major_colour'] }})</span>
                                        </span>
                                    </td>
                                    <td v-for="attr in j.values" :key="attr">
                                        <div v-if="attr.qty">
                                            {{ attr.qty}}
                                        </div>
                                        <div v-else class="text-center">---</div>
                                    </td>
                                    <th>{{ j.total_qty }}</th>
                                </tr>
                                <tr>
                                    <th>Total</th>
                                    <td v-for="attr in i.attributes"></td>
                                    <th v-for="size in i.size_wise_total" :key="size">{{ size }}</th>
                                    <th>{{ i.total_sum }}</th>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>
            </div>
        </div>
        <div v-else style="text-align: center;">
            <h2>No alternative details available</h2>
        </div>
    </div>
</template>

<script setup>

import { ref, onMounted } from 'vue';

let items = ref({})

onMounted(() => {
    frappe.call({
        method: "production_api.production_api.doctype.finishing_plan.finishing_plan.get_alternative_details",
        args: {
            "lot": cur_frm.doc.doctype == 'Lot' ? cur_frm.doc.name : cur_frm.doc.lot,
        },
        callback: function (r) {
            items.value = r.message;
        }
    })
    console.log('AlternativeDetail mounted');
})

</script>