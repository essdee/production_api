<template>
    <div>
        <item-lot-fetcher 
            :items="items"
            :other-inputs="other_inputs"
            :table-fields="table_fields"
            :allow-secondary-qty="false"
            :args="args"
            :edit="docstatus == 0"
            :validate-qty="true"
            @itemadded="updated"
            @itemupdated="updated"
            @itemremoved="updated">
        </item-lot-fetcher>
    </div>
</template>

<script setup>
import EventBus from '../../bus.js';
import ItemLotFetcher from '../../components/ItemLotFetch.vue'

import {ref} from 'vue';

const docstatus = ref(cur_frm.doc.docstatus);
const items = ref([])
const other_inputs = ref([
    {
        name: 'warehouse',
        parent: 'warehouse-control',
        df: {
            fieldtype: 'Link',
            options: 'Supplier',
            label: 'Warehouse',
            reqd: true,
        },
    },
    {
        name: 'to_lot',
        parent: 'to-lot-control',
        df: {
            fieldtype: 'Link',
            label: 'Lot',
            options: 'Lot',
            reqd: true,
        },
    },
    {
        name: 'received_type',
        parent: 'received_type-control',
        df: {
            fieldtype: 'Link',
            fieldname: 'received_type',
            label: 'Received Type',
            options:"GRN Item Type",
            reqd: true,
        },
    }
]);
const table_fields = ref([
    {
        name: 'rate',
        label: 'Rate',
        uses_primary_attribute: 1,
    },
    {
        name: 'warehouse',
        label: 'Warehouse',
    },
    {
        name: 'to_lot',
        label: 'To Lot',
    },
    {
        name:"received_type",
        label:"Received Type",
    }
]);
const args = ref({
    docstatus: cur_frm.doc.docstatus,
    item_query: function() {
        return {filters: {"is_stock_item": 1}};
    }
});

function update_status() {
    docstatus.value = cur_frm.doc.docstatus;
}

function load_data(i) {
    console.log("loading data1", i)
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
});
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