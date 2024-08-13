<template>
    <div class="item frappe-control">
        <item-lot-fetcher 
            :items="items"
            :other-inputs="otherInputs"
            :table-fields="table_fields"
            :allow-secondary-qty="true"
            :args="args"
            :edit="docstatus == 0"
            :validate-qty="true"
            :enableAdditionalParameter="true"
            :validate="true"
            @itemadded="updated"
            @itemupdated="updated"
            @itemremoved="updated">
        </item-lot-fetcher>
    </div>
</template>

<script setup>
import { ref, onMounted, reactive } from 'vue'

import EventBus from '../../bus';
import ItemLotFetcher from '../../components/ItemLotFetch.vue'

const docstatus = ref(0);
const items = ref([]);
const supplier = ref(cur_frm.doc.supplier);
const delivery_date = ref(null)

const otherInputs = ref([
    {
        name: 'delivery_location',
        parent: 'delivery-location-control',
        df: {
            fieldtype: 'Link',
            fieldname: 'delivery_location',
            options: 'Supplier',
            label: 'Delivery Location',
            reqd: true,
        },
        query: function(data, inputs) {
            return {
                filters: {
                    is_company_location: inputs['deliver_to_supplier'].get_value() ? 0 : 1,
                }
            }
        }
    },
    {
        name: 'deliver_to_supplier',
        parent: 'delivery-location-control',
        df: {
            fieldtype: 'Check',
            fieldname: 'deliver_to_supplier',
            label: 'Deliver to Supplier',
        },
    },
    {
        name: 'delivery_date',
        parent: 'delivery-date-control',
        df: {
            fieldtype: 'Date',
            fieldname: 'delivery_date',
            label: 'Delivery Date',
            reqd: true,
        },
    },
    {
        name: 'discount_percentage',
        parent: 'discount-control',
        df: {
            fieldtype: 'Float',
            fieldname: 'discount_percentage',
            label: 'Discount %',
            default: 0,
            non_negative: 1,
            precision: "1"
        },
    },
    {
        name: 'comments',
        parent: 'comments-control',
        df: {
            fieldtype: 'Data',
            fieldname: 'comments',
            label: 'Comments',
        },
    },
]);

const table_fields = ref([
    {
        name: 'pending_qty',
        label: 'Pending Qty',
        uses_primary_attribute: 1,
        condition: function(data, props) {
            return props['docstatus'] == 1;
        },
    },
    {
        name: 'cancelled_qty',
        label: 'Cancelled Qty',
        uses_primary_attribute: 1,
        condition: function(data, props) {
            return props['docstatus'] == 1;
        },
        format: function(value) {
            return value || 0;
        }
    },
    {
        name: 'rate',
        label: 'Rate',
        uses_primary_attribute: 1,
    },
    {
        name: 'discount_percentage',
        label: 'Discount %',
    },
    {
        name: 'delivery_location',
        label: 'Delivery Location',
    },
    {
        name: 'delivery_date',
        label: 'Delivery Date',
    },
    {
        name: 'comments',
        label: 'Comments',
    },
]);

const args = ref({
    'docstatus': cur_frm.doc.docstatus
});

onMounted(() => {
    // console.log('new-item mounted');
    // this.create_lot_item_inputs();
    EventBus.$on("supplier_updated", new_supplier => {
        if (supplier.value !== new_supplier) {
            supplier.value = new_supplier;
            
        }
    })
    delivery_date.value = cur_frm.doc.po_date        
});

function update_status() {
    docstatus.value = cur_frm.doc.docstatus;
    args.value['docstatus'] = cur_frm.doc.docstatus;
}

function load_data(all_items) {
    items.value = all_items;
}

function updated(value) {
    EventBus.$emit('po_updated', true);
}

defineExpose({
	items,
    load_data,
    update_status,
});
// export default {
//     name: 'item',
//     components: {ItemLotFetcher},
//     data() {
//         return {
//             docstatus: 0,
//             items: [],
//             supplier: cur_frm.doc.supplier,
//             otherInputs: [
//                 {
//                     name: 'delivery_location',
//                     parent: 'delivery-location-control',
//                     df: {
//                         fieldtype: 'Link',
//                         fieldname: 'delivery_location',
//                         options: 'Supplier',
//                         label: 'Delivery Location',
//                         reqd: true,
//                     },
//                     query: function(data, inputs) {
//                         return {
//                             filters: {
//                                 is_company_location: inputs['deliver_to_supplier'].get_value() ? 0 : 1,
//                             }
//                         }
//                     }
//                 },
//                 {
//                     name: 'deliver_to_supplier',
//                     parent: 'delivery-location-control',
//                     df: {
//                         fieldtype: 'Check',
//                         fieldname: 'deliver_to_supplier',
//                         label: 'Deliver to Supplier',
//                     },
//                 },
//                 {
//                     name: 'delivery_date',
//                     parent: 'delivery-date-control',
//                     df: {
//                         fieldtype: 'Date',
//                         fieldname: 'delivery_date',
//                         label: 'Delivery Date',
//                         reqd: 1
//                     },
//                 },
//                 {
//                     name: 'discount_percentage',
//                     parent: 'discount-control',
//                     df: {
//                         fieldtype: 'Float',
//                         fieldname: 'discount_percentage',
//                         label: 'Discount %',
//                         default: 0,
//                         non_negative: 1,
//                         precision: "1"
//                     },
//                 },
//                 {
//                     name: 'comments',
//                     parent: 'comments-control',
//                     df: {
//                         fieldtype: 'Data',
//                         fieldname: 'comments',
//                         label: 'Comments',
//                     },
//                 },
//             ],
//             table_fields: [
//                 {
//                     name: 'pending_qty',
//                     label: 'Pending Qty',
//                     uses_primary_attribute: 1,
//                     condition: function(data, props) {
//                         return props['docstatus'] == 1;
//                     },
//                 },
//                 {
//                     name: 'cancelled_qty',
//                     label: 'Cancelled Qty',
//                     uses_primary_attribute: 1,
//                     condition: function(data, props) {
//                         return props['docstatus'] == 1;
//                     },
//                     format: function(value) {
//                         return value || 0;
//                     }
//                 },
//                 {
//                     name: 'rate',
//                     label: 'Rate',
//                     uses_primary_attribute: 1,
//                 },
//                 {
//                     name: 'discount_percentage',
//                     label: 'Discount %',
//                 },
//                 {
//                     name: 'delivery_location',
//                     label: 'Delivery Location',
//                 },
//                 {
//                     name: 'delivery_date',
//                     label: 'Delivery Date',
//                 },
//                 {
//                     name: 'comments',
//                     label: 'Comments',
//                 },
//             ],
//             args: {
//                 'docstatus': cur_frm.doc.docstatus
//             },
//         }
//     },
//     mounted() {
//         // console.log('new-item mounted');
//         // this.create_lot_item_inputs();
//         EventBus.$on("supplier_updated", supplier => {
//             if (this.supplier !== supplier) {
//                 this.supplier = supplier;
//             }
//         })
//     },
//     methods: {
//         update_status: function() {
//             this.docstatus = cur_frm.doc.docstatus;
//             this.args['docstatus'] = cur_frm.doc.docstatus;
//         },

//         load_data: function(items) {
//             this.items = items;
//         },

//         updated: function(value) {
//             EventBus.$emit('po_updated', true);
//         },
//     },
// }
</script>

<style scoped>
.new-item-form {
    border-style: solid;
    border-color: red;
    border-width: thin;
    border-radius: 10px;
    padding: 10px 10px 46px 10px;
    margin-top: 20px;
}
</style>
