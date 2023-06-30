<template>
    <div>

        <table class="table table-sm table-bordered">
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
                                    <!-- <span v-if="attr.secondary_qty">
                                        <br>
                                        ({{ attr.secondary_qty }}<span v-if="j.secondary_uom">{{ ' ' + j.secondary_uom }}</span>)
                                    </span> -->
                                    <br>
                                    Rate: {{ attr.rate }}
                                </div>
                                <div v-else class="text-center">
                                    ---
                                </div>
                            </td>
                            <td>{{ j.comments }}</td>
                            <td v-if="docstatus==0">
                                <div class="pull-right cursor-pointer" @click="remove_item(item_index, item1_index)" v-html="frappe.utils.icon('delete', 'md')"></div>
                                <div class="pull-right cursor-pointer" @click="edit_item(item_index, item1_index)" v-html="frappe.utils.icon('edit', 'md', 'mr-1')"></div>
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
                            <th>Quantity</th>
                            <th>Rate</th>
                            <th>Comments</th>
                        </tr>
                        <tr v-for="(j, item1_index) in i.items" :key="item1_index">
                            <td>{{ item1_index + 1 }}</td>
                            <td>{{ j.name }}</td>
                            <td>{{ j.lot }}</td>
                            <td v-for="attr in i.attributes" :key="attr">{{ j.attributes[attr] }}</td>
                            <td>
                                {{ j.values['default'].qty }}<span v-if="j.default_uom">{{ ' ' + j.default_uom}}</span>
                                <!-- <span v-if="j.values['default'].secondary_qty">
                                    <br>
                                    ({{ j.values['default'].secondary_qty }}<span v-if="j.secondary_uom">{{ ' ' + j.secondary_uom }}</span>)
                                </span> -->
                            </td>
                            <td>{{ j.values['default'].rate }}</td>
                            <td>{{ j.comments }}</td>
                            <td v-if="docstatus==0">
                                <div class="pull-right cursor-pointer" @click="remove_item(item_index, item1_index)" v-html="frappe.utils.icon('delete', 'md')"></div>
                                <div class="pull-right cursor-pointer" @click="edit_item(item_index, item1_index)" v-html="frappe.utils.icon('edit', 'md', 'mr-1')"></div>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>

        <form v-if="docstatus==0" name="formp" class="form-horizontal" autocomplete="off" @submit.prevent="get_lot_item_details()">
            <div class="row">
                <div class="lot-control col-md-5"></div>
                <div class="item-control col-md-5"></div>
                <div class="col-md-2">
                    <button type="submit" class="btn btn-success">Fetch Item</button>
                </div>
            </div>
            <div class="row">
                <div class="col checkbox">
                    <label>
                        <span class="input-area"><input type="checkbox" autocomplete="off" class="input-with-feedback" v-model="deto"></span>
                        <span class="label-area">Use same item again</span>
                    </label>
                </div>
            </div>
        </form>
        <form name="formp" class="form-horizontal new-item-form" autocomplete="off" @submit.prevent="add_item()" v-show="docstatus==0 && !cur_item_changed && cur_item.item && cur_item.item != ''">
            <div class="row">
                <div class="item-attribute-controls col-md-6"></div>
                <div class="item-attribute-controls-right col-md-6"></div>
            </div>
            <div class="row">
                <div class="col checkbox">
                    <label>
                        <span class="input-area"><input type="checkbox" autocomplete="off" class="input-with-feedback" v-model="item.allow_zero_valuation_rate"></span>
                        <span class="label-area">Allow Zero Valuation Rate</span>
                    </label>
                </div>
            </div>
            <div v-if="cur_item.item && cur_item.item != ''">
                <div class="d-flex flex-row" v-if="cur_item.primary_attribute">
                    <div class="m-1" v-for="(attr, index) in cur_item.primary_attribute_values" :key="attr">
                        <div>
                            <label>{{ attr }}</label>
                        </div>
                        <div>
                            <label class="small text-muted">
                                {{ item.default_uom || 'Qty' }}
                            </label>
                            <input class="form-control" :ref="'qty_control_'+index" type="number" min="0" v-model.number="item.values[attr]['qty']">
                        </div>
                        <!-- <div v-if="secondary_quantity">
                            <label class="small text-muted">
                                {{ item.secondary_uom }}
                            </label>
                            <input class="form-control" type="number" min="0.000" step="0.001" v-model.number="item.values[attr]['secondary_qty']">
                        </div> -->
                        <div>
                            <label class="small text-muted">
                                Rate
                            </label>
                            <input class="form-control" type="number" min="0.000" step="0.001" v-model.number="item.values[attr]['rate']">
                        </div>
                    </div>
                </div>
                <div class="row" v-else>
                    <div class="col col-md-6">
                        <label class="small">
                            {{ item.default_uom || 'Qty' }}
                        </label>
                        <input class="form-control" ref="qty_control" type="number" min="0" v-model.number="item.values['default']['qty']" required>
                    </div>
                    <!-- <div class="col col-md-6" v-if="secondary_quantity">
                        <label class="small text-muted">
                            {{ item.secondary_uom || '' }}
                        </label>
                        <input class="form-control" type="number" min="0.000" step="0.001" v-model.number="item.values['default']['secondary_qty']">
                    </div> -->
                    <div class="col" >
                        <label class="small text-muted">
                            Rate
                        </label>
                        <input class="form-control" type="number" min="0.000" step="0.001" v-model.number="item.values['default']['rate']">
                    </div>
                </div>
            </div>
            <!-- <div class="row"> -->
                <!-- <div class="delivery-location-control col-md-3"></div>
                <div class="delivery-date-control col-md-3"></div>
                <div class="discount-control col-md-3"></div> -->
                <!-- <div class="comments-control col-md-6"></div> -->
            <!-- </div> -->
            <div>
                <button v-if="!is_edit" type="submit" class="btn btn-success pull-right">Add Item</button>
                <button v-if="is_edit" type="submit" class="btn btn-warning pull-right">Update Item</button>
                <button v-if="is_edit" type="button" @click.prevent="cancel_edit()" class="btn ">Cancel</button>
            </div>
        </form>
    </div>
