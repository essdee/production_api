<template>
    <div class="new-item-dialog">
        <div class="form-section p-2">
            <div class="row">
                <div class="col">
                    <div><label for="item" class="control-label">Item:</label></div>
                    <div>
                        <input class="form-control input-sm" id="item" type="text" v-model="item.item" placeholder="Enter Item" disabled>
                    </div>
                </div>
                <div class="default-location-control col"></div>
                <div class="default-date-control col"></div>
            </div>
            <div class="row" v-if="secondary_uom">
                <div class="col checkbox">
                    <label>
                        <span class="input-area"><input type="checkbox" autocomplete="off" class="input-with-feedback" v-model="secondary_quantity"></span>
                        <span class="label-area">Secondary Quantity</span>
                    </label>
                </div>
            </div>
        </div>

        <div class="form-section p-2">
            <table class="table table-sm table-bordered" v-if="item.variants && item.variants.length > 0">
                <tr>
                    <th>S.No.</th>
                    <th>Lot</th>
                    <th v-for="attr in Object.keys(item.variants[0].attributes)" :key="attr">{{ attr }}</th>
                    <th v-for="attr in Object.keys(item.variants[0].values)" :key="attr">{{ attr == 'default' ? 'Quantity' : attr }}</th>
                </tr>
                <tr v-for="(variant, index) in item.variants" :key="index">
                    <td>{{ index + 1 }}</td>
                    <td>{{ variant.lot }}</td>
                    <td v-for="attribute in variant.attributes" :key="attribute">{{ attribute }}</td>
                    <td v-for="attr in variant.values" :key="attr">
                        <div v-if="attr.qty">
                            {{ attr.qty + ' ' + default_uom}}
                            <span v-if="attr.secondary_qty">
                                <br>
                                ({{ attr.secondary_qty + ' ' + secondary_uom }})
                            </span>
                            <br>
                            Rate: {{ attr.rate }}
                        </div>
                        <div v-else class="text-center">---</div>
                    </td>
                    <td>
                        <button class="btn pull-right" @click="removeAt(index)" v-html="frappe.utils.icon('delete', 'xs')"></button>
                        <button class="btn pull-right" @click="edit(index)" v-html="frappe.utils.icon('edit', 'xs')"></button>
                    </td>
                </tr>
            </table>
        </div>

        <form class="form-section p-2" @submit.prevent="addVariant()">
            <div class="row">
                <div class="default-lot-control col-md-6"></div>
            </div>
            <div class="row">
                <div class="item-attribute-controls col-md-6"></div>
                <div class="item-attribute-controls-right col-md-6"></div>
            </div>
            <div class="d-flex flex-row" v-if="primary_attribute">
                <div class="m-1" v-for="(attr) in primary_attribute_values" :key="attr">
                    <div>
                        <label>{{ attr.attribute_value }}</label>
                    </div>
                    <div>
                        <label class="small text-muted">
                            {{ default_uom || '' }}
                        </label>
                        <input class="form-control" type="number" min="0" v-model.number="variant.values[attr.attribute_value]['qty']">
                    </div>
                    <div v-if="secondary_quantity">
                        <label class="small text-muted">
                            {{ secondary_uom }}
                        </label>
                        <input class="form-control" type="number" min="0.000" step="0.001" v-model.number="variant.values[attr.attribute_value]['secondary_qty']">
                    </div>
                    <div>
                        <label class="small text-muted">
                            Rate
                        </label>
                        <input class="form-control" type="number" min="0.000" step="0.001" v-model.number="variant.values[attr.attribute_value]['rate']">
                    </div>
                </div>
            </div>
            <div class="row" v-else>
                <div class="col">
                    <label class="small">
                        Qty
                    </label>
                    <input class="form-control" type="number" min="0" v-model.number="variant.values['default']['qty']" required>
                </div>
                <div class="col" v-if="secondary_quantity">
                    <label class="small text-muted">
                        Secondary Qty
                    </label>
                    <input class="form-control" type="number" min="0.000" step="0.001" v-model.number="variant.values['default']['secondary_qty']">
                </div>
                <div class="col" >
                    <label class="small text-muted">
                        Rate
                    </label>
                    <input class="form-control" type="number" min="0.000" step="0.001" v-model.number="variant.values['default']['rate']">
                </div>
            </div>
            <div>
                <button v-if="!is_edit" type="submit" class="btn btn-success pull-right">Add</button>
                <button v-if="is_edit" type="submit" class="btn btn-warning">Update</button>
                <button v-if="is_edit" type="button" @click.prevent="cancel_edit()" class="btn ">Cancel</button>
            </div>
        </form>
    </div>
</template>

