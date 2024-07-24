import AttributeValues from "./components/AttributeValues.vue";
import AttributeList from "./components/AttributeList.vue";
import DependentAttributeTemplate from "./components/DependentAttribute.vue";
import BomAttributeMapping from "./components/BomAttributeMapping.vue";
import ItemPriceList from "./ItemPriceList";
import ItemDetail from "./components/ItemDetails.vue";
import DDItem from "./PurchaseOrder/components/DateUpdateDialog.vue"
import PONewItem from "./PurchaseOrder/components/NewItem.vue"
import POItem from "./PurchaseOrder/components/Item.vue"
import GRNItemWrapper from "./GRN";
import { StockEntryWrapper, StockReconciliationWrapper, LotTransferWrapper } from "./Stock";

// Product Development
import { ProductFileVersionsWrapper, ProductCostingListWrapper } from "./ProductDevelopment"

import EventBus from "./bus.js";

import { EditBOMAttributeMappingWrapper, BOMAttributeMappingWrapper } from "./ItemBOM";

import { createApp } from 'vue';

frappe.provide("frappe.production.ui");
frappe.provide("frappe.production.product_development.ui");

frappe.production.ui.eventBus = EventBus;


frappe.production.ui.ItemAttributeValues = class {
    constructor({ wrapper, attr_values, attr_name } = {}) {
        this.$wrapper = $(wrapper);
        this.attr_values = attr_values;
        this.attr_name = attr_name;
        this.make_body();
    }
    
    make_body() {
        this.$page_container = $('<div class="attribute-value-template frappe-control">').appendTo(this.$wrapper);
        this.app = createApp(AttributeValues);
        this.app.mount(this.$wrapper.get(0));
        // this.vue = new Vue({
        //     el: '.attribute-value-template',
        //     render: h => h(AttributeValues, {
        //     }),
        // });
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
        this.app = createApp(AttributeList);
        this.app.mount(this.$wrapper.get(0));
        // this.vue = new Vue({
        //     el: '.attribute-list-template',
        //     render: h => h(AttributeList, {
        //     }),
        // });
    }
};

frappe.production.ui.ItemDependentAttributeDetail = class {
    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_body();
    }

    make_body() {
        this.$page_container = $('<div class="dependent-attribute-template frappe-control">').appendTo(this.$wrapper);
        this.app = createApp(DependentAttributeTemplate);
        this.app.mount(this.$wrapper.get(0));
        // this.vue = new Vue({
        //     el: '.dependent-attribute-template',
        //     render: h => h(DependentAttributeTemplate, {
        //     }),
        // });
    }
};

frappe.production.ui.DateDialog = class {
    constructor(wrapper, items){
        this.$wrapper = $(wrapper)
        this.items = items
        this.make_body();
    }
    make_body(){
        this.app = createApp(DDItem, {items: this.items})
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    get_items(){
        let items = JSON.parse(JSON.stringify(this.vue.item_data));
        return items
    }
}

frappe.production.ui.BomItemAttributeMapping = BOMAttributeMappingWrapper;

frappe.production.ui.ItemPriceList = ItemPriceList;

frappe.production.ui.ItemDetail = function(wrapper, type, data) {
    let $wrapper = $(wrapper);
    let $page_container = $('<div class="item-detail frappe-control">').appendTo($wrapper);
    let app = createApp(ItemDetail)
    app.mount(this.$page_container)
    // let vue = new Vue({
    //     el: '.item-detail',
    //     render: h => h(ItemDetail, {
    //         props: {
    //             type,
    //             data
    //         }
    //     })
    // });
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
        this.app = createApp(POItem)
        SetVueGlobals(this.app);
        this.vue = this.app.mount(this.$wrapper.get(0))
        // this.vue = new Vue({
        //     el: '.item',
        //     render: h => h(POItem, {
        //     })
        // });
    }

    updateWrapper(wrapper) {
        // this.$wrapper = $(wrapper);
        // let $page_container = $('<div class="item frappe-control">').appendTo(this.$wrapper);
        // this.app.unmount();
        // this.vue = this.app.mount(this.$wrapper.get(0))
    }

    get_items() {
        // let items = JSON.parse(JSON.stringify(this.vue.$children[0].items));
        let items = JSON.parse(JSON.stringify(this.vue.items));
        for (let i = 0; i < items.length; i++) {
            for (let j = 0; j < items[i].items.length; j++) {
                if (items[i].items[j].additional_parameters) {
                    items[i].items[j].additional_parameters = JSON.stringify(items[i].items[j].additional_parameters)
                }
            }
        }
        return items;
    }

    load_data(item_details) {
        let items = JSON.parse(JSON.stringify(item_details));
        for (let i = 0; i < items.length; i++) {
            for (let j = 0; j < items[i].items.length; j++) {
                if (items[i].items[j].additional_parameters) {
                    items[i].items[j].additional_parameters = JSON.parse(items[i].items[j].additional_parameters)
                }
            }
        }
        this.vue.load_data(items);
    }

    update_status() {
        this.vue.update_status();
    }
};

frappe.production.ui.GRNItem = GRNItemWrapper
frappe.production.ui.StockEntryItem = StockEntryWrapper
frappe.production.ui.StockReconciliationItem = StockReconciliationWrapper
frappe.production.ui.LotTransferItem = LotTransferWrapper
frappe.production.ui.EditBOMAttributeMapping = EditBOMAttributeMappingWrapper

// Product Development
frappe.production.product_development.ui.ProductFileVersions = ProductFileVersionsWrapper
frappe.production.product_development.ui.ProductCostingList = ProductCostingListWrapper


