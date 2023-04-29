<template>
    <div class="frappe-control">
        <table v-if="docstatus!==0" class="table table-sm table-bordered">
            <tr v-for="(i, item_index) in items" :key="item_index">
                <td v-if="i.primary_attribute">
                    <table class="table table-sm table-bordered" v-if="i.items && i.items.length > 0">
                        <tr>
                            <th>S.No.</th>
                            <th>Item</th>
                            <th>Lot</th>
                            <th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
                            <th v-for="attr in i.primary_attribute_values" :key="attr">{{ attr }}</th>
                            <th>Comments</th>
                        </tr>
                        <tr v-for="(j, item1_index) in i.items" :key="item1_index">
                            <td>{{ item1_index + 1 }}</td>
                            <td>{{ j.name }}</td>
                            <td>{{ j.lot }}</td>
                            <td v-for="attr in i.attributes" :key="attr">{{ j.attributes[attr] }}</td>
                            <td v-for="attr in j.values" :key="attr">
                                <div v-if="attr.qty">
                                    {{ attr.received }}<span v-if="j.default_uom">{{ ' ' + j.default_uom }}</span>
                                    <span v-if="attr.secondary_qty">
                                            ({{ attr.secondary_received }}<span v-if="j.secondary_uom">{{ ' ' + j.secondary_uom }}</span>)
                                    </span>
                                    <!-- <input class="form-control" type="number" v-model="attr.received" label="Qty"/>
                                    <input class="form-control" v-if="attr.secondary_qty" type="number" v-model="attr.secondary_received" label="Secondary Qty"/> -->
                                </div>
                                <div v-else class="text-center">
                                    ---
                                </div>
                            </td>
                            <td>{{ j.comments }}</td>
                        </tr>
                    </table>
                </td>
                <td v-else>
                    <table class="table table-sm table-bordered" v-if="i.items && i.items.length > 0">
                        <tr>
                            <th>S.No.</th>
                            <th>Item</th>
                            <th>Lot</th>
                            <th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
                            <th>Received Quantity</th>
                            <th>Comments</th>
                        </tr>
                        <tr v-for="(j, item1_index) in i.items" :key="item1_index">
                            <td>{{ item1_index + 1 }}</td>
                            <td>{{ j.name }}</td>
                            <td>{{ j.lot }}</td>
                            <td v-for="attr in i.attributes" :key="attr">{{ j.attributes[attr] }}</td>
                            <td>
                                {{ j.values['default'].received }}<span v-if="j.default_uom">{{ ' ' + j.default_uom}}</span>
                                <span v-if="j.values['default'].secondary_received">
                                    <br>
                                    ({{ j.values['default'].secondary_received }}<span v-if="j.secondary_uom">{{ ' ' + j.secondary_uom }}</span>)
                                </span>
                            </td>
                            <!-- <td>
                                <input class="form-control" type="number" v-model="j.values['default'].received" placeholder="0" min="0" :max="j.values['default'].qty" />
                                <input class="form-control" v-if="j.values['default'].secondary_qty" type="number" min="0" :max="j.values['default'].secondary_qty" v-model="j.values['default'].secondary_received" label="Secondary Qty"/>
                            </td> -->
                            <td>{{ j.comments }}</td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
        <table v-else-if="against_id" class="table table-sm table-bordered">
            <tr v-for="(i, item_index) in items" :key="item_index">
                <td v-if="i.primary_attribute">
                    <table class="table table-sm table-bordered" v-if="i.items && i.items.length > 0">
                        <tr>
                            <th>S.No.</th>
                            <th>Item</th>
                            <th>Lot</th>
                            <th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
                            <th v-for="attr in i.primary_attribute_values" :key="attr">{{ attr }}</th>
                            <th>Comments</th>
                        </tr>
                        <tr v-for="(j, item1_index) in i.items" :key="item1_index">
                            <td>{{ item1_index + 1 }}</td>
                            <td>{{ j.name }}</td>
                            <td>{{ j.lot }}</td>
                            <td v-for="attr in i.attributes" :key="attr">{{ j.attributes[attr] }}</td>
                            <td v-for="attr in j.values" :key="attr">
                                <div v-if="attr.qty">
                                    {{ attr.qty }}<span v-if="j.default_uom">{{ ' ' + j.default_uom }}</span>
                                    <span v-if="attr.secondary_qty">
                                            ({{ attr.secondary_qty }}<span v-if="j.secondary_uom">{{ ' ' + j.secondary_uom }}</span>)
                                    </span>
                                    <form>
                                        <input class="form-control" type="number" v-model.number="attr.received"/>
                                        <input class="form-control" v-if="attr.secondary_qty" type="number" v-model.number="attr.secondary_received"/>
                                    </form>
                                </div>
                                <div v-else class="text-center">
                                    ---
                                </div>
                            </td>
                            <td>
                                <input class="form-control" type="text" v-model="j.comments"/>
                            </td>
                        </tr>
                    </table>
                </td>
                <td v-else>
                    <table class="table table-sm table-bordered" v-if="i.items && i.items.length > 0">
                        <tr>
                            <th>S.No.</th>
                            <th>Item</th>
                            <th>Lot</th>
                            <th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
                            <th>Pending Quantity</th>
                            <th>Received Quantity</th>
                            <th>Comments</th>
                        </tr>
                        <tr v-for="(j, item1_index) in i.items" :key="item1_index">
                            <td>{{ item1_index + 1 }}</td>
                            <td>{{ j.name }}</td>
                            <td>{{ j.lot }}</td>
                            <td v-for="attr in i.attributes" :key="attr">{{ j.attributes[attr] }}</td>
                            <td>
                                {{ j.values['default'].pending_qty }}<span v-if="j.default_uom">{{ ' ' + j.default_uom}}</span>
                                <span v-if="j.values['default'].secondary_qty">
                                    <br>
                                    ({{ j.values['default'].secondary_qty }}<span v-if="j.secondary_uom">{{ ' ' + j.secondary_uom }}</span>)
                                </span>
                            </td>
                            <td>
                                <form>
                                    <input class="form-control" type="number" v-model.number="j.values['default'].received" placeholder="0" min="0"/>
                                    <input class="form-control" v-if="j.values['default'].secondary_qty" type="number" min="0" v-model.number="j.values['default'].secondary_received"/>
                                </form>
                            </td>
                            <td>
                                <input class="form-control" type="text" v-model="j.comments"/>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
        <div v-else>
            Please Select a {{ against }}
        </div>
    </div>
