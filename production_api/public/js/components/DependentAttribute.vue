<template>
    <div class="dependent-attribute-template frappe-control">
        <div v-if="dependent_attribute">
            <table class="table table-sm table-bordered" style="margin-bottom: 4px;">
                <tr>
                    <td>{{ item.dependent_attribute }}</td>
                    <td>UOM</td>
                    <td>Display Name</td>
                    <td>Is Final</td>
                    <td v-for="attr in attributes">{{ attr }}</td>
                </tr>
                <tr v-for="attr_value in dependent_attr_list">
                    <th>{{ attr_value }}</th>
                    <td>
                        <div v-if="edit" :class="get_input_class(attr_value, 'uom')"></div>
                        <span v-else>{{ data.attr_list[attr_value].uom }}</span>
                    </td>
                    <td>
                        <div v-if="edit" :class="get_input_class(attr_value, 'name')"></div>
                        <span v-else>{{ data.attr_list[attr_value].name }}</span>
                    </td>
                    <td>
                        <div v-if="edit" :class="get_input_class(attr_value, 'is_final')"></div>
                        <span v-else>
                            <span v-if="data.attr_list[attr_value].is_final">✅</span>
                            <!-- {{ data.attr_list[attr_value].attributes }} -->
                        </span>
                    </td>
                    <td v-for="attr in attributes">
                        <div v-if="edit" :class="get_input_class(attr_value, attr)"></div>
                        <span v-else>
                            <span v-if="has_value(data.attr_list[attr_value].attributes, attr)">✅</span>
                            <!-- {{ data.attr_list[attr_value].attributes }} -->
                        </span>
                    </td>
                </tr>
            </table>
            <button v-if="!edit" class="btn btn-xs btn-secondary" style="margin-bottom: 16px;" @click="enable_edit">Edit</button>
            <button v-if="edit" class="btn btn-xs btn-secondary" style="margin-bottom: 16px;" @click="save">Save</button>
        </div>
        <p v-else></p>
    </div>
</template>

<script>
// Used in Item to show details of dependent attributes of the item
export default {
    name: 'DependentAttributeTemplate',
    data: function(){
        return {
            data: cur_frm.doc.__onload.dependent_attribute,
            attr_list: cur_frm.doc.__onload.attr_list,
            item: cur_frm.doc,
            edit: false,
        };
    },
    computed: {
        dependent_attribute: function() {
            let dependent_attribute = this.item.dependent_attribute;
            if (this.data && this.data.attr_list) {
                return dependent_attribute;
            }
            return null;
        },
        dependent_attr_list: function() {
            let dependent_attribute = this.item.dependent_attribute;
            if(!dependent_attribute) return [];
            let dependent_attribute_values = []
            for (let i = 0; i < this.attr_list.length; i++)  {
                if (this.attr_list[i]["attr_name"] == dependent_attribute) {
                    for (let j = 0; j < this.attr_list[i]["attr_values"].length; j++) {
                        let value = this.attr_list[i]["attr_values"][j]["attribute_value"];
                        dependent_attribute_values.push(value);
                        if(!this.data.attr_list.hasOwnProperty(value)) {
                            this.data.attr_list[value] = {
                                "uom": this.item.default_unit_of_measure,
                                "name": "",
                                "is_final": 0,
                                "attributes": [],
                            }
                        }
                    }
                    break;
                }
            }
            console.log(JSON.stringify(dependent_attribute_values))
            return dependent_attribute_values;
        },
        attributes: function() {
            let attributes = this.attr_list.map((attr) => {
                return attr.attr_name;
            });
            let index = attributes.indexOf(this.item.dependent_attribute);
            if (index > -1) { // only splice array when item is found
                attributes.splice(index, 1); // 2nd parameter means remove one item only
            }
            console.log(JSON.stringify(this.data))
            return attributes;
        }
    },
    methods: {
        get_input_class: function(attribute, type) {
            return attribute+"-"+type;
        },

        has_value: function(list, value) {
            if (list.indexOf(value) > -1) {
                return true
            }
            return false
        },

        enable_edit: function() {
            if (cur_frm.is_dirty()) {
                frappe.msgprint("Please save this document before editing")
                return;
            }
            this.edit = true;
            this.$nextTick(() => {
                this.create_inputs();
                $(this.$el).find(".control-label").remove();
            });
        },

        create_inputs: function() {
            let inputs = {};
            let me = this;
            for (let i=0;i<this.dependent_attr_list.length;i++) {
                let attr_value = this.dependent_attr_list[i];
                let a = this.get_input_class(attr_value, 'uom');
                inputs[a] = frappe.ui.form.make_control({
                    parent: $(this.$el).find('.'+a),
                    df: {
                        fieldtype: 'Link',
                        options: 'UOM',
                        label: 'UOM',
                        reqd: true,
                        onchange: () => {
                            me.data.attr_list[attr_value].uom = inputs[a].get_value();
                        }
                    },
                    render_input: true,
                });
                inputs[a].set_value(this.data.attr_list[attr_value].uom)
                let b = this.get_input_class(attr_value, 'name');
                inputs[b] = frappe.ui.form.make_control({
                    parent: $(this.$el).find('.'+b),
                    df: {
                        fieldtype: 'Data',
                        label: 'Name',
                        onchange: () => {
                            me.data.attr_list[attr_value].name = inputs[b].get_value();
                        }
                    },
                    render_input: true,
                });
                inputs[b].set_value(this.data.attr_list[attr_value].name)
                let c = this.get_input_class(attr_value, 'is_final');
                inputs[c] = frappe.ui.form.make_control({
                    parent: $(this.$el).find('.'+c),
                    df: {
                        fieldtype: 'Check',
                        label: '',
                        onchange: () => {
                            me.data.attr_list[attr_value].is_final = inputs[c].get_value();
                        }
                    },
                    render_input: true,
                })
                inputs[c].set_value(this.data.attr_list[attr_value].is_final)

                for (let j=0;j<this.attributes.length;j++) {
                    let n = this.get_input_class(attr_value, this.attributes[j]);
                    inputs[n] = frappe.ui.form.make_control({
                        parent: $(this.$el).find('.'+n),
                        df: {
                            fieldtype: 'Check',
                            label: '',
                            onchange: () => {
                                // me.data.attr_list[attr_value].name = this.get_value();
                                let value = inputs[n].get_value();
                                if (value && !this.has_value(this.data.attr_list[attr_value].attributes, this.attributes[j])){
                                    this.data.attr_list[attr_value].attributes.push(this.attributes[j])
                                } else if (!value && this.has_value(this.data.attr_list[attr_value].attributes, this.attributes[j])) {
                                    let index = this.data.attr_list[attr_value].attributes.indexOf(this.attributes[j]);
                                    if (index > -1) { 
                                        this.data.attr_list[attr_value].attributes.splice(index, 1);
                                    }
                                }
                            }
                        },
                        render_input: true,
                    });
                    inputs[n].set_value(this.has_value(this.data.attr_list[attr_value].attributes, this.attributes[j]))
                }
            }
        },

        save: function() {
            if (cur_frm.is_dirty()) {
                frappe.msgprint("Please save this document before saving")
                return;
            }
            console.log(JSON.stringify(this.data))
            frappe.xcall("production_api.production_api.doctype.item.item.update_dependent_attribute_details", {
				dependent_attribute_mapping: this.item.dependent_attribute_mapping,
				detail: this.data,
				// enqueue: true,
				freeze: true,
				freeze_message: __("Updating related fields..."),
			}).then((r) => {
                this.edit=false;
                cur_frm.reload_doc();
			});
            
        },
    }
}
</script>