<template>
    <div>
        <!-- <button class="btn btn-xs btn-default" @click="printHelp">help</button> -->
        <button class="btn btn-xs btn-default" @click="disable_rows">Disable</button>
        <button class="btn btn-xs btn-default" @click="enable_rows">Enable</button>
        <table v-if="attributes && attributes.length > 0" class="table table-sm table-bordered">
            <tr>
                <th>S.No</th>
                <th></th>
                <th v-for="attr in item_attributes">{{ attr }}</th>
                <th v-for="attr in bom_attributes">{{ attr }}</th>
                <th v-if="bom_attributes.length > 0">Quantity</th>
            </tr>
            <tr v-for="(d, index) in data">
                <td>{{ index + 1 }}</td>
                <td>
                    <span v-if="d.included" @click="toggle_row(index, false)">
                        ⛔️
                    </span>
                    <span v-else  @click="toggle_row(index, true)">
                        ➕
                    </span>
                </td>
                <td v-for="attr in item_attributes">
                    <!-- {{get_input_class('item', attr, index)}} -->
                    <div :class="get_input_class('item', attr, index)"></div>
                </td>
                <td v-for="attr in bom_attributes">
                    <div :class="get_input_class('bom', attr, index)"></div>
                </td>
                <td v-if="bom_attributes.length > 0">
                    <div :class="get_quantity_input_class('quantity', index)"></div>
                </td>
            </tr>
        </table>
    </div>
</template>

