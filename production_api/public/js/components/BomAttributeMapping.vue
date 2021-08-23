<template>
    <div class="bom-attribute-mapping-template frappe-control">
        <div class="d-flex flex-row" v-if="bom_attr_list && bom_attr_list.length != 0">
            <div class="m-2 address-box flex-fill" v-for="bom_item in bom_attr_list" :key="bom_item.attr_name">
                <h5>{{ bom_item.bom_item + ' ' + bom_item.bom_item_attr_mapping_based_on + ' Mapping' }}
                    <a :href="'/app/Form/' + encodeURIComponent(bom_item.doctype) +'/' + encodeURIComponent(bom_item.bom_item_attr_mapping_link)" 
                    v-if="bom_item.bom_item_attr_mapping_link" class="btn btn-default btn-xs pull-right" style="margin-top:-3px; margin-right: -5px;">
                        {{ __("Edit") }}
                    </a>
                </h5>
                <p class="text-muted" v-for="value in bom_item.bom_item_attr_mapping_list" :key="value.name">{{ value.product_attribute + ' - ' + value.bom_item_attribute }}</p>
            </div>
        </div>
        <p v-else>Add a BOM above.</p>
    </div>
</template>

<script>
// Used in Item Template to list all the BOM item's attribute mapping.
export default {
    name: 'BomAttributeMappingTemplate',
    data: function(){
        return {
            bom_attr_list: cur_frm.doc.__onload.bom_attr_list
        };
    }
}
</script>