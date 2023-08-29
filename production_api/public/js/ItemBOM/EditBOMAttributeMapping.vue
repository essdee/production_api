<template>
    <div>
        <!-- <button @click="printHelp">help</button> -->
        <table v-if="attributes && attributes.length > 0" class="table table-sm table-bordered">
            <tr>
                <th>S.No</th>
                <th v-for="attr in item_attributes">{{ attr }}</th>
                <th v-for="attr in bom_attributes">{{ attr }}</th>
            </tr>
            <tr v-for="(d, index) in data">
                <td>{{ index + 1 }}</td>
                <td v-for="attr in item_attributes">
                    <div :class="get_input_class('item', attr, index)"></div>
                </td>
                <td v-for="attr in bom_attributes">
                    <div :class="get_input_class('bom', attr, index)"></div>
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
            this.get_input_values();
            let output = [];
            for (let i = 0; i < this.data.length; i++) {
                for (let j = 0; j < this.item_attributes.length; j++) {
                    let value = this.data[i][this.get_attribute_name('item', this.item_attributes[j])]
                    if (!value) {
                        return;
                    }
                    output.push({
                        index: i,
                        type: 'item',
                        attribute: this.item_attributes[j],
                        attribute_value: value,
                    });
                }
                for (let j = 0; j < this.bom_attributes.length; j++) {
                    let value = this.data[i][this.get_attribute_name('bom', this.bom_attributes[j])]
                    if (!value) {
                        return;
                    }
                    output.push({
                        index: i,
                        type: 'bom',
                        attribute: this.bom_attributes[j],
                        attribute_value: value,
                    });
                }
            }
            return {
                'attributes': this.attributes,
                'output': output,
            };
        },

        load_data: function(data) {
            this.remove_attribute_inputs()
            this.attributes = data.attributes;
            this.item_attributes = this.get_mapping_attributes('item', this.attributes);
            this.bom_attributes = this.get_mapping_attributes('bom', this.attributes);
            this.attribute_values = this.get_item_attribute_values(this.attributes);
            this.data = [];
            data.data.sort(function(a, b) {
                var keyA = a.index,
                    keyB = b.index;
                if (keyA < keyB) return -1;
                if (keyA > keyB) return 1;
                return 0;
            });
            for (let i = 0; i < data.data.length; i++) {
                let d = data.data[i]
                if (!this.data[d.index]) {
                    this.data[d.index] = {}
                }
                this.data[d.index][this.get_attribute_name(d.type, d.attribute)] = d.attribute_value;
            }
            this.$nextTick(() => {
                this.create_attribute_inputs();
                $(this.$el).find(".control-label").remove();
            });
        },

        set_attributes: function(attributes) {
            this.remove_attribute_inputs()

            this.attributes = attributes;
            this.item_attributes = this.get_mapping_attributes('item', attributes);
            this.bom_attributes = this.get_mapping_attributes('bom', attributes);
            this.attribute_values = this.get_item_attribute_values(attributes);

            this.data = [];
            if (attributes && attributes.length > 0) {
                let data = [];
                let attr = this.item_attributes[0]
                let attr_values = this.attribute_values[attr]
                for (let i = 0; i < attr_values.length; i++) {
                    let d = {};
                    d[this.get_attribute_name('item', attr)] = attr_values[i];
                    data.push(d);
                }
                for (let i = 1; i < this.item_attributes.length; i++) {
                    let data1 = [...data];
                    data = [];
                    attr = this.item_attributes[i];
                    attr_values = this.attribute_values[attr]
                    for (let j  = 0; j < attr_values.length; j++) {
                        for (let k = 0; k < data1.length; k++) {
                            let d = {...data1[k]};
                            d[this.get_attribute_name('item', attr)] = attr_values[j];
                            data.push(d);
                        }
                    }
                }
                for (let i = 0; i < data.length; i++) {
                    for (let j = 0; j < this.bom_attributes.length; j++) {
                        data[i][this.get_attribute_name('bom', this.bom_attributes[j])] = null;
                    }
                }
                this.data = data;
            }
            this.$nextTick(() => {
                this.create_attribute_inputs();
                $(this.$el).find(".control-label").remove();
            });
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
                doc: this.sample_doc,
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
                }
            }
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
    }
}
</script>
