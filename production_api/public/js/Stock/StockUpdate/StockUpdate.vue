<template>
    <div>
        <item-lot-fetcher 
            :items="items"
            :other-inputs="otherInputs"
            :table-fields="table_fields"
            :allow-secondary-qty="true"
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
import ItemLotFetcher from '../../components/ItemLotFetch.vue';

import { ref, onMounted } from 'vue';

const docstatus = ref(cur_frm.doc.docstatus)
const items = ref([])
const can_create = ref(true)
const otherInputs = ref([
    // {
    //     name: 'remarks',
    //     parent: 'remarks-control',
    //     df: {
    //         fieldtype: 'Data',
    //         fieldname: 'remarks',
    //         label: 'Remarks',
    //         reqd: true,
    //     },
    // },
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
    },
])
const table_fields = ref([
    {
        name: 'rate',
        label: 'Rate',
        uses_primary_attribute: 1,
    },
    {
        name: 'available_stock',
        label: 'Available Stock',
        uses_primary_attribute: 1,
    },
    {
        name: "total_qty",
        label: "Total Qty",
    },
    // {
    //     name: 'remarks',
    //     label: 'Remarks',
    // },
    {
        name: 'received_type',
        label: 'Received Type',
    },
])
const args = ref({
    docstatus: cur_frm.doc.docstatus,
    can_edit: function() {
        return true;
    },
    can_create: function() {
        return can_create;
    },
    can_remove: function() {
        return true;
    },
    item_query: function() {
        return {filters: {"is_stock_item": 1}};
    }
})

onMounted(() => {
    if (cur_frm.doc.purpose == "Receive at Warehouse") {
        can_create.value = false;
    }
    EventBus.$on("purpose_updated", purpose => {
        if (purpose == "Receive at Warehouse") {
            can_create.value = false;
        } else {
            can_create.value = true;
        }
    })
})

function is_editable(field) {
    console.log(docstatus.value)
    console.log(field)
    console.log(cur_frm.doc.purpose)
    if (docstatus > 0) {
        return false;
    }
    if (field != 'qty' && cur_frm.doc.purpose == "Receive at Warehouse") {
        return false;
    }
    return true;
}

function update_status() {
    docstatus.value = cur_frm.doc.docstatus;
    args.value['docstatus'] = cur_frm.doc.docstatus;
}

function load_data(all_items) {
    all_items.forEach(element => {	
		if(element.primary_attribute){
			details = []
			element.items.forEach((row,index) => {
				details.push(row.values)
                let qty = 0;
                Object.keys(row.values).forEach((key, idx) => {
                    qty += row.values[key].qty;
                })
                row.total_qty = qty
			})
		}
		else{
			element.items.forEach((row,index) => {
				row['total_qty'] = row['values']['default']['qty']
			})
		}
	});
	items.value = all_items;
}

function get_items() {
    return items.value;
}

function updated(value) {
    EventBus.$emit("stock_updated", true);
}

defineExpose({
	items,
    load_data,
    update_status,
    get_items,
});
</script>