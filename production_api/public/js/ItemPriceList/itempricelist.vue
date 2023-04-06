<template>
    <div class="item-price-list-template frappe-control">
        <table class="table table-sm table-bordered" v-if="item_price_list">
            <tr>
                <th style="width:36px"> </th>
                <th style="width:48px">S.No</th>
                <th v-if='doctype=="Supplier"'>Item Name</th>
                <th v-if='doctype=="Item"'>Supplier Name</th>
                <!-- <th>Item Price</th>
                <th>Minimum Order Quantity</th> -->
            </tr>
            <template v-for="(item, index) in item_price_list" :key="item">
                <tr  class="openable-row" :class="{ opened: opened.includes(index) }" @click="toggle(index)">
                    <td>
                        <i class="fa fa-md fa-fw pull-left" :class="{ 'fa-minus-square-o': opened.includes(index), 'fa-plus-square-o': !opened.includes(index) }"></i>
                    </td>
                    <td class="text-center">
                         {{ index + 1 }}
                    </td>
                    <td v-if='doctype=="Supplier"'>{{ item.item_name }}</td>
                    <td v-if='doctype=="Item"'>{{ item.supplier_name }}</td>
                    <!-- <td>{{ item.price }}</td>
                    <td>{{ item.moq }}</td> -->
                </tr>
                <tr v-if="opened.includes(index)" :key="'i-'+index">
                    <td></td>
                    <td colspan="2">
                        <div class="sub-table">
                            <div v-if="item.depends_on_attribute">Depends on {{item.attribute}}</div>
                            <table class="table table-sm table-bordered" v-if="item.item_price_values">
                                <tr>
                                    <th>S.No</th>
                                    <th>Minimum Order Quantity</th>
                                    <th>Item Price</th>
                                    <th v-if="item.depends_on_attribute">Attribute Value</th>
                                </tr>
                                <tr v-for="(price, j) in item.item_price_values" :key="price">
                                    <td>{{ j + 1 }}</td>
                                    <td>{{ price.moq }}</td>
                                    <td>{{ price.price }}</td>
                                    <td v-if="item.depends_on_attribute">{{ price.attribute_value }}</td>
                                </tr>
                            </table>
                        </div>
                    </td>
                </tr>
            </template>
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
            doc_name: cur_frm.doc.name,
            doctype: cur_frm.doctype,
            opened: [],
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
        toggle(id) {
            const index = this.opened.indexOf(id);
            if (index > -1) {
                this.opened.splice(index, 1)
            } else {
                this.opened.push(id)
            }
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
