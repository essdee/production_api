import { createApp } from 'vue';
import StockItem from "./StockEntry/StockEntry.vue"
import StockReconciliation from "./StockReconciliation/StockReconciliation.vue"
import LotTransfer from "./LotTransfer/LotTransfer.vue"
import StockUpdate from "./StockUpdate/StockUpdate.vue"

export class StockEntryWrapper {
    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_body();
    }

    make_body() {
        let $page_container = $('<div class="item frappe-control">').appendTo(this.$wrapper);
        this.app = createApp(StockItem);
        SetVueGlobals(this.app);
        this.stockEntry = this.app.mount(this.$wrapper.get(0))
        // this.vue = new Vue({
        //     el: '.item',
        //     render: h => h(StockItem, {
        //     })
        // });
        // this.stockEntry = this.vue.$children[0];
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
        this.app = createApp(StockReconciliation);
        SetVueGlobals(this.app);
        this.stockReconciliation = this.app.mount(this.$wrapper.get(0))
        // this.vue = new Vue({
        //     el: '.item',
        //     render: h => h(StockReconciliation, {
        //     })
        // });
        // this.stockReconciliation = this.vue.$children[0];
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

export class LotTransferWrapper {
    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_body();
    }

    make_body() {
        let $page_container = $('<div class="item frappe-control">').appendTo(this.$wrapper);
        this.app = createApp(LotTransfer);
        SetVueGlobals(this.app);
        this.lotTransfer = this.app.mount(this.$wrapper.get(0));
        // this.vue = new Vue({
        //     el: '.item',
        //     render: h => h(LotTransfer, {
        //     })
        // });
        // this.lotTransfer = this.vue.$children[0];
    }

    updateWrapper(wrapper) {
        this.$wrapper = $(wrapper);
        $(this.vue.$el).appendTo(this.$wrapper)
    }

    get_items() {
        return this.lotTransfer.get_items();
    }

    load_data(data) {
        console.log("Loading Data", data)
        this.lotTransfer.load_data(data);
    }
    
    update_status() {
        this.lotTransfer.update_status();
    }
};

export class StockUpdateWrapper {
    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_body();
    }

    make_body() {
        let $page_container = $('<div class="item frappe-control">').appendTo(this.$wrapper);
        this.app = createApp(StockUpdate);
        SetVueGlobals(this.app);
        this.stockUpdate = this.app.mount(this.$wrapper.get(0))
    }

    updateWrapper(wrapper) {
        this.$wrapper = $(wrapper);
        $(this.vue.$el).appendTo(this.$wrapper)
    }

    get_items() {
        return this.stockUpdate.get_items();
    }

    load_data(data) {
        this.stockUpdate.load_data(data);
    }
    
    update_status() {
        this.stockUpdate.update_status();
    }
};
