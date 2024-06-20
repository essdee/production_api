import { createApp } from 'vue';
import GRNItem from "./components/GRNItem.vue"
// import Vue from 'vue';
// import VueCompositionAPI from '@vue/composition-api';

// Vue.use(VueCompositionAPI);
export default class GRNItemWrapper {
    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_body();
    }

    make_body() {
        let $page_container = $('<div class="item frappe-control">').appendTo(this.$wrapper);
        this.app = createApp(GRNItem);
        this.grn = this.app.mount(this.$wrapper.get(0));
        // this.vue = new Vue({
        //     el: '.item',
        //     render: h => h(GRNItem, {
        //     })
        // });
    }

    updateWrapper(wrapper) {
        this.$wrapper = $(wrapper);
        $(this.vue.$el).appendTo(this.$wrapper)
    }

    get_items() {
        // console.log(JSON.stringify(this.grn.get_items()))
        return this.grn.get_items();
    }

    load_data(data, skip_watch=false) {
        // console.log(JSON.stringify(data))
        this.grn.load_data(data, skip_watch);
    }
    
    update_status() {
        this.grn.update_status();
    }
    // get_items() {
    //     return this.vue.$children[0].get_items();
    // }

    // load_data(data, skip_watch=false) {
    //     this.vue.$children[0].load_data(data, skip_watch);
    // }
    
    // update_status() {
    //     this.vue.$children[0].update_status();
    // }
};