</template>

<script>
import evntBus from '../../bus.js';
export default ({
    name: 'StockReconciliation',
    data() {
        return {
            docstatus: cur_frm.doc.docstatus,
            items: [],
            item: {
                name: "",
                lot: "",
                attributes: {},
                primary_attribute: "",
                values: {},
                default_uom: "",
		        secondary_uom: "",
                // comments: "",
            },
            cur_item: {
                item: "",
                attributes: [],
                primary_attribute: "",
                primary_attribute_values: [],
                default_uom: "",
		        secondary_uom: "",
            },
            deto: true,
            // secondary_quantity: false,
            is_edit: false,
            edit_index: -1,
            edit_index1: -1,
            cur_item_changed: false,
            // s_warehouse: null,
            // t_warehouse: null,
        };
    },
    mounted() {
        this.create_lot_item_inputs();
        // evntBus.$on("warehouse_updated", warehouse => {
        //     if (this.s_warehouse !== cur_frm.from_warehouse) {
        //         this.s_warehouse = cur_frm.from_warehouse;
        //     }
        //     if (this.t_warehouse !== cur_frm.to_warehouse) {
        //         this.t_warehouse = cur_frm.to_warehouse;
        //     }
        // })
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

        create_lot_item_inputs: function() {
            let me = this;
            $(this.$el).find('.lot-control').html("");
            this.lot_input = frappe.ui.form.make_control({
                parent: $(this.$el).find('.lot-control'),
                df: {
                    fieldtype: 'Link',
                    options: 'Lot',
                    label: 'Lot',
                    reqd: true,
                    onchange: () => {
                        me.onchange_lot_item();
                    }
                },
                render_input: true,
            });
            $(this.$el).find('.item-control').html("");
            this.item_input = frappe.ui.form.make_control({
                parent: $(this.$el).find('.item-control'),
                df: {
                    fieldtype: 'Link',
                    options: 'Item',
                    label: 'Item',
                    reqd: true,
                    onchange: () => {
                        me.onchange_lot_item();
                    }
                },
                render_input: true,
            });
        },

        onchange_lot_item: function(){
            if(!this.cur_item.item || this.cur_item.item == '') return;
            let cur_lot = this.lot_input.get_value();
            let cur_item = this.item_input.get_value();
            if (cur_lot != this.item.lot || (cur_item != this.item.name && cur_item != this.cur_item.item)) {
                this.cur_item_changed = true;
            } else {
                this.cur_item_changed = false;
            }
        },

        clear_lot_item_inputs: function() {
            this.lot_input.set_value('');
            this.item_input.set_value('');
            this.cur_item = {
                item: "",
                attributes: [],
                primary_attribute: "",
                primary_attribute_values: [],
                default_uom: "",
		        secondary_uom: "",
            };
        },

        get_lot_item_details: function() {
            if(!this.item_input.get_value()) return;
            if(!this.lot_input.get_value()) return;
            this.cur_item = {};
            this.secondary_quantity = false;
            var me = this;

            frappe.call({
                method: 'production_api.production_api.doctype.item.item.get_attribute_details',
                args: {
                    item_name: me.item_input.get_value()
                },
                callback: function(r) {
                    if(r.message) {
                        me.cur_item = r.message;
                        me.set_lot_item_details(r.message, null)
                    }
                }
            });
        },

        set_lot_item_details: function(item_details, item) {
            this.cur_item_changed = false;
            if(!item || Object.keys(item).length < 1){
                this.item = {
                    name: item_details.item,
                    lot: this.lot_input.get_value(),
                    attributes: {},
                    primary_attribute: item_details.primary_attribute,
                    values: {},
                    default_uom: item_details.default_uom,
                    secondary_uom: item_details.secondary_uom,
                    comments: "",
                };
                for(var i = 0; i < item_details.attributes.length; i++){
                    this.item.attributes[item_details.attributes[i]] = ""
                }
                if(item_details.primary_attribute){
                    for(var i = 0;i < item_details.primary_attribute_values.length; i++){
                        this.item.values[item_details.primary_attribute_values[i]] = {qty: 0, rate: 0}
                    }
                }
                else{
                    this.item.values['default'] = {qty: 0, rate: 0}
                }
            } else {
                this.item = item;
                this.set_lot_item_inputs(item_details);
            }
            this.create_item_attribute_inputs();
            // this.create_comments_inputs();
        },

        create_item_attribute_inputs: function(){
            if(!this.cur_item.item || this.cur_item.item == '') return;
            this.attribute_inputs = [];
            $(this.$el).find('.item-attribute-controls').html("");
            $(this.$el).find('.item-attribute-controls-right').html("");
            let i = 0;
            for(i = 0; i < this.cur_item.attributes.length; i++){
                let current_index = i;
                let attribute = this.cur_item.attributes[i];
                let attribute_name = attribute.charAt(0).toUpperCase() + attribute.slice(1);
                let classname = '';
                if(i%2 == 0) classname = '.item-attribute-controls';
                else classname = '.item-attribute-controls-right';
                let me = this;
                this.attribute_inputs[i] = frappe.ui.form.make_control({
                    parent: $(this.$el).find(classname),
                    df: {
                        fieldtype: 'Link',
                        options: 'Item Attribute Value',
                        label: attribute_name,
                        only_select: true,
                        get_query: function() {
                            return {
                                query: "production_api.production_api.doctype.item.item.get_item_attribute_values",
                                filters: {
                                    "item": me.cur_item.item,
                                    "attribute": attribute_name
                                }
                            };
                        },
                        reqd: true,
                        onchange: function() {
                            let df_me = this;
                            let value = df_me.get_value();
                            if (!value) return;
                            let args = {
                                'txt': value,
                                'doctype': 'Item Attribute Value',
                                query: "production_api.production_api.doctype.item.item.get_item_attribute_values",
                                filters: {
                                    "item": me.cur_item.item,
                                    "attribute": attribute_name
                                }
                            };
                            frappe.call({
                                type: "POST",
                                method: "frappe.desk.search.search_link",
                                no_spinner: true,
                                args: args,
                                callback: function (r) {
                                    if (r.results.length > 0) {
                                        // results has json of value and description
                                        // check if value is in results
                                        let value_exists = false;
                                        for (let index = 0; index < r.results.length; index++) {
                                            if (r.results[index].value == value) {
                                                value_exists = true;
                                                break;
                                            }
                                        }
                                        if (!value_exists) {
                                            df_me.set_value("");
                                        }
                                    }
                                    else {
                                        df_me.set_value("");
                                    }
                                }
                            });
                        }
                    },
                    render_input: true,
                });
                this.attribute_inputs[i].set_value(this.item.attributes[attribute])
            }
        },

        // create_comments_inputs: function() {
        //     var me = this;
        //     if(!this.cur_item.item || this.cur_item.item == '') return;
        //     this.comments_input = null;
        //     $(this.$el).find('.comments-control').html("");
        //     this.comments_input = frappe.ui.form.make_control({
        //         parent: $(this.$el).find('.comments-control'),
        //         df: {
        //             fieldtype: 'Data',
        //             label: 'Comments',
        //         },
        //         render_input: true,
        //     });
        //     this.comments_input.set_value(this.item.comments)
        // },

        get_item_attributes: function() {
            if(!this.attribute_inputs) return false;
            let attributes = [];
            let attribute_values = {};
            for (let i = 0; i < this.attribute_inputs.length; i++) {
                let attribute = this.attribute_inputs[i].df.label;
                attributes.push(attribute);
                let value = this.attribute_inputs[i].get_value();
                if (!value) {
                    this.attribute_inputs[i].$input.select();
                    frappe.show_alert({
                        message: __('Attribute ' + attribute + ' does not have a value'),
                        indicator: 'red'
                    });
                    return false;
                }
                attribute_values[attribute] = value;
            }
            if (!this.arrays_equal(attributes, this.cur_item.attributes)) {
                frappe.show_alert({
                    message: __('Attributes might have changed. Please try again'),
                    indicator: 'red'
                });
                return false;
            } else {
                this.item.attributes = {
                    ...this.item.attributes,
                    ...attribute_values
                }
            }
            return true;
        },

        // get_comments: function() {
        //     if(!this.comments_input) return false;
        //     this.item.comments = this.comments_input.get_value();
        //     return true;
        // },

        get_item_group_index: function() {
            let index = -1;
            for(let i = 0; i < this.items.length; i++){
                if (this.arrays_equal(this.items[i].attributes, this.cur_item.attributes) 
                    && this.items[i].primary_attribute === this.cur_item.primary_attribute
                    && this.arrays_equal(this.items[i].primary_attribute_values, this.cur_item.primary_attribute_values)) {
                    index = i;
                    break;
                }
            }
            return index;
        },

        // find if two arrays have the same elements, It can be in any order
        arrays_equal: function(a, b) {
            // duplicate the arrays to avoid changing the original
            var arr1 = a.concat([]), arr2 = b.concat([]);
            arr1.sort();arr2.sort();
            return JSON.stringify(arr1)===JSON.stringify(arr2);
        },

        clear_item_attribute_inputs: function() {
            if(!this.attribute_inputs) return;
            for(let i = 0; i < this.attribute_inputs.length; i++){
                this.attribute_inputs[i].set_value('');
            }
        },

        // clear_other_inputs: function() {
        //     if(this.comments_input) this.comments_input.set_value('');
        // },
        
        clear_item_values: function() {
            for(var i = 0; i < this.cur_item.attributes.length; i++){
                this.item.attributes[this.cur_item.attributes[i]] = ""
            }
            if(this.cur_item.primary_attribute){
                for(var i = 0;i < this.cur_item.primary_attribute_values.length; i++){
                    this.item.values[this.cur_item.primary_attribute_values[i]] = {qty: 0, rate: 0}
                }
            }
            else{
                this.item.values['default'] = {qty: 0, rate: 0}
            }
        },

        clear_inputs: function(force) {
            this.clear_item_attribute_inputs();
            // this.clear_other_inputs();
            this.clear_item_values();
            if(!this.deto || force){
                this.clear_lot_item_inputs();
            }
        },

        validate_item_values: function() {
            if(!this.cur_item.primary_attribute){
                if(this.item.values['default'].qty == 0){
                    this.$nextTick(() => {
                        this.$refs.qty_control.focus();
                    });
                    frappe.show_alert({
                        message: __('Quantity cannot be 0'),
                        indicator: 'red'
                    });
                    return false;
                }
            }
            else{
                let total_qty = 0;
                for(var i = 0; i < this.cur_item.primary_attribute_values.length; i++){
                    total_qty += this.item.values[this.cur_item.primary_attribute_values[i]].qty;
                }
                if(total_qty == 0){
                    this.$nextTick(() => {
                        this.$refs.qty_control_0[0].focus();
                    });
                    frappe.show_alert({
                        message: __('Quantity cannot be 0'),
                        indicator: 'red'
                    });
                    return false;
                }
            }
            return true;
        },

        add_item: function() {
            if(!this.get_item_attributes()) return;
            if (!this.validate_item_values()) return;
            // if(!this.get_comments()) return;
            if(this.item.name != this.item_input.get_value()){
                frappe.msgprint(__('Item does not match'));
                this.clear_inputs(true);
                return;
            }
            if(this.is_edit){
                this.items[this.edit_index].items[this.edit_index1] = JSON.parse(JSON.stringify(this.item));
                this.cancel_edit();
                evntBus.$emit("stock_updated", true);
                return;
            }
            let index = this.get_item_group_index();
            if(index == -1){
                this.items.push({
                    attributes: this.cur_item.attributes,
                    primary_attribute: this.cur_item.primary_attribute,
                    primary_attribute_values: this.cur_item.primary_attribute_values,
                    items: [JSON.parse(JSON.stringify(this.item))]
                });
            } else {
                this.items[index].items.push(JSON.parse(JSON.stringify(this.item)));
            }
            evntBus.$emit("po_updated", true);
            this.clear_inputs(false);
        },

        remove_item: function(index, index1) {
            if(this.is_edit){
                if(this.edit_index == index){
                    if(this.edit_index1 > index1){
                        this.edit_index1--;
                    }
                    else if(this.edit_index1 == index1){
                        this.cancel_edit();
                    }
                }
            }
            if(this.items[index].items.length == 1){
                if(this.is_edit){
                    if(this.edit_index == index){
                        this.cancel_edit();
                    }
                    else if(this.edit_index > index){
                        this.edit_index--;
                    }
                }
                this.items.splice(index, 1);
            } else {
                this.items[index].items.splice(index1, 1);
            }
            evntBus.$emit("po_updated", true);
        },

        set_lot_item_inputs: function(cur_item) {
            this.lot_input.set_value(this.item.lot);
            this.item_input.set_value(this.item.name);
            this.cur_item = cur_item;
        },

        edit_item: function(index, index1) {
            this.cur_item_changed = false
            if(!this.is_edit) this.is_edit = !this.is_edit;
            this.edit_index = index;
            this.edit_index1 = index1;
            let items = JSON.parse(JSON.stringify(this.items[index]))
            this.set_lot_item_details({
                item: items.items[index1].name,
                attributes: items.attributes,
                primary_attribute: items.primary_attribute,
                primary_attribute_values: items.primary_attribute_values,
                default_uom: items.items[index1].default_uom,
                secondary_uom: items.items[index1].secondary_uom,
            }, items.items[index1])
            this.lot_input.df.read_only = 1;
            this.item_input.df.read_only = 1;
            this.item_input.refresh();
            this.lot_input.refresh();
        },

        cancel_edit() {
            this.is_edit = !this.is_edit;
            this.edit_index = -1;
            this.edit_index1 = -1;
            this.clear_inputs(true);
            this.lot_input.df.read_only = 0;
            this.item_input.df.read_only = 0;
            this.item_input.refresh();
            this.lot_input.refresh();
        },
    }
})
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