import { createApp } from 'vue';
import ProductFileVersions from "./Product/ProductFileVersions.vue"
import ProductCostingList from "./Product/ProductCostingList.vue"
import ProductImageList from './Product/ProductImageList.vue';
import ProductTrimColourComb from "./Product/ProductTrimColourComb.vue"
import ProductMeasurement from "./Product/ProductMeasurement.vue";
import ProductSilhoutte from "./Product/ProductSilhoutte.vue"
import ProductGraphics from './Product/ProductGraphics.vue'
import ProductMeasurementImage from './Product/ProductMeasurementImage.vue'

export class ProductFileVersionsWrapper {
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

export class ProductCostingListWrapper {
    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_body();
    }

    make_body() {
        let $page_container = $('<div class="costing-list frappe-control">').appendTo(this.$wrapper);
        this.app = createApp(ProductCostingList);
        this.productCostingList = this.app.mount(this.$wrapper.get(0));
        // this.vue = new Vue({
        //     el: '.costing-list',
        //     render: h => h(ProductCostingList, {
        //     })
        // });
    }
};

export class ProductImageListWrapper {
    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_body();
    }

    make_body() {
        this.app = createApp(ProductImageList);
        this.productImageList = this.app.mount(this.$wrapper.get(0));
    }
    get_data() {
        return this.productImageList.get_data()
    }
    load_data(data, view) {
        this.productImageList.load_data(JSON.parse(JSON.stringify(data)), view)
    }
}

export class ProductTrimColourCombWrapper {
    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_body();
    }

    make_body() {
        this.app = createApp(ProductTrimColourComb);
        this.productTrimColourComb = this.app.mount(this.$wrapper.get(0));
    }
    get_data() {
        return this.productTrimColourComb.get_data()
    }
    load_data(data, view) {
        this.productTrimColourComb.load_data(JSON.parse(JSON.stringify(data)), view)
    }
}

export class ProductMeasurementWrapper {
    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_body();
    }

    make_body() {
        this.app = createApp(ProductMeasurement);
        this.productMeasurement = this.app.mount(this.$wrapper.get(0));
    }
    get_data() {
        return this.productMeasurement.get_data()
    }
    load_data(data) {
        this.productMeasurement.load_data(JSON.parse(JSON.stringify(data)))
    }
}

export class ProductSilhoutteWrapper {
    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_body();
    }

    make_body() {
        this.app = createApp(ProductSilhoutte);
        this.productSilhoutte = this.app.mount(this.$wrapper.get(0));
    }

    load_data(data, text) {
        this.productSilhoutte.load_data(JSON.parse(JSON.stringify(data)), text)
    }
}

export class ProductGraphicsWrapper {
    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_body();
    }

    make_body() {
        this.app = createApp(ProductGraphics);
        this.productGraphics = this.app.mount(this.$wrapper.get(0));
    }
    load_data(value) {
        this.productGraphics.load_data(value)
    }
}

export class ProductMeasurementImageWrapper {
    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_body();
    }

    make_body() {
        this.app = createApp(ProductMeasurementImage);
        this.productMeasurementImage = this.app.mount(this.$wrapper.get(0));
    }
}