<template>
    <div>
        <item-lot-fetcher 
            :items="items"
            :other-inputs="other_inputs"
            :table-fields="table_fields"
            :allow-secondary-qty="false"
            :args="args"
            :edit="docstatus == 0"
            :qty-fields="qty_fields"
            :validate-qty="false"
            @itemadded="updated"
            @itemupdated="updated"
            @itemremoved="updated">
        </item-lot-fetcher>
    </div>
</template>

<script setup>
import EventBus from '../../bus.js';
import ItemLotFetcher from '../../components/ItemLotFetch.vue';
import {ref} from 'vue';

const docstatus = ref(cur_frm.doc.docstatus)
const items = ref([])
const other_inputs = ref([
    {
        name: 'allow_zero_valuation_rate',
        parent: 'zero-valuation-control',
        df: {
            fieldtype: 'Check',
            fieldname: 'allow_zero_valuation_rate',
            label: 'Allow Zero Valuation Rate',
        },
    },
    {
        name: 'make_qty_zero',
        parent: 'make-qty-zero',
        df: {
            fieldtype: 'Check',
            fieldname: 'make_qty_zero',
            label: 'Make Qty Zero',
        },
    },
])
const table_fields = ref([
    {
        name: 'rate',
        label: 'Rate',
        uses_primary_attribute: 1,
    },
])
const args = ref({
    docstatus: cur_frm.doc.docstatus,
    item_query: function() {
        return {filters: {"is_stock_item": 1}};
    }
})
const qty_fields = ref(["rate"])

function update_status() {
    docstatus.value = cur_frm.doc.docstatus;
}

function load_data(i) {
    items.value = i;
}

function get_items() {
    return items.value;
}

function updated(value) {
    EventBus.$emit('stock_updated', true);
}

defineExpose({
	items,
    load_data,
    update_status,
    get_items,
})
</script>