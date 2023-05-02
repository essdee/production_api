import GRNItem from "./components/GRNItem.vue"

export default class GRNItemWrapper {
    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_body();
    }

    make_body() {
        let $page_container = $('<div class="item frappe-control">').appendTo(this.$wrapper);
        this.vue = new Vue({
            el: '.item',
            render: h => h(GRNItem, {
            })
        });
    }

    updateWrapper(wrapper) {
        this.$wrapper = $(wrapper);
        $(this.vue.$el).appendTo(this.$wrapper)
    }

    get_items() {
        return this.vue.$children[0].get_items();
    }

    load_data(data, skip_watch=false) {
        this.vue.$children[0].load_data(data, skip_watch);
    }
    
    update_status() {
        this.vue.$children[0].update_status();
    }
};