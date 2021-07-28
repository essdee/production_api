import AttributeList from "./attributelist.vue";

export default class ItemAttributeList {
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
}