<script>
export default {
    name: 'new-item-dialog',
    props: ['item', 'attributes', 'primary_attribute_values', 'primary_attribute', 'default_uom', 'secondary_uom'],
    data() {
        return {
            lot: {},
            variant: {
                attributes: {},
                values: {}
            },
            secondary_quantity: Boolean(this.secondary_uom),
            default_lot: '',
            attribute_inputs: [],
            default_lot_input: null,
            default_location_input: null,
            default_date_input: null,
            is_edit: false,
            edit_index: -1
        };
    },
    created() {
        console.log('Created Dialog');
        console.log(this.primary_attribute_values);
        this.newVariant();
        console.log(this.variant);
    },
    mounted() {
        console.log('Mounted Dialog');
        this.create_attribute_input();
        this.create_default_inputs();
    },
    methods: {
        create_attribute_input: function(){
            this.attribute_inputs = [];
            let i = 0;
            for(i = 0; i < this.attributes.length; i++){
                let attribute = this.attributes[i];
                let attribute_name = attribute.charAt(0).toUpperCase() + attribute.slice(1);
                let classname = '';
                if(i%2 == 0) classname = '.item-attribute-controls';
                else classname = '.item-attribute-controls-right';
                this.attribute_inputs[i] = frappe.ui.form.make_control({
                    parent: $(this.$el).find(classname),
                    df: {
                        fieldtype: 'Link',
                        options: 'Item Attribute Value',
                        label: attribute_name,
                        get_query: function() {
                            return {
                                filters: [
                                    ['Item Attribute Value', 'attribute_name', '=', attribute_name]
                                ]
                            };
                        },
                        reqd: 1
                    },
                    render_input: true,
                });
            }
            console.log(this.attribute_inputs[0]);
        },

        clear_attribute_input: function(){
            for(let i = 0; i < this.attribute_inputs.length; i++){
                this.attribute_inputs[i].set_value('');
            }
        },

        create_default_inputs: function() {
            this.default_location_input = frappe.ui.form.make_control({
                parent: $(this.$el).find('.default-location-control'),
                df: {
                    fieldtype: 'Link',
                    options: 'Location',
                    label: 'Default Delivery Location',
                    reqd: 1
                },
                render_input: true,
            });
            this.default_date_input = frappe.ui.form.make_control({
                parent: $(this.$el).find('.default-date-control'),
                df: {
                    fieldtype: 'Date',
                    label: 'Default Delivery Date',
                    reqd: 1
                },
                render_input: true,
            });
            this.default_lot_input = frappe.ui.form.make_control({
                parent: $(this.$el).find('.default-lot-control'),
                df: {
                    fieldtype: 'Link',
                    options: 'Lot',
                    label: 'Lot',
                    reqd: 1
                },
                render_input: true,
            });
            if(this.item.delivery_location){
                this.default_location_input.set_value(this.item.delivery_location);
            }
            if(this.item.delivery_date){
                this.default_date_input.set_value(this.item.delivery_date);
            }
        },

        newVariant: function() {
            this.variant = {
                lot: '',
                attributes: {},
                values: {}
            };
            console.log(this.primary_attribute);
            console.log(this.primary_attribute_values);
            if(this.primary_attribute && this.primary_attribute_values.length > 0) {
                this.variant['primary_attribute'] = this.primary_attribute;
                for(var i = 0; i < this.primary_attribute_values.length; i++) {
                    this.variant.values[this.primary_attribute_values[i]['attribute_value']] = {};
                }
            }
            else{
                this.variant.values['default'] = {};
            }
        },

        addVariant: function(){
            for(let i = 0; i < this.attributes.length; i++){
                let attribute = this.attributes[i];
                let value = this.attribute_inputs[i].get_value();
                if(!value) {
                    this.attribute_inputs[i].$input.select();
                    frappe.msgprint(__('Attribute '+ attribute + ' does not have a value'));
                    return;
                }
                this.variant.attributes[attribute] = value;
            }
            let value = this.default_lot_input.get_value();
            if(!value) {
                this.default_lot_input.$input.select();
                frappe.msgprint(__('Enter Lot to continue'));
                return;
            }
            this.variant.lot = value;
            if(this.is_edit){
                this.update_variant();
                return;
            }
            this.item.variants.push(this.variant);
            this.newVariant();
            this.clear_attribute_input();
            this.default_lot_input.$input.select();
        },

        update_variant: function() {
            this.item.variants[this.edit_index] = JSON.parse(JSON.stringify(this.variant));
            this.newVariant();
            this.clear_attribute_input();
            this.is_edit = false;
            this.edit_index = -1;
        },

        removeAt(index) {
            if(this.is_edit){
                if(this.edit_index > index){
                    this.edit_index--;
                }
                else if(this.edit_index == index){
                    this.cancel_edit();
                }
            }
            this.item.variants.splice(index, 1);
        },

        edit(index) {
            if(!this.is_edit) this.is_edit = !this.is_edit;
            this.edit_index = index;
            for(let i = 0; i < this.attributes.length; i++){
                let attribute = this.attributes[i];
                this.attribute_inputs[i].set_value(this.item.variants[index]['attributes'][attribute]);
            }
            this.default_lot_input.set_value(this.item.variants[index]['lot']);
            this.variant = JSON.parse(JSON.stringify(this.item.variants[index]));
        },

        cancel_edit() {
            this.is_edit = !this.is_edit;
            this.edit_index = -1;
            this.newVariant();
            this.clear_attribute_input();
        },

        saveitem(){
            console.log(this.item);
            let delivery_location = this.default_location_input.get_value();
            if(!delivery_location) {
                this.default_location_input.$input.select();
                frappe.msgprint(__('Enter Delivery Location to continue'));
                return;
            }
            this.item.delivery_location = delivery_location;
            let delivery_date = this.default_date_input.get_value();
            if(!delivery_date) {
                this.default_date_input.$input.select();
                frappe.msgprint(__('Enter Delivery date to continue'));
                return;
            }
            this.item.delivery_date = delivery_date;
            if(this.item.variants.length > 0) {
                return this.item;
            }
            return null;
        },
    }
}
</script>
