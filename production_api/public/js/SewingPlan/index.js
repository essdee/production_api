import { createApp } from 'vue';
import SewingPlan from './SewingPlan.vue'

export class SewingPlanWrapper {
    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_app()
    }
    make_app() {
        this.app = createApp(SewingPlan)
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