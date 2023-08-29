import AttributeValues from "./components/AttributeValues.vue";
import AttributeList from "./components/AttributeList.vue";
import BomAttributeMapping from "./components/BomAttributeMapping.vue";
import ItemPriceList from "./ItemPriceList";
import ItemDetail from "./components/ItemDetails.vue";

import PONewItem from "./PurchaseOrder/components/NewItem.vue"
import POItem from "./PurchaseOrder/components/Item.vue"
import GRNItemWrapper from "./GRN";
import { StockEntryWrapper, StockReconciliationWrapper, LotTransferWrapper } from "./Stock";
import ProductFileVersionsWrapper from "./ProductDevelopment"
import evntBus from "./bus.js";

import { EditBOMAttributeMappingWrapper, BOMAttributeMappingWrapper } from "./ItemBOM";

frappe.provide("frappe.production.ui");
frappe.provide("frappe.production.product_development.ui");

frappe.production.ui.eventBus = evntBus;

frappe.production.ui.ItemAttributeValues = class {
    constructor({ wrapper, attr_values, attr_name } = {}) {
        this.$wrapper = $(wrapper);
        this.attr_values = attr_values;
        this.attr_name = attr_name;
        this.make_body();
    }
    
    make_body() {
        this.$page_container = $('<div class="attribute-value-template frappe-control">').appendTo(this.$wrapper);
        this.vue = new Vue({
            el: '.attribute-value-template',
            render: h => h(AttributeValues, {
            }),
        });
    }
};

frappe.production.ui.ItemAttributeList = class {
    constructor({ wrapper, attr_values, attr_name } = {}) {
        this.$wrapper = $(wrapper);
        this.attr_values = attr_values;
        this.attr_name = attr_name;
        this.make_body();
    }

    make_body() {
        this.$page_container = $('<div class="attribute-list-template frappe-control">').appendTo(this.$wrapper);
        this.vue = new Vue({
            el: '.attribute-list-template',
            render: h => h(AttributeList, {
            }),
        });
    }
};

frappe.production.ui.BomItemAttributeMapping = BOMAttributeMappingWrapper;

frappe.production.ui.ItemPriceList = ItemPriceList;

frappe.production.ui.ItemDetail = function(wrapper, type, data) {
    let $wrapper = $(wrapper);
    let $page_container = $('<div class="item-detail frappe-control">').appendTo($wrapper);
    let vue = new Vue({
        el: '.item-detail',
        render: h => h(ItemDetail, {
            props: {
                type,
                data
            }
        })
    });
};

// frappe.production.ui.PurchaseOrderItem = function(wrapper) {
//     let $wrapper = $(wrapper);
//     let $page_container = $('<div class="item frappe-control">').appendTo($wrapper);
//     return new Vue({
//         el: '.item',
//         render: h => h(POItem, {
//         })
//     });
// };

frappe.production.ui.PurchaseOrderItem = class {
    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_body();
    }

    make_body() {
        let $page_container = $('<div class="item frappe-control">').appendTo(this.$wrapper);
        this.vue = new Vue({
            el: '.item',
            render: h => h(POItem, {
            })
        });
    }

    updateWrapper(wrapper) {
        this.$wrapper = $(wrapper);
        $(this.vue.$el).appendTo(this.$wrapper)
    }

    get_items() {
        return this.vue.$children[0].items;
    }

    load_data(item_details) {
        this.vue.$children[0].load_data(item_details);
    }

    update_status() {
        this.vue.$children[0].update_status();
    }
};

frappe.production.ui.GRNItem = GRNItemWrapper
frappe.production.ui.StockEntryItem = StockEntryWrapper
frappe.production.ui.StockReconciliationItem = StockReconciliationWrapper
frappe.production.ui.LotTransferItem = LotTransferWrapper
frappe.production.product_development.ui.ProductFileVersions = ProductFileVersionsWrapper

frappe.production.ui.EditBOMAttributeMapping = EditBOMAttributeMappingWrapper

