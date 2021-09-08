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
                <!-- <div class="default-lot-control col">
                    <div><label for="lot" class="control-label">Default Lot:</label></div>
                    <div>
                        <input class="form-control input-sm" id="lot" type="text" v-model="default_lot" placeholder="Enter Lot">
                    </div>
                </div> -->
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
                    <th v-for="attribute in attributes" :key="attribute">{{ attribute }}</th>
                    <th v-for="attr in primary_attribute_values" :key="attr.idx">{{ attr.attribute_value }}</th>
                    <th v-if="!primary_attribute">Quantity</th>
                </tr>
                <tr v-for="(i, index) in item.variants" :key="index">
                    <td>{{ index + 1 }}</td>
                    <td v-for="attribute in attributes" :key="attribute">{{ i.attributes[attribute] }}</td>
                    <td class="cursor-pointer" v-for="attr in primary_attribute_values" :key="attr" @click.prevent="show_item_details_dialog(item.item, attr, i.values[attr.attribute_value])">{{ i.values[attr.attribute_value]['qty'] }}</td>
                    <td class="cursor-pointer" v-if="!primary_attribute" @click.prevent="show_item_details_dialog(item.item, '', i.values['default'])">{{ i.values['default']['qty'] }}</td>
                    <td class="">
                        <button class="btn pull-right" @click="removeAt(index)" v-html="frappe.utils.icon('delete', 'xs')"></button>
                        <button class="btn pull-right" @click="edit(index)" v-html="frappe.utils.icon('edit', 'xs')"></button>
                    </td>
                </tr>
            </table>
        </div>

        <form class="form-section p-2" @submit.prevent="addVariant()">
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
                        <input class="form-control" type="number" min="0.000" step="0.001" v-model.number="variant.values[attr.attribute_value]['sec_qty']">
                    </div>
                    <div>
                        <label class="small text-muted">
                            Rate
                        </label>
                        <input class="form-control" type="number" min="0.000" step="0.001" v-model.number="variant.values[attr.attribute_value]['rate']">
                    </div>
                    <button type="button" class="btn mt-2" 
                    :class="variant.values[attr.attribute_value] && variant.values[attr.attribute_value].mapping_qty == variant.values[attr.attribute_value].qty?'btn-success':'btn-warning'" 
                    @click.prevent="showlotdialog(attr.attribute_value)" tabindex="-1">
                    Delivery and Lot Mapping
                    </button>
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
                <button type="button" class="btn mt-2" 
                :class="variant.values['default'] && variant.values['default'].mapping_qty == variant.values['default'].qty?'btn-success':'btn-warning'" 
                @click.prevent="showlotdialog('default')" tabindex="-1">Delivery and Lot Mapping</button>
            </div>
            <div>
                <button v-if="!is_edit" type="submit" class="btn btn-success">Add</button>
                <button v-if="is_edit" type="submit" class="btn btn-warning">Update</button>
                <button v-if="is_edit" type="button" @click.prevent="cancel_edit()" class="btn ">Cancel</button>
            </div>
        </form>
        <form>
            <div class="default-lot-control"></div>
            <div class="default-location-control"></div>
            <div class="default-date-control"></div>
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
            default_value_inputs: [],
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
    },
    methods: {
        create_attribute_input: function(){
            this.attribute_inputs = [];
            for(let i = 0; i < this.attributes.length; i++){
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
        create_default_inputs: function(){
            this.default_value_inputs = [];
            this.default_value_inputs[0] = frappe.ui.form.make_control({
                parent: $(this.$el).find('.default-lot-control'),
                df: {
                    fieldtype: 'Link',
                    options: 'Lot',
                    label: 'Lot',
                    reqd: 1
                },
                render_input: true,
            });
            this.default_value_inputs[1] = frappe.ui.form.make_control({
                parent: $(this.$el).find('.default-location-control'),
                df: {
                    fieldtype: 'Link',
                    options: 'Location',
                    label: 'Location',
                    reqd: 1
                },
                render_input: true,
            });
            this.default_value_inputs[2] = frappe.ui.form.make_control({
                parent: $(this.$el).find('.default-date-control'),
                df: {
                    fieldtype: 'Date',
                    label: 'Date',
                    reqd: 1
                },
                render_input: true,
            });
        },
        clear_default_inputs: function(){
            for(let i = 0; i < this.default_value_inputs.length; i++){
                this.default_value_inputs[i].set_value('');
            }
        },
        set_defaults: function(){
            // Used to set lot and delivery details to current variant

        },
        newVariant: function() {
            this.variant = {
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
                    frappe.msgprint(__('Attribute '+ attribute + ' does not have a value'));
                    return;
                }
                this.variant.attributes[attribute] = value;
            }
            if(this.is_edit){
                this.update_variant();
                return;
            }
            this.item.variants.push(this.variant);
            this.newVariant();
            this.clear_attribute_input();
        },
        update_variant: function() {
            this.item.variants[this.edit_index] = this.variant;
            this.newVariant();
            this.clear_attribute_input();
            this.is_edit = false;
            this.edit_index = -1;
        },
        showlotdialog: function(attr) {
            var me = this;
            this.lotdialog = new frappe.ui.Dialog({
                title: __('Delivery and Lot Details'),
                static: true,
                primary_action_label: 'Save',
                primary_action(values) {
                    console.log(values);
                    if(!me.validate_lot_details(attr, values.lot_details) || !me.validate_delivery_details(attr, values.delivery_details)) return;
                    me.variant.values[attr]['lot_mapping'] = values.lot_details;
                    me.variant.values[attr].delivery_mapping = values.delivery_details;
                    me.variant.values[attr].mapping_qty = me.variant.values[attr].qty;
                    me.lotdialog.hide();
                },
                secondary_action_label: 'Cancel',
                secondary_action(values) {
                    me.lotdialog.hide();
                },
                fields: [
                    {
                        fieldtype: "Section Break",
                    },
                    {
                        fieldtype: "Table",
                        fieldname: "lot_details",
                        label: __("Lot Details"),
                        in_place_edit: true,
                        get_data: () => {
                            if(!this.variant.values[attr].lot_mapping) return [];
                            return JSON.parse(JSON.stringify(this.variant.values[attr].lot_mapping));
                        },
                        fields: [
                            {
                                fieldtype: "Link",
                                fieldname: "lot",
                                options: "Lot",
                                label: __("Lot"),
                                read_only: 0,
                                in_list_view: 1,
                                reqd: 1,
                            },
                            {
                                fieldtype: "Float",
                                fieldname: "qty",
                                label: __("Qty"),
                                read_only: 0,
                                in_list_view: 1,
                                reqd: 1,
                            },
                        ]

                    },
                    {
                        fieldtype: "Section Break",
                    },
                    {
                        fieldtype: 'Table',
                        fieldname: 'delivery_details',
                        label: "Delivery Details",
                        in_place_edit: true,
						get_data: () => {
                            if(!this.variant.values[attr].delivery_mapping) return [];
                            return JSON.parse(JSON.stringify(this.variant.values[attr].delivery_mapping));
						},
                        fields: [
                            {
                                fieldtype: 'Link',
                                fieldname: 'location',
                                default: 0,
                                options: 'Location',
                                read_only: 0,
                                in_list_view: 1,
                                reqd: 1,
                                label: __('Location'),
                            },
                            {
                                fieldtype: 'Date',
                                fieldname: 'date',
                                default: 0,
                                read_only: 0,
                                in_list_view: 1,
                                reqd: 1,
                                label: __('Date'),
                            },
                            {
                                fieldtype: 'Float',
                                fieldname: 'qty',
                                default: 0,
                                read_only: 0,
                                in_list_view: 1,
                                reqd: 1,
                                label: __('Qty'),
                            },
                        ],
                    }
                ]
            });
            this.lotdialog.show();
            this.lotdialog.$wrapper.find('.modal-dialog').css("max-width", "900px");
        },
        updatevariantlotdetails: function(lot_details) {
            console.log(lot_details);
            this.variant.values[lot_details.attr]['lot_mapping'] = lot_details.lot_mapping;
            console.log(this.variant);
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
            if(this.item.variants.length > 0) {
                return this.item;
            }
            return null;
        },
        show_item_details_dialog: function(item_name, attr, data) {
            var me = this;
            let fields = [
                {
                    fieldtype: 'Data',
                    fieldname: "qty",
                    label: 'Qty',
                    read_only: 1
                },
                {fieldtype:'Column Break'},
                {
                    fieldtype: 'Data',
                    fieldname: "rate",
                    label: 'Rate',
                    read_only: 1
                },
                {fieldtype:'Section Break'},
                {
                    fieldtype: 'Table',
                    fieldname: "lot_details",
                    label: __("Lot Details"),
                    in_place_edit: true,
                    cannot_add_rows: true,
                    cannot_delete_rows: true,
                    data: data.lot_mapping,
                    get_data: () => {
                        if(!data.lot_mapping) return [];
                        return data.lot_mapping;
                    },
                    fields: [
                        {
                            fieldtype: "Read Only",
                            fieldname: "lot",
                            options: "Lot",
                            label: __("Lot"),
                            read_only: 0,
                            in_list_view: 1,
                            reqd: 1,
                        },
                        {
                            fieldtype: "Read Only",
                            fieldname: "qty",
                            label: __("Qty"),
                            read_only: 0,
                            in_list_view: 1,
                            reqd: 1,
                        },
                    ],
                },
                {
                    fieldtype: 'Table',
                    fieldname: "delivery_details",
                    label: __("Delivery Details"),
                    in_place_edit: true,
                    cannot_add_rows: true,
                    cannot_delete_rows: true,
                    data: data.delivery_mapping,
                    get_data: () => {
                        if(!data.delivery_mapping) return [];
                        return data.delivery_mapping;
                    },
                    fields: [
                        {
                                fieldtype: 'Read Only',
                                fieldname: 'location',
                                default: 0,
                                options: 'Location',
                                read_only: 1,
                                in_list_view: 1,
                                reqd: 1,
                                label: __('Location'),
                            },
                            {
                                fieldtype: 'Read Only',
                                fieldname: 'date',
                                default: 0,
                                read_only: 1,
                                in_list_view: 1,
                                reqd: 1,
                                label: __('Date'),
                            },
                            {
                                fieldtype: 'Read Only',
                                fieldname: 'qty',
                                default: 0,
                                read_only: 1,
                                in_list_view: 1,
                                reqd: 1,
                                label: __('Qty'),
                            },
                    ],
                },
            ];
            var d = new frappe.ui.Dialog({
                title: item_name + attr,
                fields: fields,
                secondary_action_label: 'Cancel',
                secondary_action(values) {
                    d.hide();
                }
            });
            d.set_values({
                'qty': data.qty,
                'rate': data.rate,
            });
            d.show();
        },
        validate_lot_details: function(attr, lot_details){
            if(!lot_details || lot_details.length < 1) return false;
            let total_qty = 0;
            for(let i = 0; i < lot_details.length; i++){
                total_qty += lot_details[i]['qty'];
            }
            if(total_qty != this.variant.values[attr]['qty']){
                frappe.msgprint(__('Total Qty in Lot Details must be equal to Qty'));
                return false;
            }
            return true;
        },
        validate_delivery_details: function(attr, delivery_details){
            if(!delivery_details || delivery_details.length < 1) return false;
            let total_qty = 0;
            for(let i = 0; i < delivery_details.length; i++){
                total_qty += delivery_details[i]['qty'];
            }
            if(total_qty != this.variant.values[attr]['qty']){
                frappe.msgprint(__('Total Qty in Delivery Details must be equal to Qty'));
                return false;
            }
            return true;
        },
    }
}
</script>