<script>
export default {
    name: 'EditBomMapping',
    data() {
        return {
            attributes: [],
            item_attributes: [],
            bom_attributes: [],
            attribute_values: [],
            attribute_inputs: [],
            data: [],
            bom_item: cur_frm.doc.bom_item,
            sample_doc: {},
        };
    },
    methods: {
        printHelp: function() {
            console.log(this)
        },

        get_final_output: function() {
            if (!this.get_input_values()) return;
            let output = [];
            for (let i = 0; i < this.data.length; i++) {
                if (!this.data[i]["included"]) continue;
                for (let j = 0; j < this.item_attributes.length; j++) {
                    let value = this.data[i][this.get_attribute_name('item', this.item_attributes[j])]
                    if (!value) {
                        return;
                    }
                    let qty = this.data[i][this.get_attribute_name('quantity',i)]
                    output.push({
                        index: i,
                        type: 'item',
                        attribute: this.item_attributes[j],
                        attribute_value: value,
                        quantity: qty,
                    });
                }
                for (let j = 0; j < this.bom_attributes.length; j++) {
                    let value = this.data[i][this.get_attribute_name('bom', this.bom_attributes[j])]
                    if (!value) {
                        return;
                    }
                    let qty = this.data[i][this.get_attribute_name('quantity',i)]
                    if (qty == 0){
                        return
                    }
                    output.push({
                        index: i,
                        type: 'bom',
                        attribute: this.bom_attributes[j],
                        attribute_value: value,
                        quantity: qty,
                    });
                }
            }
            if (output.length == 0) return;
            return {
                'attributes': this.attributes,
                'output': output,
            };
        },

        find_index: function(item_attributes) {
            let index = -1;
            for (let i = 0; i < this.data.length; i++) {
                let flag = true;
                let d = this.data[i];
                for (let j = 0; j < this.item_attributes.length; j++) {
                    let attr = this.item_attributes[j];
                    let attr_value = item_attributes[attr];
                    let attr_value1 = d[this.get_attribute_name('item', attr)];
                    if (attr_value != attr_value1) {
                        flag = false;
                        break;
                    }
                }
                if (flag) {
                    index = i;
                    break;
                }
            }
            return index;
        },

        load_data:async function(data) {
            this.remove_attribute_inputs()
            // this.attributes = data.attributes;
            // this.item_attributes = this.get_mapping_attributes('item', this.attributes);
            // this.bom_attributes = this.get_mapping_attributes('bom', this.attributes);
            // this.attribute_values = this.get_item_attribute_values(this.attributes);
            // this.data = [];
            console.log(data)
            await this.set_attributes(data.attributes);
            this.$nextTick(() => {
                data.data.sort(function(a, b) {
                    var keyA = a.index,
                        keyB = b.index;
                    if (keyA < keyB) return -1;
                    if (keyA > keyB) return 1;
                    return 0;
                });
    
                let g_data = {}
                let indexes = []
                for (let i = 0; i < data.data.length; i++) {
                    let d = data.data[i]
                    if (!(d.index in g_data)) {
                        g_data[d.index] = {};
                        indexes.push(d.index);
                    }
                    g_data[d.index][this.get_attribute_name(d.type, d.attribute)] = d.attribute_value;
                    g_data[d.index][this.get_attribute_name("quantity", d.index)] = d.quantity;
                }
                for (let i = 0; i < indexes.length; i++) {
                    let i_attrs = {}
                    for (let j = 0; j < this.item_attributes.length; j++) {
                        let attr = this.item_attributes[j];
                        i_attrs[attr] = g_data[indexes[i]][this.get_attribute_name('item', attr)]
                    }
                    let index = this.find_index(i_attrs);
                    if (index > -1) {
                        for (let j = 0; j < this.bom_attributes.length; j++) {
                            let attr = this.bom_attributes[j];
                            let attr_name = this.get_attribute_name('bom', attr);
                            this.data[index][attr_name] = g_data[indexes[i]][attr_name]
                            this.attribute_inputs[index][attr_name].set_value(this.data[index][attr_name]);
                        }
                        if(this.bom_attributes.length > 0){
                            let attr_name = this.get_attribute_name('quantity', index)
                            this.data[index][attr_name] = g_data[indexes[i]][attr_name]
                            this.attribute_inputs[index][attr_name].set_value(this.data[index][attr_name])
                        }
                    }
                }
                for (let i = 0; i < this.data.length; i++) {
                    if (!indexes.includes(i)) {
                        this.toggle_row(i, false);
                    }
                }
            });
            // this.$nextTick(() => {
            //     this.create_attribute_inputs();
            //     $(this.$el).find(".control-label").remove();
            // });
        },

        set_attributes:async function(attributes) {
            this.remove_attribute_inputs()

            this.attributes = attributes;
            this.item_attributes = this.get_mapping_attributes('item', attributes);
            this.bom_attributes = this.get_mapping_attributes('bom', attributes);
            this.attribute_values = this.get_item_attribute_values(attributes);
            this.data = [];
            let me = this
            if (attributes && attributes.length > 0) {
                await frappe.call({
                    method: "production_api.production_api.doctype.item_bom_attribute_mapping.item_bom_attribute_mapping.get_item_bom_mapping_combination",
                    args: {
                        "item_attributes": this.item_attributes,
                        "bom_attributes": this.bom_attributes,
                        "attribute_values": this.attribute_values,
                        "ipd":cur_frm.doc.item_production_detail,
                    },
                    callback: function(r){
                        if (r.message) {
                            me.data = r.message;
                            me.$nextTick(() => {
                                me.create_attribute_inputs();
                                $(me.$el).find(".control-label").remove();
                            });
                        }
                    }
                })
            }
        },

        get_mapping_attributes: function(type, attributes) {
            if (!attributes || attributes.length == 0) return [];
            let item_attributes = [];
            for (let i = 0; i < attributes.length; i++) {
                if (attributes[i].type == type) {
                    item_attributes.push(attributes[i].attribute);
                }
            }
            return item_attributes;
        },

        get_item_attribute_values: function(attributes) {
            let attribute_values = {};
            for (let i = 0; i < attributes.length; i++) {
                if (attributes[i].type == "item") {
                    attribute_values[attributes[i].attribute] = [...attributes[i].attribute_values];
                }
            }
            return attribute_values;
        },

        get_attribute_name: function(type, attribute) {
            return type+"_"+attribute;
        },

        get_input_class: function(type, attribute, index) {
            return type+"-"+attribute+"-"+index;
        },

        get_quantity_input_class: function(key, index){
            return key+"-"+index;
        },

        create_input: function(type, attribute, index) {
            let me = this;
            let parent_class = "." + this.get_input_class(type, attribute, index);
            let df = {
                fieldtype: 'Link',
                fieldname: this.get_attribute_name(type, attribute)+"_"+index,
                options: 'Item Attribute Value',
                // label: 'Attribute',
            };
            if (type == "item") {
                df["read_only"] = true;
            } else if (type == "bom") {
                df["get_query"] = function() {
                    return {
                        query: "production_api.production_api.doctype.item.item.get_item_attribute_values",
                        filters: {
                            "item": me.bom_item,
                            "attribute": attribute,
                        }
                    };
                }
                df["reqd"] = true;
            }
            return frappe.ui.form.make_control({
                parent: $(this.$el).find(parent_class),
                df: df,
                // doc: this.sample_doc,
                render_input: true,
            });
        },

        create_quantity_input: function(attribute, index) {
            let parent_class = "." + this.get_quantity_input_class(attribute, index);
            let df = {
                fieldtype: 'Float',
                fieldname: this.get_attribute_name(attribute, index),
                // label: 'Attribute',
            };
            return frappe.ui.form.make_control({
                parent: $(this.$el).find(parent_class),
                df: df,
                // doc: this.sample_doc,
                render_input: true,
            });
        },

        get_input_values: function() {
            if (!this.attribute_inputs || this.attribute_inputs.length == 0) return;
            for (let i = 0; i < this.attribute_inputs.length; i++) {
                for (let j=0;j<this.bom_attributes.length;j++) {
                    let attr = this.bom_attributes[j];
                    let attr_name = this.get_attribute_name('bom', attr);
                    let input = this.attribute_inputs[i][attr_name]
                    let value = input.get_value();
                    if (input.df.reqd && !value) {
                        input.$input.select();
                        // frappe.msgprint(__(label + ' does not have a value'));
                        return false;
                    }
                    this.data[i][attr_name] = value;
                    attr_name = this.get_attribute_name("quantity", i)
                    let quantity = this.attribute_inputs[i][attr_name]
                    this.data[i][attr_name] = quantity.get_value()
                }
            }
            return true;
        },

        create_attribute_inputs: function() {
            this.attribute_inputs = [];
            for (let i=0;i<this.data.length;i++) {
                let inputs = {};
                for (let j=0;j<this.item_attributes.length;j++) {
                    let attr = this.item_attributes[j];
                    let attr_name = this.get_attribute_name('item', attr);
                    inputs[attr_name] = this.create_input("item", attr, i);
                    inputs[attr_name].set_value(this.data[i][attr_name]);
                }
                for (let j=0;j<this.bom_attributes.length;j++) {
                    let attr = this.bom_attributes[j];
                    let attr_name = this.get_attribute_name('bom', attr);
                    inputs[attr_name] = this.create_input("bom", attr, i);
                    inputs[attr_name].set_value(this.data[i][attr_name]);
                }
                if(this.bom_attributes.length > 0){
                    let attr_name = this.get_attribute_name("quantity", i)
                    inputs[attr_name] = this.create_quantity_input("quantity", i)
                    inputs[attr_name].set_value(this.data[i][attr_name])
                }
                this.attribute_inputs.push(inputs);
            }
        },

        remove_attribute_inputs: function() {
            if (!this.data || this.data.length == 0) return;
            if (!this.attribute_inputs || this.attribute_inputs.length == 0) return;

            for (let i=0;i<this.data.length;i++) {
                for (let j=0;j<this.item_attributes.length;j++) {
                    let parent_class = "." + this.get_input_class('item', this.item_attributes[j], i);
                    $(this.$el).find(parent_class).empty();
                }
                for (let j=0;j<this.bom_attributes.length;j++) {
                    let parent_class = "." + this.get_input_class('bom', this.bom_attributes[j], i);
                    $(this.$el).find(parent_class).empty();
                }
            }
            this.attribute_inputs = [];
        },

        toggle_row: function(index, b) {
            this.data[index]["included"] = b;
            for (let j=0;j<this.bom_attributes.length;j++) {
                let attr = this.bom_attributes[j];
                let attr_name = this.get_attribute_name('bom', attr);
                let input = this.attribute_inputs[index][attr_name]
                input.set_value("");
                input.df["reqd"] = b;
                input.df["read_only"] = !b;
                input.refresh();
            }
        },

        disable_rows: function() {
            for (let i = 0; i < this.data.length; i++) {
                if (!this.data[i]["included"]) continue;
                let flag = false;
                for (let j = 0; j<this.bom_attributes.length; j++) {
                    let attr = this.bom_attributes[j];
                    let attr_name = this.get_attribute_name('bom', attr);
                    let input = this.attribute_inputs[i][attr_name]
                    let value = input.get_value();
                    if (!value) {
                        flag = true;
                        break;
                    }
                }
                if (this.bom_attributes.length == 0) {
                    flag = true;
                }
                if (flag) {
                    this.toggle_row(i, false);
                }
            }
        },

        enable_rows: function() {
            for (let i = 0; i < this.data.length; i++) {
                if (!this.data[i]["included"]) {
                    this.toggle_row(i, true);
                }
            }
        }
    }
}
</script>
