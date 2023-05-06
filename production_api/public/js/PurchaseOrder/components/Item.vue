<template>
    <div class="item frappe-control">

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
                            <th>Discount %</th>
                            <th>Delivery Location</th>
                            <th>Delivery Date</th>
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
                                        <br>
                                        ({{ attr.secondary_qty }}<span v-if="j.secondary_uom">{{ ' ' + j.secondary_uom }}</span>)
                                    </span>
                                    <span v-if="docstatus==1">
                                        <br>
                                        Pending: {{ attr.pending_qty }}
                                        <br>
                                        Cancelled: {{ attr.cancelled_qty || 0 }}
                                    </span>
                                    <br>
                                    Rate: {{ attr.rate }}
                                </div>
                                <div v-else class="text-center">
                                    ---
                                </div>
                            </td>
                            <td>{{ j.discount_percentage }}</td>
                            <td>{{ j.delivery_location }}</td>
                            <td>{{ j.delivery_date }}</td>
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
                            <th v-if="docstatus==1">Pending Quantity</th>
                            <th v-if="docstatus==1">Cancelled Quantity</th>
                            <th>Rate</th>
                            <th>Discount %</th>
                            <th>Delivery Location</th>
                            <th>Delivery Date</th>
                            <th>Comments</th>
                        </tr>
                        <tr v-for="(j, item1_index) in i.items" :key="item1_index">
                            <td>{{ item1_index + 1 }}</td>
                            <td>{{ j.name }}</td>
                            <td>{{ j.lot }}</td>
                            <td v-for="attr in i.attributes" :key="attr">{{ j.attributes[attr] }}</td>
                            <td>
                                {{ j.values['default'].qty }}<span v-if="j.default_uom">{{ ' ' + j.default_uom}}</span>
                                <span v-if="j.values['default'].secondary_qty">
                                    <br>
                                    ({{ j.values['default'].secondary_qty }}<span v-if="j.secondary_uom">{{ ' ' + j.secondary_uom }}</span>)
                                </span>
                            </td>
                            <td v-if="docstatus==1">{{ j.values['default'].pending_qty }}</td>
                            <td v-if="docstatus==1">{{ j.values['default'].cancelled_qty || 0 }}</td>
                            <td>{{ j.values['default'].rate }}</td>
                            <td>{{ j.discount_percentage }}</td>
                            <td>{{ j.delivery_location }}</td>
                            <td>{{ j.delivery_date }}</td>
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
            <div class="row" v-if="cur_item.secondary_uom">
                <div class="col checkbox">
                    <label>
                        <span class="input-area"><input type="checkbox" autocomplete="off" class="input-with-feedback" v-model="secondary_quantity"></span>
                        <span class="label-area">Secondary Quantity</span>
                    </label>
                </div>
            </div>
            <div v-if="cur_item.item && cur_item.item != ''">
                <div class="d-flex flex-row" v-if="cur_item.primary_attribute">
                    <div class="m-1" v-for="(attr) in cur_item.primary_attribute_values" :key="attr">
                        <div>
                            <label>{{ attr }}</label>
                        </div>
                        <div>
                            <label class="small text-muted">
                                {{ item.default_uom || '' }}
                            </label>
                            <input class="form-control" type="number" min="0" v-model.number="item.values[attr]['qty']">
                        </div>
                        <div v-if="secondary_quantity">
                            <label class="small text-muted">
                                {{ item.secondary_uom }}
                            </label>
                            <input class="form-control" type="number" min="0.000" step="0.001" v-model.number="item.values[attr]['secondary_qty']">
                        </div>
                        <!-- <div>
                            <label class="small text-muted">
                                Rate
                            </label>
                            <input class="form-control" type="number" min="0.000" step="0.001" v-model.number="item.values[attr]['rate']">
                        </div> -->
                    </div>
                </div>
                <div class="row" v-else>
                    <div class="col col-md-6">
                        <label class="small">
                            {{ item.default_uom || 'Qty' }}
                        </label>
                        <input class="form-control" type="number" min="0" v-model.number="item.values['default']['qty']" required>
                    </div>
                    <div class="col col-md-6" v-if="secondary_quantity">
                        <label class="small text-muted">
                            {{ item.secondary_uom || '' }}
                        </label>
                        <input class="form-control" type="number" min="0.000" step="0.001" v-model.number="item.values['default']['secondary_qty']">
                    </div>
                    <!-- <div class="col" >
                        <label class="small text-muted">
                            Rate
                        </label>
                        <input class="form-control" type="number" min="0.000" step="0.001" v-model.number="item.values['default']['rate']">
                    </div> -->
                </div>
            </div>
            <div class="row">
                <div class="delivery-location-control col-md-3"></div>
                <div class="delivery-date-control col-md-3"></div>
                <div class="discount-control col-md-3"></div>
                <div class="comments-control col-md-3"></div>
            </div>
            <div>
                <button v-if="!is_edit" type="submit" class="btn btn-success pull-right">Add Item</button>
                <button v-if="is_edit" type="submit" class="btn btn-warning pull-right">Update Item</button>
                <button v-if="is_edit" type="button" @click.prevent="cancel_edit()" class="btn ">Cancel</button>
            </div>
        </form>
    </div>
