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

<script>
import EventBus from '../../bus.js';
import ItemLotFetcher from '../../components/ItemLotFetcher.vue'

export default ({
    name: 'StockReconciliation',
    components: {ItemLotFetcher},
    data() {
        return {
            docstatus: cur_frm.doc.docstatus,
            items: [],
            other_inputs: [
                {
                    name: 'allow_zero_valuation_rate',
                    parent: 'zero-valuation-control',
                    df: {
                        fieldtype: 'Check',
                        fieldname: 'allow_zero_valuation_rate',
                        label: 'Allow Zero Valuation Rate',
                    },
                },
            ],
            table_fields: [
                {
                    name: 'rate',
                    label: 'Rate',
                    uses_primary_attribute: 1,
                },
            ],
            args: {
                docstatus: cur_frm.doc.docstatus,
                item_query: function() {
                    return {filters: {"is_stock_item": 1}};
                }
            },
            qty_fields: ["rate"],
        };
    },
    methods: {
        update_status: function() {
            this.docstatus = cur_frm.doc.docstatus;
        },

        load_data: function(items) {
            this.items = items;
        },

        get_items: function() {
            return this.items;
        },

        updated: function(value) {
            EventBus.$emit('stock_updated', true);
        },
    }
})
</script>