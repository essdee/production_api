<template>
    <div>
        <item-lot-fetcher 
            :items="items"
            :other-inputs="otherInputs"
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

<script>
import EventBus from '../../bus.js';
import ItemLotFetcher from '../../components/ItemLotFetcher.vue'

export default ({
    name: 'StockEntry',
    components: {ItemLotFetcher},
    data() {
        let me = this;
        return {
            docstatus: cur_frm.doc.docstatus,
            items: [],
            can_create: true,
            otherInputs: [
                {
                    name: 'remarks',
                    parent: 'remarks-control',
                    df: {
                        fieldtype: 'Data',
                        fieldname: 'remarks',
                        label: 'Remarks',
                        reqd: true,
                    },
                },
            ],
            table_fields: [
                {
                    name: 'rate',
                    label: 'Rate',
                    uses_primary_attribute: 1,
                },
                {
                    name: 'remarks',
                    label: 'Remarks',
                },
            ],
            args: {
                docstatus: cur_frm.doc.docstatus,
                can_edit: function() {
                    return true;
                },
                can_create: function() {
                    return me.can_create;
                },
                can_remove: function() {
                    return true;
                },
                item_query: function() {
                    return {filters: {"is_stock_item": 1}};
                }
            }
        };
    },
    mounted() {
        if (cur_frm.doc.purpose == "Receive at Warehouse") {
            this.can_create = false;
        }
        EventBus.$on("purpose_updated", purpose => {
            if (purpose == "Receive at Warehouse") {
                this.can_create = false;
            } else {
                this.can_create = true;
            }
        })
    },
    methods: {
        is_editable: function(field) {
            console.log(this.docstatus)
            console.log(field)
            console.log(cur_frm.doc.purpose)
            if (this.docstatus > 0) {
                return false;
            }
            if (field != 'qty' && cur_frm.doc.purpose == "Receive at Warehouse") {
                return false;
            }
            return true;
        },

        update_status: function() {
            this.docstatus = cur_frm.doc.docstatus;
            this.args['docstatus'] = cur_frm.doc.docstatus;
        },

        load_data: function(items) {
            this.items = items;
        },

        get_items: function() {
            return this.items;
        },

        updated: function(value) {
            EventBus.$emit("stock_updated", true);
        }
    }
})
</script>