</template>

<script>
import evntBus from '../../bus';

export default {
    name: 'item',
    data() {
        return {
            docstatus: 0,
            items: [],
            item: {
                name: "",
                lot: "",
                delivery_location: "",
                delivery_date: "",
                attributes: {},
                primary_attribute: "",
                values: {},
                default_uom: "",
		        secondary_uom: "",
                comments: "",
                discount_percentage: 0,
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
            secondary_quantity: false,
            is_edit: false,
            edit_index: -1,
            edit_index1: -1,
            cur_item_changed: false,
            supplier: cur_frm.doc.supplier,
        }
    },
    mounted() {
        console.log('new-item mounted');
        this.create_lot_item_inputs();
        evntBus.$on("supplier_updated", supplier => {
            if (this.supplier !== supplier) {
                this.supplier = supplier;
            }
        })
    },
    methods: {
        update_status: function() {
            this.docstatus = cur_frm.doc.docstatus;
        },

        load_data: function(items) {
            this.items = items;
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
            console.log('inside clear')
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

        set_lot_item_inputs: function(cur_item) {
            this.lot_input.set_value(this.item.lot);
            this.item_input.set_value(this.item.name);
            this.cur_item = cur_item;
        },

        get_lot_item_details: function() {
            if (!cur_frm.doc.supplier) {
                frappe.throw('Please set Supplier before adding items.')
            }
            if (cur_frm.doc.supplier !== this.supplier) {
                this.supplier = cur_frm.doc.supplier;
            }
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
                    delivery_location: cur_frm.doc.default_delivery_location || "",
                    delivery_date: "",
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
            this.create_item_delivery_inputs();
        },

        create_item_attribute_inputs: function(){
            if(!this.cur_item.item || this.cur_item.item == '') return;
            this.attribute_inputs = [];
            $(this.$el).find('.item-attribute-controls').html("");
            $(this.$el).find('.item-attribute-controls-right').html("");
            let i = 0;
            for(i = 0; i < this.cur_item.attributes.length; i++){
                let attribute = this.cur_item.attributes[i];
                let attribute_name = attribute.charAt(0).toUpperCase() + attribute.slice(1);
                let classname = '';
                if(i%2 == 0) classname = '.item-attribute-controls';
                else classname = '.item-attribute-controls-right';
                console.log($(this.$el).find(classname))
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
                    },
                    render_input: true,
                });
                this.attribute_inputs[i].set_value(this.item.attributes[attribute])
            }
        },

        create_item_delivery_inputs: function() {
            var me = this;
            if(!this.cur_item.item || this.cur_item.item == '') return;
            this.delivery_location_input = null;
            this.delivery_date_input = null;
            this.discount_input = null;
            this.comments_input = null;
            $(this.$el).find('.delivery-location-control').html("");
            $(this.$el).find('.delivery-date-control').html("");
            $(this.$el).find('.discount-control').html("");
            $(this.$el).find('.comments-control').html("");
            this.delivery_location_input = frappe.ui.form.make_control({
                parent: $(this.$el).find('.delivery-location-control'),
                df: {
                    fieldtype: 'Link',
                    options: 'Supplier',
                    label: 'Delivery Location',
                    get_query: function(){
                        return {
                            filters: {
                                is_company_location: me.deliver_to_supplier.get_value() ? 0 : 1,
                            }
                        }
                    },
                    reqd: true,
                },
                render_input: true,
            });
            this.deliver_to_supplier = frappe.ui.form.make_control({
                parent: $(this.$el).find('.delivery-location-control'),
                df: {
                    fieldtype: 'Check',
                    label: 'Deliver to Supplier',
                },
                render_input: true,
            });
            this.delivery_location_input.set_value(this.item.delivery_location)
            this.delivery_date_input = frappe.ui.form.make_control({
                parent: $(this.$el).find('.delivery-date-control'),
                df: {
                    fieldtype: 'Date',
                    label: 'Delivery Date',
                    reqd: 1
                },
                render_input: true,
            });
            this.delivery_date_input.set_value(this.item.delivery_date)
            this.discount_input = frappe.ui.form.make_control({
                parent: $(this.$el).find('.discount-control'),
                df: {
                    fieldtype: 'Float',
                    label: 'Discount %',
                    default: 0,
                    non_negative: 1,
                    precision: "1"
                },
                render_input: true,
            });
            this.discount_input.set_value(this.item.discount_percentage)
            this.comments_input = frappe.ui.form.make_control({
                parent: $(this.$el).find('.comments-control'),
                df: {
                    fieldtype: 'Data',
                    label: 'Comments',
                },
                render_input: true,
            });
            this.comments_input.set_value(this.item.comments)
        },

        get_item_attributes: function() {
            if(!this.attribute_inputs) return false;
            for(let i = 0; i < this.cur_item.attributes.length; i++){
                let attribute = this.cur_item.attributes[i];
                let value = this.attribute_inputs[i].get_value();
                if(!value) {
                    this.attribute_inputs[i].$input.select();
                    frappe.msgprint(__('Attribute '+ attribute + ' does not have a value'));
                    return false;
                }
                this.item.attributes[attribute] = value;
            }
            return true;
        },

        get_item_delivery_details: function() {
            if(!this.delivery_location_input) return false;
            if(!this.delivery_date_input) return false;
            if(!this.comments_input) return false;

            let location = this.delivery_location_input.get_value();
            if(!location) {
                this.delivery_location_input.$input.select();
                frappe.msgprint(__('Delivery Location does not have a value'));
                return false;
            }
            this.item.delivery_location = location;

            let date = this.delivery_date_input.get_value();
            if(!date) {
                this.delivery_date_input.$input.select();
                frappe.msgprint(__('Delivery Date does not have a value'));
                return false;
            }
            this.item.delivery_date = date;
            
            this.item.discount_percentage = this.discount_input.get_value();
            console.log(this.item.discount_percentage)
            this.item.comments = this.comments_input.get_value();
            return true;
        },

        get_item_group_index: function() {
            let index = -1;
            for(let i = 0; i < this.items.length; i++){
                if(!(this.items[i].attributes.sort().join(',') === this.cur_item.attributes.sort().join(','))) continue;
                if(!(this.items[i].primary_attribute === this.cur_item.primary_attribute)) continue;
                if(!(this.items[i].primary_attribute_values.sort().join(',') === this.cur_item.primary_attribute_values.sort().join(','))) continue;
                index = i;
                break;
            }
            return index;
        },

        clear_item_attribute_inputs: function() {
            if(!this.attribute_inputs) return;
            for(let i = 0; i < this.attribute_inputs.length; i++){
                this.attribute_inputs[i].set_value('');
            }
        },

        clear_item_delivery_inputs: function() {
            if(this.delivery_location_input) this.delivery_location_input.set_value('');
            if(this.delivery_date_input) this.delivery_date_input.set_value('');
            if(this.discount_input) this.discount_input.set_value('');
            if(this.comments_input) this.comments_input.set_value('');
        },
        
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
            this.clear_item_delivery_inputs();
            this.clear_item_values();
            if(!this.deto || force){
                this.clear_lot_item_inputs();
            }
        },

        add_item: function() {
            if(!this.get_item_attributes()) return;
            if(!this.get_item_delivery_details()) return;
            if(this.item.name != this.item_input.get_value()){
                frappe.msgprint(__('Item does not match'));
                this.clear_inputs(true);
                return;
            }
            if(this.is_edit){
                this.items[this.edit_index].items[this.edit_index1] = JSON.parse(JSON.stringify(this.item));
                this.cancel_edit();
                console.log("Updated PO Item")
                evntBus.$emit("po_updated", true);
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
            console.log("Added PO Item")
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
            console.log("Deleted PO Item")
            evntBus.$emit("po_updated", true);
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
            console.log(items, index, index1)
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
    },
}
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
