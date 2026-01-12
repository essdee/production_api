import { createApp } from 'vue';
import FinishingGRN from "./FinishingGRN.vue";
import FinishingDetail from "./FinishingDetail.vue"
import FinishingQtyDetail from "./FinishingQtyDetail.vue"
import FinishingInward from "./FinishingInward.vue"
import FinishingOldLotTransfer from "./FinishingOldLotTransfer.vue"
import FinishingIroningExcess from "./FinishingIroningExcess.vue";
import FinishingOCR from "./FinishingOCR.vue"
import FinishingPackReturn from "./FinishingPackReturn.vue"
import FinishingPlanCompleteTransfer from "./FinishingPlanCompleteTransfer.vue";
import FinishingPlanDispatch from "./FinishingPlanDispatch.vue";
import AlternativeDetail from "./AlternativeDetail.vue"
import AlternativeItem from "./AlternativeItem.vue"

export class FinishingGRNWrapper {
    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_app()
    }
    make_app() {
        this.app = createApp(FinishingGRN)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    load_data(data) {
        this.vue.load_data(data)
    }
    get_data() {
        let items = JSON.parse(JSON.stringify(this.vue.get_items()))
        return items
    }
}

export class FinishingDetailWrapper {
    constructor(wrapper) {
        this.$wrapper = $(wrapper)
        this.make_app()
    }
    make_app() {
        this.app = createApp(FinishingDetail)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    load_data(data) {
        this.vue.load_data(JSON.parse(JSON.stringify(data)))
    }
}

export class AlternativeItemWrapper {
    constructor(wrapper, data) {
        this.$wrapper = $(wrapper)
        this.make_app()
        this.load_data(data)
    }
    make_app() {
        this.app = createApp(AlternativeItem)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    load_data(data) {
        this.vue.load_data(JSON.parse(JSON.stringify(data)))
    }
    get_data() {
        return this.vue.get_items()
    }
}

export class AlternativeDetailWrapper {
    constructor(wrapper) {
        this.$wrapper = $(wrapper)
        this.make_app()
    }
    make_app() {
        this.app = createApp(AlternativeDetail)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
}

export class FinishingInwardWrapper {
    constructor(wrapper) {
        this.$wrapper = $(wrapper)
        this.make_app()
    }
    make_app() {
        this.app = createApp(FinishingInward)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    load_data(data) {
        this.vue.load_data(JSON.parse(JSON.stringify(data)))
    }
}

export class FinishingIroningExcessWrapper {
    constructor(wrapper) {
        this.$wrapper = $(wrapper)
        this.make_app()
    }
    make_app() {
        this.app = createApp(FinishingIroningExcess)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    load_data(data) {
        this.vue.load_data(JSON.parse(JSON.stringify(data)))
    }
}

export class FinishingOCRWrapper {
    constructor(wrapper) {
        this.$wrapper = $(wrapper)
        this.make_app()
    }
    make_app() {
        this.app = createApp(FinishingOCR)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    load_data(data) {
        this.vue.load_data(JSON.parse(JSON.stringify(data)))
    }
}

export class FinishingPackReturnWrapper {
    constructor(wrapper) {
        this.$wrapper = $(wrapper)
        this.make_app()
    }
    make_app() {
        this.app = createApp(FinishingPackReturn)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    load_data(data) {
        this.vue.load_data(JSON.parse(JSON.stringify(data)))
    }
}

export class FinishingPlanCompleteTransferWrapper {
    constructor(wrapper) {
        this.$wrapper = $(wrapper)
        this.make_app()
    }
    make_app() {
        this.app = createApp(FinishingPlanCompleteTransfer)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
}

export class FinishingPlanDispatchWrapper {
    constructor(wrapper) {
        this.$wrapper = $(wrapper)
        this.make_app()
    }
    make_app() {
        this.app = createApp(FinishingPlanDispatch)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    load_data(data) {
        this.vue.load_data(JSON.parse(JSON.stringify(data)))
    }
    get_data() {
        return this.vue.get_data()
    }
}

export class FinishingOldLotTransferWrapper {
    constructor(wrapper) {
        this.$wrapper = $(wrapper)
        this.make_app()
    }
    make_app() {
        this.app = createApp(FinishingOldLotTransfer)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
}

export class FinishingQtyDetailWrapper {
    constructor(wrapper) {
        this.$wrapper = $(wrapper)
        this.make_app()
    }
    make_app() {
        this.app = createApp(FinishingQtyDetail)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    load_data(data) {
        this.vue.load_data(JSON.parse(JSON.stringify(data)))
    }
}
