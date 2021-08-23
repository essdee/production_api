import AttributeValues from "./components/AttributeValues.vue";
import AttributeList from "./components/AttributeList.vue";
import BomAttributeMapping from "./components/BomAttributeMapping.vue";
import ItemPriceList from "./ItemPriceList";
import ItemDetail from "./components/ItemDetails.vue";

frappe.provide("frappe.production.ui");
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

frappe.production.ui.BomItemAttributeMapping = class {
    constructor({ wrapper } = {}) {
        this.$wrapper = $(wrapper);
        this.make_body();
    }

    make_body() {
        this.$page_container = $('<div class="bom-attribute-mapping-template frappe-control">').appendTo(this.$wrapper);
        this.vue = new Vue({
            el: '.bom-attribute-mapping-template',
            render: h => h(BomAttributeMapping, {
            }),
        });
    }
};

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
