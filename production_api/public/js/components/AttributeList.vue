<template>
    <div class="attribute-list-template frappe-control">
        <div class="d-flex flex-row" v-if="attr_list && attr_list.length != 0">
            <div class="m-2 address-box flex-fill" v-for="(attr, index) in attr_list" :key="attr.attr_name">
                <h5>{{ attr.attr_name }}
                    <a :href="'/app/Form/' + encodeURIComponent(attr.doctype) +'/' + encodeURIComponent(attr.attr_values_link)" 
                    v-if="attr.attr_values_link" class="btn btn-default btn-xs pull-right" style="margin-top:-3px; margin-right: -5px;">
                        Edit
                    </a>
                    <a @click="addAttributeMapping(attr.doctype, index)" 
                    v-else class="btn btn-default btn-xs pull-right" style="margin-top:-3px; margin-right: -5px;">
                        Add
                    </a>
                </h5>
                <p class="text-muted" v-for="value in attr.attr_values" :key="value.name">{{ value.attribute_value }}</p>
            </div>
        </div>
        <p v-else>Add an attribute above.</p>
    </div>
</template>

<script setup>
// Used in Item to show list of attributes of the item
import { ref } from 'vue'

const attr_list = ref(cur_frm.doc.__onload.attr_list)

function addAttributeMapping(doctype, name) {
    frappe.model.with_doctype(doctype, function() {
        var new_doc = frappe.model.get_new_doc(doctype);
        console.log(new_doc);
        frappe.ui.form.make_quick_entry(doctype, (doc) => {});
    });
}
</script>