import { createApp } from 'vue';
import ProductFileVersions from "./Product/ProductFileVersions.vue"

export default class ProductFileVersionsWrapper {
    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_body();
    }

    make_body() {
        let $page_container = $('<div class="file-uploader frappe-control">').appendTo(this.$wrapper);
        this.app = createApp(ProductFileVersions);
        this.productFileVersions = this.app.mount(this.$wrapper.get(0));
        // this.vue = new Vue({
        //     el: '.file-uploader',
        //     render: h => h(ProductFileVersions, {
        //     })
        // });
    }
};