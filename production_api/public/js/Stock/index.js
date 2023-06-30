import StockItem from "./StockEntry/StockEntry.vue"
import StockReconciliation from "./StockReconciliation/StockReconciliation.vue"

export class StockEntryWrapper {
    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_body();
    }

    make_body() {
        let $page_container = $('<div class="item frappe-control">').appendTo(this.$wrapper);
        this.vue = new Vue({
            el: '.item',
            render: h => h(StockItem, {
            })
        });
        this.stockEntry = this.vue.$children[0];
    }

    updateWrapper(wrapper) {
        this.$wrapper = $(wrapper);
        $(this.vue.$el).appendTo(this.$wrapper)
    }

    get_items() {
        return this.stockEntry.get_items();
    }

    load_data(data) {
        this.stockEntry.load_data(data);
    }
    
    update_status() {
        this.stockEntry.update_status();
    }
};

export class StockReconciliationWrapper {
    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_body();
    }

    make_body() {
        let $page_container = $('<div class="item frappe-control">').appendTo(this.$wrapper);
        this.vue = new Vue({
            el: '.item',
            render: h => h(StockReconciliation, {
            })
        });
        this.stockReconciliation = this.vue.$children[0];
    }

    updateWrapper(wrapper) {
        this.$wrapper = $(wrapper);
        $(this.vue.$el).appendTo(this.$wrapper)
    }

    get_items() {
        return this.stockReconciliation.get_items();
    }

    load_data(data) {
        this.stockReconciliation.load_data(data);
    }
    
    update_status() {
        this.stockReconciliation.update_status();
    }
};