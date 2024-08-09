<template>
    <div ref="root">
        <!-- <button @click="printHelp">help</button>
        {{ sample_doc }} -->
        <table class="table table-sm table-bordered">
            <tr v-for="(i, item_index) in items" :key="item_index">
                <td v-if="i.primary_attribute">
                    <table class="table table-sm table-bordered" v-if="i.items && i.items.length > 0">
                        <tr>
                            <th>S.No.</th>
                            <th>Item</th>
                            <th>Lot</th>
                            <th v-for="attr in i.attributes" :key="attr">{{ attr }}</th>
                            <th v-if="has_additional_parameter(i)">Additional Parameters</th>
                            <th v-for="attr in i.primary_attribute_values" :key="attr">{{ attr }}</th>
                            <th v-for="a in other_table_fields" :key="a.name">{{ a.label }}</th>
                            <th v-if="edit"></th>
                        </tr>
                        <tr v-for="(j, item1_index) in i.items" :key="item1_index">
                            <td>{{ item1_index + 1 }}</td>
                            <td>{{ j.name }}</td>
                            <td>{{ j.lot }}</td>
                            <td v-for="attr in i.attributes" :key="attr">{{ j.attributes[attr] }}</td>
                            <td v-if="has_additional_parameter(i)">
                                <p v-for="(parameter, p_index) in j.additional_parameters" :key="p_index">
                                    {{ parameter.additional_parameter_key }} : {{ parameter.additional_parameter_value }}
                                </p>
                            </td>
                            <td v-for="(attr, key) in j.values" :key="key">
                                <div v-if="attr.qty">
                                    {{ attr.qty }}<span v-if="j.default_uom">{{ ' ' + j.default_uom }}</span>
                                    <span v-if="allowSecondaryQty && attr.secondary_qty">
                                        <br>
                                        ({{ attr.secondary_qty }}<span v-if="j.secondary_uom">{{ ' ' + j.secondary_uom }}</span>)
                                    </span>
                                    <span v-for="a in table_qty_fields" :key="a.name">
                                        <br>
                                        {{ a.label }}: {{ a.format ? a.format(attr[a.name]) : attr[a.name] }}
                                    </span>
                                </div>
                                <div v-else class="text-center">
                                    ---
                                </div>
                            </td>
                            <td v-for="a in other_table_fields" :key="a.name">{{ a.format ? a.format(j[a.name]) : j[a.name] }}</td>
                            <td v-if="edit">
                                <div v-if="can_remove" class="pull-right cursor-pointer" @click="remove_item(item_index, item1_index)" v-html="frappe.utils.icon('delete', 'md')"></div>
                                <div v-if="can_edit" class="pull-right cursor-pointer" @click="edit_item(item_index, item1_index)" v-html="frappe.utils.icon('edit', 'md', 'mr-1')"></div>
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
                            <th v-if="has_additional_parameter(i)">Additional Parameters</th>
                            <th>Quantity</th>
                            <th v-for="a in table_qty_fields" :key="a.name">{{ a.label }}</th>
                            <th v-for="a in other_table_fields" :key="a.name">{{ a.label }}</th>
                            <th v-if="edit"></th>
                        </tr>
                        <tr v-for="(j, item1_index) in i.items" :key="item1_index">
                            <td>{{ item1_index + 1 }}</td>
                            <td>{{ j.name }}</td>
                            <td>{{ j.lot }}</td>
                            <td v-for="attr in i.attributes" :key="attr">{{ j.attributes[attr] }}</td>
                            <td v-if="has_additional_parameter(i)">
                                <span v-for="(parameter, p_index) in j.additional_parameters" :key="p_index">
                                    {{ parameter.additional_parameter_key }} : {{ parameter.additional_parameter_value }} <br>
                                </span>
                            </td>
                            <td>
                                {{ j.values['default'].qty }}<span v-if="j.default_uom">{{ ' ' + j.default_uom}}</span>
                                <span v-if="allowSecondaryQty && j.values['default'].secondary_qty">
                                    <br>
                                    ({{ j.values['default'].secondary_qty }}<span v-if="j.secondary_uom">{{ ' ' + j.secondary_uom }}</span>)
                                </span>
                            </td>
                            <td v-for="a in table_qty_fields" :key="a.name">{{ a.format ? a.format(j.values['default'][a.name]) : j.values['default'][a.name] }}</td>
                            <td v-for="a in other_table_fields" :key="a.name">{{ a.format ? a.format(j[a.name]) : j[a.name] }}</td>
                            <td v-if="edit">
                                <div v-if="can_remove" class="pull-right cursor-pointer" @click="remove_item(item_index, item1_index)" v-html="frappe.utils.icon('delete', 'md')"></div>
                                <div v-if="can_edit" class="pull-right cursor-pointer" @click="edit_item(item_index, item1_index)" v-html="frappe.utils.icon('edit', 'md', 'mr-1')"></div>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>

        <form v-show="can_create && edit" name="formp" class="form-horizontal" autocomplete="off" @submit.prevent="get_lot_item_details()">
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

        <form name="formp" class="form-horizontal new-item-form" autocomplete="off" @submit.prevent="add_item()" v-show="edit && !cur_item_changed && cur_item.item && cur_item.item != ''">
            <div v-show="cur_item.dependent_attribute" class="row">
                <div class="dependent-attribute-controls col-md-6"></div>
            </div>
            <div class="row">
                <div class="item-attribute-controls col-md-6"></div>
                <div class="item-attribute-controls-right col-md-6"></div>
            </div>
            <div class="row" v-if="allowSecondaryQty && cur_item.secondary_uom">
                <div class="col checkbox">
                    <label>
                        <span class="input-area"><input type="checkbox" autocomplete="off" class="input-with-feedback" v-model="secondary_quantity"></span>
                        <span class="label-area">Secondary Quantity</span>
                    </label>
                </div>
            </div>
            <div v-if="cur_item.item && cur_item.item != '' && show_qty_fields">
                <div class="d-flex flex-row" v-if="cur_item.primary_attribute">
                    <div class="m-1" v-for="(attr, index) in cur_item.primary_attribute_values" :key="attr">
                        <div>
                            <label>{{ attr }}</label>
                        </div>
                        <div>
                            <label class="small text-muted">
                                {{ item.default_uom || '' }}
                            </label>
                            <input class="form-control" :ref="'qty_control_'+index" type="number" min="0" v-model.number="item.values[attr]['qty']">
                        </div>
                        <div v-if="allowSecondaryQty && secondary_quantity">
                            <label class="small text-muted">
                                {{ item.secondary_uom }}
                            </label>
                            <input class="form-control" type="number" min="0.000" step="0.001" v-model.number="item.values[attr]['secondary_qty']">
                        </div>
                        <div v-if="has_qty_field('rate')">
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
                        <input class="form-control" ref="qty_control" type="number" min="0.000" step="0.001" v-model.number="item.values['default']['qty']" required>
                    </div>
                    <div class="col col-md-6" v-if="allowSecondaryQty && secondary_quantity">
                        <label class="small text-muted">
                            {{ item.secondary_uom || '' }}
                        </label>
                        <input class="form-control" type="number" min="0.000" step="0.001" v-model.number="item.values['default']['secondary_qty']">
                    </div>
                    <div v-if="has_qty_field('rate')" class="col">
                        <label class="small text-muted">
                            Rate
                        </label>
                        <input class="form-control" type="number" min="0.000" step="0.001" v-model.number="item.values['default']['rate']">
                    </div>
                </div>
            </div>

            <div class="row" v-if="enableAdditionalParameter">
                <div class="additional-parameter-controls col-md-6"></div>
                <div class="additional-parameter-controls-right col-md-6"></div>
            </div>

            <div class="row" v-if="other_inputs">
                <div v-for="i in other_inputs" :class="[i, other_fields_class]"></div>
            </div>
            <div>
                <button v-if="!is_edit" type="submit" class="btn btn-success pull-right">Add Item</button>
                <button v-if="is_edit" type="submit" class="btn btn-warning pull-right">Update Item</button>
                <button v-if="is_edit" type="button" @click.prevent="cancel_edit()" class="btn ">Cancel</button>
            </div>
        </form>
    </div>