</template>

<script>
import evntBus  from '../../bus';

export default {
    name: 'grnitem',
    data() {
        return {
            docstatus: 0,
            items: [],
            supplier: null,
            against: null,
            against_id: null,
            skip_watch: false,
        }
    },
    mounted() {
        console.log('new-grn-item mounted');
        evntBus.$on("update_grn_details", data => {
            this.load_data(data);
        })
    },
    methods: {
        update_status: function() {
            this.docstatus = cur_frm.doc.docstatus;
        },

        load_data: function(data, skip_watch=false) {
            if (data) {
                // Only update the values which are present in the data object
                for (let key in data) {
                    if (this.hasOwnProperty(key)) {
                        this[key] = data[key];
                    }
                }
                if (data.hasOwnProperty("against_id") && !skip_watch) {
                    this.against_id_changed();
                }
                if (data.hasOwnProperty("items")) {
                    this.skip_watch = skip_watch;
                }
            }
        },

        get_purchase_order_items: function() {
            let me = this;
            frappe.call({
                method: "production_api.production_api.doctype.purchase_order.purchase_order.get_purchase_order_items",
                args: {
                    "purchase_order": me.against_id
                },
                callback: function(r) {
                    if (r.message) {
                        me.items = r.message;
                    }
                }
            });
        },

        clear_items: function() {
            this.items = [];
        },

        against_id_changed: function() {
            if (this.against_id) {
                if (this.against == "Purchase Order") {
                    this.get_purchase_order_items();
                }
            } else {
                this.clear_items();
            }
        }
    },
    watch: {
        items: {
            handler(newVal, oldVal) {
                if (this.skip_watch) {
                    this.skip_watch = false;
                    return;
                }
                evntBus.$emit("grn_updated", true);
            },
            deep: true
        }
    }
}
</script>