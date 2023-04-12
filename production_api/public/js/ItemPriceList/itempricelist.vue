<template>
    <div class="item-price-list-template frappe-control">
        <table class="table table-sm table-bordered" v-if="item_price_list">
            <tr>
                <th style="width:48px">S.No</th>
                <th v-if='doctype=="Supplier"'>Item Name</th>
                <th v-if='doctype=="Item"'>Supplier Name</th>
                <th>Based on Attribute</th>
                <th>Minimum Order Quantity</th>
                <th>Item Price</th>
                <th>Attribute</th>
            </tr>
            <tr v-for="item in item_price_list" :key="item.uid">
                <td v-if='item.count' class="text-center" :rowspan="item.count">
                    {{ item.index + 1 }}
                </td>
                <td v-if='item.count && doctype=="Supplier"' :rowspan="item.count">{{ item.item_name }}</td>
                <td v-if='item.count && doctype=="Item"' :rowspan="item.count">{{ item.supplier }}</td>
                <td v-if='item.count' :rowspan="item.count">{{ item.depends_on_attribute ? item.attribute : "" }}</td>
                <td>{{ item.moq }}</td>
                <td>{{ item.price }}</td>
                <td>{{ item.attribute_value }}</td>
            </tr>
        </table>
        <p v-else>Price not available.</p>
        <!-- <p>
            <button class="btn btn-xs btn-default btn-address" @click="addValue('Item Price', doc_name)">
                {{ __("Add") + ' Price' }}
            </button>
        </p> -->
    </div>
</template>

<script>
let uuid = 0;
export default {
    name: 'ItemPriceListTemplate',
    data: function(){
        return {
            item_price_list: this.compute_price_list(this.getPriceList()),
            doc_name: cur_frm.doc.name,
            doctype: cur_frm.doctype,
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
        },
        compute_price_list: function(item_price_list) {
            if (!item_price_list) return null
            let pl = []
            for (let i = 0;i<item_price_list.length;i++) {
                let item_price = item_price_list[i]
                let x = {
                    index: i,
                    item: item_price.item_name,
                    supplier: item_price.supplier,
                    depends_on_attribute: item_price.depends_on_attribute,
                    attribute: item_price.attribute,
                    count: item_price.item_price_values.length
                }
                for (let j = 0;j<item_price.item_price_values.length;j++) {
                    let price_value = item_price.item_price_values[j]
                    let y = {}
                    if (j==0) {
                        y = {...x}
                    }
                    y = {
                        ...y,
                        moq: price_value.moq,
                        price: price_value.price,
                        attribute_value: price_value.attribute_value,
                        row_count: j,
                        uid: uuid++
                    }
                    pl.push(y)
                }
            }
            return pl;
        }
    }
}
</script>

<style scoped>
.opened {
  background-color: white;
}
.sub-table {
    padding: 8px 16px;
    /* background-color: aliceblue; */
}
.openable-row {
    cursor: pointer;
}
.fa-md {
    font-size: 18px;
}
</style>
