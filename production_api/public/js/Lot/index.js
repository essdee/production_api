import { createApp } from 'vue';
import LotOrder from "./components/LotOrder.vue"
import WorkStation from "./components/WorkStation.vue"
import InwardQuantityReport from "./components/InwardQuantityReport.vue";
import InhouseQuantity from "./components/InhouseQuantity.vue";
import OCRDetail from './components/OCRDetail.vue';
// import CadDetail from "./components/CadDetail.vue";

export class LotOrderWrapper {
    constructor(wrapper) {
        this.$wrapper = $(wrapper)
        this.make_app()
    }
    make_app() {
        this.app = createApp(LotOrder)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    get_data() {
        let items = JSON.parse(JSON.stringify(this.vue.list_item))
        return items
    }
    show_inputs() {
        this.vue.show_add_items()
    }
    load_data(item_details) {
        let items = JSON.parse(JSON.stringify(item_details));
        this.vue.load_data(items)
    }
}

export class OCRDetailWrapper {
    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_app();
    }
    make_app() {
        this.app = createApp(OCRDetail)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
}

export class WorkStationWrapper {
    constructor(wrapper) {
        this.$wrapper = $(wrapper)
        this.make_app()
    }
    make_app() {
        this.app = createApp(WorkStation)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    load_data(data, type) {
        let items = JSON.parse(JSON.stringify(data))
        this.vue.load_data(items, type)
    }
    set_attributes() {
        this.vue.set_attributes()
    }
    get_items() {
        return this.vue.get_items()
    }
}

export class InwardQuantityReportWrapper {
    constructor(wrapper) {
        this.$wrapper = $(wrapper)
        this.make_app()
    }
    make_app() {
        this.app = createApp(InwardQuantityReport)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
}

export class InhouseQuantityWrapper {
    constructor(wrapper) {
        this.$wrapper = $(wrapper)
        this.make_app()
    }
    make_app() {
        this.app = createApp(InhouseQuantity)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
}

// export class CadDetailWrapper {
//     constructor(wrapper){
//         this.$wrapper = $(wrapper)
//         this.make_app()
//     }
//     make_app(){
//         this.app = createApp(CadDetail)
//         SetVueGlobals(this.app)
//         this.vue = this.app.mount(this.$wrapper.get(0))
//     }
//     load_data(data){
//         this.vue.load_data(JSON.parse(JSON.stringify(data)))
//     }
//     get_data(){
//         return this.vue.get_data()
//     }
// }
