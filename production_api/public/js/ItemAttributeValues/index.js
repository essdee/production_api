import AttributeValues from "./attributevalues.vue";

export default class ItemAttributeValues {
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
}
