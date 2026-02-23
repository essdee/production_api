import { createApp } from 'vue';
import WorkOrderDeliverables from "./components/Deliverables.vue"
import WorkOrderRework from "./components/WOReworkPopUp.vue"
import WOReworkDeliverable from "./components/WOReworkDeliverables.vue"
import WOReworkReceivable from "./components/WOReworkReceivables.vue"
import WorkOrderReceivables from "./components/Receivables.vue"
import WorkOrderItemView from "./components/WorkOrderItemView.vue"
import WOSummary from "./components/WoSummary.vue"
import ReworkCompletion from "./components/ReworkCompletion.vue"
import ReworkPage from "./components/ReworkPage.vue";
import RejectionPage from "./components/RejectionPage.vue";
import QualityInspection from "./components/QualityInspection.vue";

export class DeliverablesWrapper {
    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_table();
    }
    make_table() {
        this.app = createApp(WorkOrderDeliverables)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    get_deliverables_data() {
        let items = JSON.parse(JSON.stringify(this.vue.items))
        return items
    }
    load_data(item_details) {
        let items = JSON.parse(JSON.stringify(item_details));
        this.vue.load_data(items)
    }
    update_status(val) {
        this.vue.update_status(val);
    }
};

export class WOReworkPopUpWrapper {
    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_table();
    }
    make_table() {
        this.app = createApp(WorkOrderRework)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    load_data(item_details) {
        let items = JSON.parse(JSON.stringify(item_details));
        this.vue.load_data(items)
    }
    get_items() {
        let items = JSON.parse(JSON.stringify(this.vue.get_items()))
        return items
    }
};

export class WOReworkDeliverablesWrapper {
    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_table();
    }
    make_table() {
        this.app = createApp(WOReworkDeliverable)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    load_data(item_details) {
        let items = JSON.parse(JSON.stringify(item_details));
        this.vue.load_data(items)
    }
};

export class WOReworkReceivablesWrapper {
    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_table();
    }
    make_table() {
        this.app = createApp(WOReworkReceivable)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    load_data(item_details) {
        let items = JSON.parse(JSON.stringify(item_details));
        this.vue.load_data(items)
    }
    get_receivables_data() {
        let items = JSON.parse(JSON.stringify(this.vue.get_items()))
        return items
    }
};

export class ReceivablesWrapper {
    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_table();
    }
    make_table() {
        this.app = createApp(WorkOrderReceivables)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    get_receivables_data() {
        let items = JSON.parse(JSON.stringify(this.vue.items))
        return items
    }
    load_data(item_details) {
        let items = JSON.parse(JSON.stringify(item_details));
        this.vue.load_data(items)
    }
    update_status(val) {
        this.vue.update_status(val);
    }
};

export class ReworkPageWrapper {
    constructor(wrapper) {
        this.$wrapper = $(wrapper)
        this.make_app()
    }
    make_app() {
        this.app = createApp(ReworkPage)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
}

export class RejectionPageWrapper {
    constructor(wrapper) {
        this.$wrapper = $(wrapper)
        this.make_app()
    }
    make_app() {
        this.app = createApp(RejectionPage)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
}

export class WorkOrderItemViewWrapper {
    constructor(wrapper) {
        this.$wrapper = $(wrapper)
        this.make_app()
    }
    make_app() {
        this.app = createApp(WorkOrderItemView)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    load_data(item_details) {
        let items = JSON.parse(JSON.stringify(item_details))
        this.vue.load_data(items)
    }
    get_work_order_items() {
        let items = this.vue.get_items()
        for (let i = 0; i < items[0].items.length; i++) {
            items[0].items[i]['entered_qty'] = {}
        }
        return items
    }
    create_input_attributes() {
        this.vue.create_input_classes()
    }
}

export class WOSummaryWrapper {
    constructor(wrapper) {
        this.$wrapper = $(wrapper)
        this.make_app()
    }
    make_app() {
        this.app = createApp(WOSummary)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    load_data(item_details, delivered_items) {
        let items = JSON.parse(JSON.stringify(item_details))
        let delivered = JSON.parse(JSON.stringify(delivered_items))
        this.vue.load_data(items, delivered)
    }
}

export class QualityInspectionWrapper {
    constructor(wrapper) {
        this.$wrapper = $(wrapper)
        this.make_app()
    }
    make_app() {
        this.app = createApp(QualityInspection)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    get_data() {
        let items = this.vue.get_data()
        return items
    }
    unmount() {
        if (this.app) {
            this.app.unmount();
        }
    }
    load_data(data) {
        this.vue.load_data(JSON.parse(JSON.stringify(data)))
    }
}

export class ReworkCompletionWrapper {
    constructor(wrapper) {
        this.$wrapper = $(wrapper)
        this.make_app()
    }
    make_app() {
        this.app = createApp(ReworkCompletion)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
}
