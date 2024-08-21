<template>
    <div class="bom-attribute-mapping-template frappe-control">
        <div class="d-flex flex-row" v-if="bom_attr_list && bom_attr_list.length != 0">
            <div class="m-2 address-box flex-fill" v-for="bom_item, index in bom_attr_list" :key="index">
                <h5>{{ bom_item.bom_item + ' Mapping' }}
                    <a :href="'/app/Form/' + encodeURIComponent(bom_item.doctype) +'/' + encodeURIComponent(bom_item.bom_attr_mapping_link)" 
                    v-if="bom_item.bom_attr_mapping_link" class="btn btn-default btn-xs pull-right" style="margin-top:-3px; margin-right: -5px;">
                        Edit
                    </a>
                </h5>
                <p class="text-muted" v-for="(value, index1) in get_mapping_attributes(bom_item.bom_attr_mapping_list, index)" :key="index1">
                    <span >{{ value["item"].join(', ') }}</span> ->
                    <span >{{ value["bom"].join(', ') }}</span>
                </p>
            </div>
        </div>
        <p v-else>Add a BOM above.</p>
    </div>
</template>

<script>
// Used in Item to list all the BOM item's attribute mapping.
export default {
    name: 'BomAttributeMappingTemplate',
    data: function(){
        return {
            bom_attr_list: cur_frm.doc.__onload.bom_attr_list,
            expand_list: this.get_expand_list(cur_frm.doc.__onload.bom_attr_list),
        };
    },
    methods: {
        get_mapping_attributes: function(mapping, index) {
            let data = [];
            let len = 5;
            for (let i = 0; i < mapping.length; i++) {
                let d = mapping[i]
                if (!data[d.index]) {
                    data[d.index] = {"item": [], "bom": []};
                }
                if (d.type == "item") {
                    data[d.index]["item"].push(d.attribute_value);
                } else if (d.type == "bom") {
                    data[d.index]["bom"].push(d.attribute_value);
                }
            }
            var i = 0;
            while (i < data.length) {
                if (data[i] == null) {
                    data.splice(i, 1);
                } 
                else {
                    ++i;
                }
            }
            if (this.expand_list[index] || data.length < 5) {
                len = mapping.length;
            }
            return data.splice(0, len);
        },

        get_expand_list: function(mapping) {
            let expand_list = []
            for (let i = 0; i < mapping.length; i++) {
                expand_list.push(false);
            }
            return expand_list;
        }
    },
}
</script>