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
            :lot_no="lot_no"
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
const lot_no = ref(cur_frm.doc.lot)

const otherInputs = ref([
    // {
    //     name: 'rate',
    //     parent: 'rate-control',
    //     df: {
    //         fieldtype: 'Float',
    //         fieldname: 'rate',
    //         label: 'Rate',
    //         reqd: 1,
    //     },
    // },
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
		name: 'total_qty',
		label: 'Total Qty',
	},
    // {
    //     name: 'cancelled_qty',
    //     label: 'Cancelled Qty',
    //     uses_primary_attribute: 1,
    //     condition: function(data, props) {
    //         return props['docstatus'] == 1;
    //     },
    //     format: function(value) {
    //         return value || 0;
    //     }
    // },
    {
        name: 'comments',
        label: 'Comments',
    },
    
]);
const args = ref({
    'docstatus': cur_frm.doc.docstatus,
});

onMounted(() => {
    EventBus.$on("supplier_updated", new_supplier => {
        if (supplier.value !== new_supplier) {
            supplier.value = new_supplier;
        }
    })
});

function update_status(val) {
    let doc_status = cur_frm.doc.docstatus;
    docstatus.value = doc_status;
    args.value['docstatus'] = doc_status;
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