</template>

<script setup>
    import { ref, onMounted, computed, nextTick } from 'vue'

    const root = ref(null);

    const props = defineProps(['items', 'edit', 'otherInputs', 'tableFields', 'allowSecondaryQty', 'qtyFields', 'args', 'validateQty', 'enableAdditionalParameter','validate']);
    const emit = defineEmits(['itemupdated', 'itemadded', 'itemremoved'])
    const item = ref({
        name: "",
        lot: "",
        attributes: {},
        primary_attribute: "",
        values: {},
        default_uom: "",
        secondary_uom: "",
    });
    const cur_item = ref({
        item: "",
        attributes: [],
        primary_attribute: "",
        primary_attribute_values: [],
        default_uom: "",
        secondary_uom: "",
    });
    const secondary_quantity = ref(false)
    const is_edit = ref(false)
    const edit_index = ref(-1)
    const edit_index1 = ref(-1)
    const deto = ref(true)
    const cur_item_changed = ref(false)
    const sample_doc = ref({})
    const cur_dependent_attribute_value = ref(null)
    // const frappe = frappe

    let lot_input = null;
    let item_input = null;
    let attribute_inputs = null;
    let other_input_controls = null;
    let additional_parameter_inputs = null;
    let dependent_attribute_input = null;


    onMounted(() => {
        console.log('new-item mounted');
        create_lot_item_inputs();
    });

    const can_create = computed(() => {
        let flag = true;
        if (props.args && props.args.hasOwnProperty('can_create')) {
            if (props.args.can_create instanceof Function) {
                flag = Boolean(props.args.can_create());
            } else {
                flag = Boolean(props.args.can_create);
            }
        }
        return flag;
    });
    const can_edit = computed(() => {
        let flag = true;
        if (props.args && props.args.hasOwnProperty('can_edit')) {
            if (props.args.can_edit instanceof Function) {
                flag = Boolean(props.args.can_edit());
            } else {
                flag = Boolean(props.args.can_edit);
            }
        }
        return flag;
    });
    const can_remove = computed(() => {
        let flag = true;
        if (props.args && props.args.hasOwnProperty('can_remove')) {
            if (props.args.can_remove instanceof Function) {
                flag = Boolean(props.args.can_remove());
            } else {
                flag = Boolean(props.args.can_remove);
            }
        }
        return flag;
    });

    const show_qty_fields = function() {
        if (!cur_item.value.dependent_attribute) return true;
        return Boolean(cur_dependent_attribute_value.value)
    }

    const other_inputs = computed(() => {
        let x = [];
        if (!props.otherInputs) return x;
        for (let i = 0; i < props.otherInputs.length; i++) {
            if (!x.includes(props.otherInputs[i].parent)) {
                x.push(props.otherInputs[i].parent);
            }
        }
        return x;
    });
    const table_qty_fields = computed(() => {
        let x = [];
        let out = [];
        if (props.tableFields) {
            for (let i = 0; i < props.tableFields.length; i++) {
                let valid = true;
                if (props.tableFields[i].condition) {
                    valid = props.tableFields[i].condition(props.items, props.args)
                }
                if (valid && !x.includes(props.tableFields[i].name) && props.tableFields[i].uses_primary_attribute) {
                    x.push(props.tableFields[i].name);
                    out.push({...props.tableFields[i]})
                }
            }
        }
        return out;
    });
    const other_table_fields = computed(() => {
        let x = [];
        let out = [];
        if (props.tableFields) {
            for (let i = 0; i < props.tableFields.length; i++) {
                let valid = true;
                if (props.tableFields[i].condition) {
                    valid = props.tableFields[i].condition(props.items, props.args)
                }
                if (valid && !x.includes(props.tableFields[i].name) && !props.tableFields[i].uses_primary_attribute) {
                    x.push(props.tableFields[i].name);
                    out.push({...props.tableFields[i]})
                }
            }
        }
        return out;
    });
    const other_fields_class = computed(() => {
        let cl = "col";
        if (other_inputs) {
            if (other_inputs.length != 0) {
                let l = 12 / other_inputs.length;
                if (l >= 6) {
                    cl = "col-md-6";
                } else if (l == 4) {
                    cl = "col-md-4";
                } else {
                    cl = "col-md-3";
                }
            }
        }
        return cl;
    });


    function printHelp() {
        // console.log(this)
    }

    function has_qty_field(field) {
        return props.qtyFields && props.qtyFields.includes(field);
    }

    function has_additional_parameter(item) {
        return props.enableAdditionalParameter && item.additional_parameters && item.additional_parameters.length;
    }

    function create_lot_item_inputs() {
        let el = root.value;
        console.log("in lot inputs", frappe, $(el))
        $(el).find('.lot-control').html("");
        lot_input = frappe.ui.form.make_control({
            parent: $(el).find('.lot-control'),
            df: {
                fieldtype: 'Link',
                fieldname: 'lot',
                options: 'Lot',
                label: 'Lot',
                reqd: true,
                get_query: function() {
                    if (props.args && props.args.hasOwnProperty('lot_query') && props.args.lot_query instanceof Function) {
                        return props.args.lot_query() || {};
                    }
                    return {}
                },
                onchange: () => {
                    onchange_lot_item();
                }
            },
            doc: sample_doc.value,
            render_input: true,
        });
        
        console.log("Lot Input", lot_input)
        $(el).find('.item-control').html("");
        item_input = frappe.ui.form.make_control({
            parent: $(el).find('.item-control'),
            df: {
                fieldtype: 'Link',
                fieldname: 'item',
                options: 'Item',
                label: 'Item',
                reqd: true,
                get_query: function() {
                    if (props.args && props.args.hasOwnProperty('item_query') && props.args.item_query instanceof Function) {
                        return props.args.item_query() || {};
                    }
                    return {}
                },
                onchange: () => {
                    onchange_lot_item();
                }
            },
            doc: sample_doc.value,
            render_input: true,
        });
    }

    function onchange_lot_item(){
        if(!cur_item.value.item || cur_item.value.item == '') return;
        let lot_value = lot_input.get_value();
        let item_value = item_input.get_value();
        if (lot_value != item.value.lot || (item_value != item.value.name && item_value != cur_item.value.item)) {
            cur_item_changed.value = true;
        } else {
            cur_item_changed.value = false;
        }
    }

    function clear_lot_item_inputs() {
        lot_input.set_value('');
        item_input.set_value('');
        cur_item.value = {
            item: "",
            attributes: [],
            primary_attribute: "",
            primary_attribute_values: [],
            default_uom: "",
            secondary_uom: "",
        };
    }

    function set_lot_item_inputs(cur_item1) {
        lot_input.set_value(item.value.lot);
        item_input.set_value(item.value.name);
        cur_item.value = cur_item1;
    }

    function get_lot_item_details() {
        // if (!cur_frm.doc.supplier) {
        //     frappe.throw('Please set Supplier before adding items.')
        // }
        // if (cur_frm.doc.supplier !== supplier) {
        //     supplier = cur_frm.doc.supplier;
        // }
        if(!item_input.get_value()) return;
        if(!lot_input.get_value()) return;
        cur_item.value = {};
        secondary_quantity.value = false;

        frappe.call({
            method: 'production_api.production_api.doctype.item.item.get_attribute_details',
            args: {
                item_name: item_input.get_value()
            },
            callback: function(r) {
                if(r.message) {
                    cur_item.value = r.message;
                    set_lot_item_details(r.message, null)
                }
            }
        });
    }

    function set_lot_item_details(item_details, item1) {
        cur_item_changed.value = false;
        if(!item1 || Object.keys(item1).length < 1){
            item.value = {
                name: item_details.item,
                lot: lot_input.get_value(),
                delivery_location: cur_frm.doc.default_delivery_location || "",
                delivery_date: "",
                attributes: {},
                primary_attribute: item_details.primary_attribute,
                dependent_attribute: item_details.dependent_attribute,
                values: {},
                default_uom: item_details.default_uom,
                secondary_uom: item_details.secondary_uom,
                comments: "",
                additional_parameters: item_details.additional_parameters,
            };
            for(var i = 0; i < item_details.attributes.length; i++){
                item.value.attributes[item_details.attributes[i]] = ""
            }
            if(item_details.primary_attribute){
                for(var i = 0;i < item_details.primary_attribute_values.length; i++){
                    item.value.values[item_details.primary_attribute_values[i]] = {qty: 0, rate: 0}
                }
            } else {
                item.value.values['default'] = {qty: 0, rate: 0}
            }
            if(item_details.dependent_attribute){
                item.value.attributes[item_details.dependent_attribute] = ""
            }
        } else {
            item.value = item1;
            set_lot_item_inputs(item_details);
        }
        if (item_details.dependent_attribute) { 
            create_item_dependent_attribute_input();
        } else {
            create_item_attribute_inputs();
            if (props.enableAdditionalParameter) {
                create_additional_parameter_inputs();
            }
            if (props.otherInputs) {
                createOtherInputs();
            }
        }
    }

    function get_attribute_field(attribute, attribute_name, default_value, classname, on_change) {
        let $el = root.value;
        if (!classname) {
            classname = '';
            if(index%2 == 0) classname = '.item-attribute-controls';
            else classname = '.item-attribute-controls-right';
        }
        let field = frappe.ui.form.make_control({
            parent: $($el).find(classname),
            df: {
                fieldtype: 'Link',
                fieldname: attribute_name,
                options: 'Item Attribute Value',
                label: attribute_name,
                only_select: true,
                get_query: function() {
                    return {
                        query: "production_api.production_api.doctype.item.item.get_item_attribute_values",
                        filters: {
                            "item": cur_item.value.item,
                            "attribute": attribute_name
                        }
                    };
                },
                reqd: true,
                onchange: function() {
                    let df_me = this;
                    let value = df_me.get_value();
                    if (!value) {
                        if (on_change) {
                            on_change(value);
                        }
                        return;
                    };
                    let args = {
                        'txt': value,
                        'doctype': 'Item Attribute Value',
                        query: "production_api.production_api.doctype.item.item.get_item_attribute_values",
                        filters: {
                            "item": cur_item.value.item,
                            "attribute": attribute_name
                        }
                    };
                    frappe.call({
                        type: "POST",
                        method: "frappe.desk.search.search_link",
                        no_spinner: true,
                        args: args,
                        callback: function (r) {
                            if (r.message && r.message.length > 0) {
                                // results has json of value and description
                                // check if value is in results
                                let value_exists = false;
                                for (let i = 0; i < r.message.length; i++) {
                                    if (r.message[i].value == value) {
                                        value_exists = true;
                                        break;
                                    }
                                }
                                if (!value_exists) {
                                    df_me.set_value("");
                                }
                                if (on_change) {
                                    on_change(value);
                                }
                            } else {
                                df_me.set_value("");
                            }
                        }
                    });
                }
            },
            doc: sample_doc,
            render_input: true,
        });
        field.set_value(default_value)
        return field;
    };

    function create_item_dependent_attribute_input() {
        dependent_attribute_input = null;
        let $el = root.value;
        $($el).find('.dependent-attribute-controls').html("");
        if (item.value.dependent_attribute) {
            let attribute = item.value.dependent_attribute;
            let attribute_name = attribute.charAt(0).toUpperCase() + attribute.slice(1);
            let default_value = item.value.attributes[attribute];
            dependent_attribute_input = get_attribute_field(attribute, attribute_name, default_value, '.dependent-attribute-controls', (value) => {
                if (value == cur_dependent_attribute_value.value) {
                    return;
                }

                if (!value) {
                    // remove all other fields
                    clear_dependent_attribute_inputs();
                } else {
                    let d_attr_values = cur_item.value.dependent_attribute_details.attr_list[value]
                    if (!d_attr_values) return;
                    let attributes = d_attr_values.attributes
                    item.value.default_uom = d_attr_values.uom
                    create_item_attribute_inputs(attributes, 1);
                    if (props.enableAdditionalParameter) {
                        create_additional_parameter_inputs();
                    }
                    if (props.otherInputs) {
                        createOtherInputs();
                    }
                }
                cur_dependent_attribute_value.value = value;
            })
            if (default_value) {
                let d_attr_values = cur_item.value.dependent_attribute_details.attr_list[default_value]
                if (!d_attr_values) return;
                let attributes = d_attr_values.attributes
                item.value.default_uom = d_attr_values.uom
                create_item_attribute_inputs(attributes, 1);
                if (props.enableAdditionalParameter) {
                    create_additional_parameter_inputs();
                }
                if (props.otherInputs) {
                    createOtherInputs();
                }
            } else {
                clear_dependent_attribute_inputs();
            }

        }
    }

    function create_item_attribute_inputs(attributes = null, start_index = 0){
        if(!cur_item.value.item || cur_item.value.item == '') return;
        attribute_inputs = [];
        let $el = root.value;
        $($el).find('.item-attribute-controls').html("");
        $($el).find('.item-attribute-controls-right').html("");
        if (!attributes || attributes.length == 0) {
            attributes = cur_item.value.attributes;
        }
        if (cur_item.value.primary_attribute) {
            attributes = attributes.filter((v) => {
                if (v == cur_item.value.primary_attribute) return false;
                if (v == cur_item.value.dependent_attribute) return false;
                return true;
            })
        }
        for(let i = 0; i < attributes.length; i++){
            let attribute = attributes[i];
            let attribute_name = attribute.charAt(0).toUpperCase() + attribute.slice(1);
            let classname = '';
            if(i % 2 == 0) classname = '.item-attribute-controls';
            else classname = '.item-attribute-controls-right';
            attribute_inputs[i] = get_attribute_field(attribute, attribute_name, item.value.attributes[attribute], classname, null);
        }
    }

    function create_additional_parameter_inputs(){
        if(!cur_item.value.item || cur_item.value.item == '') return;
        additional_parameter_inputs = [];
        let $el = root.value;
        $($el).find('.additional-parameter-controls').html("");
        $($el).find('.additional-parameter-controls-right').html("");
        for(let i = 0; i < cur_item.value.additional_parameters.length; i++){
            let current_index = i;
            let additional_parameter = cur_item.value.additional_parameters[i];
            let key = additional_parameter.additional_parameter_key;
            let value = additional_parameter.additional_parameter_value;
            
            let classname = '';
            if(i%2 == 0) classname = '.additional-parameter-controls';
            else classname = '.additional-parameter-controls-right';
            additional_parameter_inputs[i] = frappe.ui.form.make_control({
                parent: $($el).find(classname),
                df: {
                    fieldtype: 'Link',
                    fieldname: key + '_parameter',
                    options: 'Additional Parameter Value',
                    label: key,
                    get_query: function() {
                        return {
                            filters: {
                                "key": key,
                            }
                        };
                    },
                    get_route_options_for_new_doc: function(field) {
                        return {
                            key: key,
                        }
                    },
                    reqd: true,
                },
                doc: sample_doc.value,
                render_input: true,
            });
            additional_parameter_inputs[i].set_value(item.value.additional_parameters[i].additional_parameter_value || value || '')
        }
    }
    
    function createOtherInputs() {
        if(!cur_item.value.item || cur_item.value.item == '') return;
        if (!props.otherInputs) return;
        let $el = root.value;
        for (let i = 0;i < other_inputs.value.length; i++) {
            let data = other_inputs.value[i];
            let parent_class = '.' + data
            $($el).find(parent_class).html("");
        }
        other_input_controls = {};
        for (let i=0; i < props.otherInputs.length ;i++) {
            let data = props.otherInputs[i];
            let parent_class = '.' + data.parent
            if (data['query']) {
                data.df['get_query'] = function() {
                    return data.query(item.value, other_input_controls)
                }
            }
            other_input_controls[data.name] = frappe.ui.form.make_control({
                parent: $($el).find(parent_class),
                df: data.df,
                doc: sample_doc.value,
                render_input: true,
            });
           
            if (data.df.fieldtype == 'Date' && item.value[data.name] == "None") {
                item.value[data.name] = null;
            }
            if(data.df.default){
                other_input_controls[data.name].set_value(data.df.default)
            }
            other_input_controls[data.name].set_value(item.value[data.name])
        }
    }
    
    function get_item_attributes() {
        if(!attribute_inputs) return false;
        let attributes = [];
        let attribute_values = {};
        let dependent_attribute = null;
        let dependent_attribute_value = null;
        if (cur_item.value.dependent_attribute) {
            let attribute = dependent_attribute_input.df.label;
            let value = dependent_attribute_input.get_value();
            attributes.push(attribute);
            if (!value) {
                dependent_attribute_input.$input.select();
                frappe.msgprint(__('Attribute ' + attribute + ' does not have a value'));
                return false;
            }
            attribute_values[attribute] = value
            dependent_attribute = attribute;
            dependent_attribute_value = value;
        }
        for (let i = 0; i < attribute_inputs.length; i++) {
            let attribute = attribute_inputs[i].df.label;
            attributes.push(attribute);
            let value = attribute_inputs[i].get_value();
            if (!value) {
                attribute_inputs[i].$input.select();
                frappe.msgprint(__('Attribute ' + attribute + ' does not have a value'));
                return false;
            }
            attribute_values[attribute] = value;
        }
        let attr_list = cur_item.value.attributes;
        if (cur_item.value.dependent_attribute) {
            let d_attr_values = cur_item.value.dependent_attribute_details.attr_list[dependent_attribute_value]
            if (!d_attr_values) return false;
            attr_list = d_attr_values.attributes;
            attr_list = attr_list.filter((v) => {
                return v !== cur_item.value.primary_attribute
            })
            attr_list.push(dependent_attribute);
        }
        if (!arrays_equal(attributes, attr_list)) {
            frappe.msgprint(__('Attributes might have changed. Please try again'));
            return false;
        } else {
            item.value.attributes = {
                ...attribute_values
            }
        }
        return true;
    }
    
    function get_additional_parameters() {
        if(!additional_parameter_inputs) return false;
        let attributes = [];
        let attribute_values = [];
        for (let i = 0; i < additional_parameter_inputs.length; i++) {
            let attribute = additional_parameter_inputs[i].df.label;
            attributes.push(attribute);
            let value = additional_parameter_inputs[i].get_value();
            if (!value) {
                additional_parameter_inputs[i].$input.select();
                frappe.msgprint(__('Additional Parameter ' + attribute + ' does not have a value'));
                return false;
            }
            attribute_values.push({
                additional_parameter_key: attribute,
                additional_parameter_value: value,
            });
        }
        item.value.additional_parameters = attribute_values
        return true;
    }
    
    function get_other_details() {
        if(!other_input_controls) return false;
        for (let i = 0; i < props.otherInputs.length; i++) {
            let data = props.otherInputs[i];
            let label = data.df.label;
            let value = other_input_controls[data.name].get_value();
            if (data.df.reqd && !value) {
                other_input_controls[data.name].$input.select();
                frappe.msgprint(__(label + ' does not have a value'));
                return false;
            }
            item.value[data.name] = value;
        }
        return true;
    }
    function get_item_group_index() {
        let index = -1;
        for(let i = 0; i < props.items.length; i++){
            if (arrays_equal(props.items[i].attributes, cur_item.value.attributes) 
                && props.items[i].primary_attribute === cur_item.value.primary_attribute
                && arrays_equal(props.items[i].primary_attribute_values, cur_item.value.primary_attribute_values)
                && has_additional_parameter(props.items[i]) == has_additional_parameter(cur_item.value)) {
                index = i;
                break;
            }
        }
        return index;
    }

    // find if two arrays have the same elements, It can be in any order
    function arrays_equal(a, b) {
        // duplicate the arrays to avoid changing the original
        var arr1 = a.concat([]), arr2 = b.concat([]);
        arr1.sort();arr2.sort();
        return JSON.stringify(arr1)===JSON.stringify(arr2);
    }
    
    function clear_dependent_attribute() {
        if (!dependent_attribute_input) return;
        dependent_attribute_input.set_value('');
    }
    function clear_item_attribute_inputs() {
        if(!attribute_inputs) return;
        for(let i = 0; i < attribute_inputs.length; i++){
            attribute_inputs[i].set_value('');
        }
    }

    function clear_other_inputs() {
        if (!other_input_controls) return;
        for (let key in other_input_controls) {
            let value = ''
            if(other_input_controls[key].df.default){
                value = other_input_controls[key].df.default    
            }
            other_input_controls[key].set_value(value);
        }
    }

    function clear_item_values() {
        for(var i = 0; i < cur_item.value.attributes.length; i++){
            item.value.attributes[cur_item.value.attributes[i]] = ""
        }
        if(cur_item.value.primary_attribute){
            for(var i = 0;i < cur_item.value.primary_attribute_values.length; i++){
                item.value.values[cur_item.value.primary_attribute_values[i]] = {qty: 0, rate: 0}
            }
        }
        else{
            item.value.values['default'] = {qty: 0, rate: 0}
        }
    }

    function clear_inputs(force) {
        clear_dependent_attribute();
        clear_item_attribute_inputs();
        clear_other_inputs();
        clear_item_values();
        if(!deto.value || force){
            clear_lot_item_inputs();
        }
    }

    function clear_dependent_attribute_inputs() {

        attribute_inputs = [];
        let $el = root.value
        $($el).find('.item-attribute-controls').html("");
        $($el).find('.item-attribute-controls-right').html("");

        additional_parameter_inputs = [];
        $($el).find('.additional-parameter-controls').html("");
        $($el).find('.additional-parameter-controls-right').html("");

        if (!props.otherInputs) return;
        for (let i = 0;i < other_inputs.value.length; i++) {
            let data = other_inputs.value[i];
            let parent_class = '.' + data
            $($el).find(parent_class).html("");
        }
        other_input_controls = {};
    }
    function validate_item_values() {
        if(!cur_item.value.primary_attribute){
            if(item.value.values['default'].qty == 0){
                // $nextTick(() => {
                //     $ref.qty_control.focus();
                // });
                frappe.show_alert({
                    message: __('Quantity cannot be 0'),
                    indicator: 'red'
                });
                return false;
            }
        }
        else{
            let total_qty = 0;
            for(var i = 0; i < cur_item.value.primary_attribute_values.length; i++){
                total_qty += item.value.values[cur_item.value.primary_attribute_values[i]].qty;
            }
            if(total_qty == 0){
                // $nextTick(() => {
                //     $ref.qty_control_0[0].focus();
                // });
                frappe.show_alert({
                    message: __('Quantity cannot be 0'),
                    indicator: 'red'
                });
                return false;
            }
        }
        return true;
    }

    function add_item() {
        if(!get_item_attributes()) return;
        if(props.enableAdditionalParameter && !get_additional_parameters()) return;
        if(!get_other_details()) return;
        

        if(props.validateQty && !validate_item_values()) return;
        if(props.validate && !props.validate(item.value)) return;
        if(item.value.name != item_input.get_value()){
            frappe.msgprint(__('Item does not match'));
            clear_inputs(true);
            return;
        }
        if(is_edit.value){
            props.items[edit_index.value].items[edit_index1.value] = JSON.parse(JSON.stringify(item.value));
            cancel_edit();
            emit("itemupdated", true);
            return;
        }
        let index = get_item_group_index();
        if(index == -1){
            props.items.push({
                attributes: cur_item.value.attributes,
                primary_attribute: cur_item.value.primary_attribute,
                dependent_attribute: cur_item.value.dependent_attribute,
                dependent_attribute_details: cur_item.value.dependent_attribute_details,
                primary_attribute_values: cur_item.value.primary_attribute_values,
                additional_parameters: cur_item.value.additional_parameters,
                items: [JSON.parse(JSON.stringify(item.value))]
            });
        } else {
            props.items[index].items.push(JSON.parse(JSON.stringify(item.value)));
        }
        emit("itemadded", true);
        clear_inputs(false);
    }

    function remove_item(index, index1) {
        if(is_edit.value){
            if(edit_index.value == index){
                if(edit_index1.value > index1){
                    edit_index1.value--;
                }
                else if(edit_index1.value == index1){
                    cancel_edit();
                }
            }
        }
        if(props.items[index].items.length == 1){
            if(is_edit.value){
                if(edit_index.value == index){
                    cancel_edit();
                }
                else if(edit_index.value > index){
                    edit_index.value--;
                }
            }
            props.items.splice(index, 1);
        } else {
            props.items[index].items.splice(index1, 1);
        }
        emit("itemremoved", true);
    }

    function edit_item(index, index1) {
        cur_item_changed.value = false
        if(!is_edit.value) is_edit.value = !is_edit.value;
        edit_index.value = index;
        edit_index1.value = index1;
        let items = JSON.parse(JSON.stringify(props.items[index]))
        set_lot_item_details({
            item: items.items[index1].name,
            attributes: items.attributes,
            primary_attribute: items.primary_attribute,
            dependent_attribute: items.dependent_attribute,
            dependent_attribute_details: items.dependent_attribute_details,
            primary_attribute_values: items.primary_attribute_values,
            default_uom: items.items[index1].default_uom,
            secondary_uom: items.items[index1].secondary_uom,
            additional_parameters: items.additional_parameters,
        }, items.items[index1])
        lot_input.df.read_only = 1;
        item_input.df.read_only = 1;
        item_input.refresh();
        lot_input.refresh();
    }

    function cancel_edit() {
        is_edit.value = !is_edit.value;
        edit_index.value = -1;
        edit_index1.value = -1;
        clear_inputs(true);
        lot_input.df.read_only = 0;
        item_input.df.read_only = 0;
        item_input.refresh();
        lot_input.refresh();
    }

</script> 
