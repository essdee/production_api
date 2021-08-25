<template>
    <div class="item-price-list-template frappe-control">
        <table class="table table-sm table-bordered" v-if="item_price_list">
            <tr>
                <th>S.No</th>
                <th>Item Name</th>
                <th>Item Price</th>
            </tr>
            <tr v-for="(item, index) in item_price_list" :key="item">
                <td>{{ index + 1 }}</td>
                <td>{{ item.item_name }}</td>
                <td>{{ item.price }}</td>
            </tr>
        </table>
        <p v-else>Price not available.</p>
        <p>
            <button class="btn btn-xs btn-default btn-address" @click="addValue('Item Price', doc_name)">
                {{ __("Add") + ' Price' }}
            </button>
        </p>
        
    </div>
</template>

<script>
export default {
    name: 'ItemPriceListTemplate',
    data: function(){
        return {
            item_price_list: this.getPriceList(),
            doc_name: cur_frm.doc.name
        };
    },
    methods: {
        addValue: function(doctype, name){
            frappe.model.with_doctype(doctype, function() {
                var new_doc = frappe.model.get_new_doc(doctype);
                if(cur_frm.doctype == "Supplier")
                    new_doc.supplier = name;
                else if(cur_frm.doctype == "Item")
                    new_doc.item_name = name;
                frappe.ui.form.make_quick_entry(doctype, function(x){cur_frm && cur_frm.reload_doc();}, null, new_doc);
		    });
        },
        getPriceList: function() {
            if(cur_frm.doc.__onload.item_price_list && cur_frm.doc.__onload.item_price_list.length != 0)
                return cur_frm.doc.__onload["item_price_list"];
            else return null;
        }
    }
}
</script>