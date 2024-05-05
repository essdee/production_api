<template>
    <div class="attribute-value-template frappe-control">
        <table class="table table-sm table-bordered" v-if="attr_values">
            <tr>
                <th>S.No</th>
                <th>Attribute Value</th>
            </tr>
            <tr v-for="(attr, index) in attr_values" :key="attr">
                <td>{{ index + 1 }}</td>
                <td>{{ attr.attribute_value }}</td>
            </tr>
        </table>
        <p v-else>No available values for {{ attr_name }}</p>
        <p v-if="!is_numeric">
            <button class="btn btn-xs btn-default btn-address" @click="addValue('Item Attribute Value', attr_name)">
                {{ "New " + attr_name }}
            </button>
        </p>
    </div>
</template>

<script setup>
// Used in Item Attribute to list all the values of an attribute
import { ref } from 'vue'
const attr_values = ref(getAttrValues())
const attr_name = ref(cur_frm.doc.attribute_name);
const is_numeric = ref(cur_frm.doc.numeric_values);

function addValue(doctype, attr_name) {
    frappe.model.with_doctype(doctype, function() {
        var new_doc = frappe.model.get_new_doc(doctype);
        new_doc.attribute_name = attr_name;
        frappe.ui.form.make_quick_entry(doctype, function(x){cur_frm && cur_frm.reload_doc();}, null, new_doc);
    });
}

function getAttrValues() {
    if(cur_frm.doc.__onload.attr_values && cur_frm.doc.__onload.attr_values.length != 0) {
        return cur_frm.doc.__onload["attr_values"];
    } else {
        return null;
    }
}
</script>