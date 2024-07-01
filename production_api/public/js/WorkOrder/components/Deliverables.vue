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
            @itemadded="updated"
            @itemupdated="updated"
            @itemremoved="updated">
        </item-lot-fetcher>
    </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

import EventBus from '../../bus';
import ItemLotFetcher from '../../components/ItemLotFetch.vue'

const docstatus = ref(0);
const items = ref([]);
const supplier = ref(cur_frm.doc.supplier);

const otherInputs = ref([
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
		name : 'pending_qty',
		label : 'Pending Qty',
		uses_primary_attribute: 1,
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
    EventBus.$on("supplier_updated", new_supplier => {
        if (supplier.value !== new_supplier) {
            supplier.value = new_supplier;
        }
    })
});

function update_status() {
    docstatus.value = cur_frm.doc.docstatus;
    args.value['docstatus'] = cur_frm.doc.docstatus;
}

function load_data(all_items) {
    items.value = all_items;
}

function updated(value) {
    EventBus.$emit('wo_updated', true);
}

defineExpose({
	items,
    load_data,
    update_status,
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
