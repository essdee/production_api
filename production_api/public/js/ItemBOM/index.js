import EditBOMAttributeMapping from './EditBOMAttributeMapping.vue';
import BOMAttributeMapping from './BOMAttributeMapping.vue';

export class EditBOMAttributeMappingWrapper {

    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_body();
    }

    make_body() {
        let $page_container = $('<div class="item frappe-control">').appendTo(this.$wrapper);
        this.vue = new Vue({
            el: '.item',
            render: h => h(EditBOMAttributeMapping, {
            })
        });
        this.bomEntry = this.vue.$children[0];
    }

    updateWrapper(wrapper) {
        this.$wrapper = $(wrapper);
        $(this.vue.$el).appendTo(this.$wrapper)
    }

    get_items() {
        return this.bomEntry.get_final_output();
    }

    load_data(data) {
        this.bomEntry.load_data(data);
    }

    set_attributes(attributes) {
        this.bomEntry.set_attributes(attributes);
    }
    
    update_status() {
        this.bomEntry.update_status();
    }
};

export class BOMAttributeMappingWrapper {

    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_body();
    }

    make_body() {
        let $page_container = $('<div class="item frappe-control">').appendTo(this.$wrapper);
        this.vue = new Vue({
            el: '.item',
            render: h => h(BOMAttributeMapping, {
            })
        });
        this.bomEntry = this.vue.$children[0];
    }
};