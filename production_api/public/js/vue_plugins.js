import AttributeValues from "./components/AttributeValues.vue";
import AttributeList from "./components/AttributeList.vue";
import DependentAttributeTemplate from "./components/DependentAttribute.vue";
import BomAttributeMapping from "./components/BomAttributeMapping.vue";
import ItemPriceList from "./ItemPriceList";
import ItemDetail from "./components/ItemDetails.vue";
import DDItem from "./PurchaseOrder/components/DateUpdateDialog.vue"
import PONewItem from "./PurchaseOrder/components/NewItem.vue"
import POItem from "./PurchaseOrder/components/Item.vue"
import GRNItemWrapper from "./GRN";
import GRNPurchaseOrder from "./GRN/components/GRNPurchaseOrder.vue";
import GRNWorkOrder from "./GRN/components/GRNWorkOrder.vue";
import GRNConsumedDetail from "./GRN/components/GRNConsumedDetail.vue"
import LotOrder from "./Lot/components/LotOrder.vue" 
import WorkStation from "./Lot/components/WorkStation.vue"
import TimeActionPreview from "./Lot/components/TimeActionPreview.vue"
import TimeAction from "./Lot/components/TimeAction.vue"
import TimeActionReport from "./Lot/components/TimeActionReport.vue"
import CutPlanItems from "./CuttingPlan/components/CutPlanItems.vue"
import CuttingCompletionDetail from "./CuttingPlan/components/CuttingCompletionDetail.vue"
import CuttingIncompletionDetail from "./CuttingPlan/components/CuttingIncompletionDetail.vue"
import CutPlanClothItems from "./CuttingPlan/components/CutPlanClothItems.vue"
import CombinationItemDetail from "./Item_Po_detail/CombinationItemDetail.vue"
import EmblishmentDetails from "./Item_Po_detail/EmblishmentDetails.vue"
import CuttingItemDetail from "./Item_Po_detail/CuttingItemDetail.vue"
import ClothAccessory from "./Item_Po_detail/ClothAccessory.vue"
import ClothAccessoryCombination from "./Item_Po_detail/ClothAccessoryCombination.vue"
import AccessoryItems from "./Item_Po_detail/AccessoryItems.vue"
import { StockEntryWrapper, StockReconciliationWrapper, LotTransferWrapper } from "./Stock";
import WorkOrderDeliverables from "./WorkOrder/components/Deliverables.vue"
import WorkOrderReceivables from "./WorkOrder/components/Receivables.vue"
import WorkOrderItemView from "./WorkOrder/components/WorkOrderItemView.vue"
import LaySheetCloths from "./CuttingLaySheet/components/LaySheetCloths.vue"
import DeliveryChallan from "./Delivery_Challan/components/deliverable_items.vue"

// Product Development
import { ProductFileVersionsWrapper, ProductCostingListWrapper } from "./ProductDevelopment"

import EventBus from "./bus.js";

import { EditBOMAttributeMappingWrapper, BOMAttributeMappingWrapper } from "./ItemBOM";

import { createApp } from 'vue';

frappe.provide("frappe.production.ui");
frappe.provide("frappe.production.product_development.ui");

frappe.production.ui.eventBus = EventBus;


frappe.production.ui.ItemAttributeValues = class {
    constructor({ wrapper, attr_values, attr_name } = {}) {
        this.$wrapper = $(wrapper);
        this.attr_values = attr_values;
        this.attr_name = attr_name;
        this.make_body();
    }
    
    make_body() {
        this.$page_container = $('<div class="attribute-value-template frappe-control">').appendTo(this.$wrapper);
        this.app = createApp(AttributeValues);
        this.app.mount(this.$wrapper.get(0));
        // this.vue = new Vue({
        //     el: '.attribute-value-template',
        //     render: h => h(AttributeValues, {
        //     }),
        // });
    }
};

frappe.production.ui.ItemAttributeList = class {
    constructor({ wrapper, attr_values, attr_name } = {}) {
        this.$wrapper = $(wrapper);
        this.attr_values = attr_values;
        this.attr_name = attr_name;
        this.make_body();
    }

    make_body() {
        this.$page_container = $('<div class="attribute-list-template frappe-control">').appendTo(this.$wrapper);
        this.app = createApp(AttributeList);
        this.app.mount(this.$wrapper.get(0));
        // this.vue = new Vue({
        //     el: '.attribute-list-template',
        //     render: h => h(AttributeList, {
        //     }),
        // });
    }
};

frappe.production.ui.ItemDependentAttributeDetail = class {
    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_body();
    }

    make_body() {
        this.$page_container = $('<div class="dependent-attribute-template frappe-control">').appendTo(this.$wrapper);
        this.app = createApp(DependentAttributeTemplate);
        this.app.mount(this.$wrapper.get(0));
        // this.vue = new Vue({
        //     el: '.dependent-attribute-template',
        //     render: h => h(DependentAttributeTemplate, {
        //     }),
        // });
    }
};

frappe.production.ui.DateDialog = class {
    constructor(wrapper, items){
        this.$wrapper = $(wrapper)
        this.items = items
        this.make_body();
    }
    make_body(){
        this.app = createApp(DDItem, {items: this.items})
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    get_items(){
        let items = JSON.parse(JSON.stringify(this.vue.item_data));
        return items
    }
}
frappe.production.ui.CombinationItemDetail = class {
    constructor(wrapper){
        this.$wrapper = $(wrapper);
        this.make_body();
    }
    make_body(){
        this.app = createApp(CombinationItemDetail)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    load_data(items){
        this.vue.load_data(JSON.parse(JSON.stringify(items)))
    }
    set_attributes(){
        this.vue.set_attributes();
    }
    get_data(){
        let items = JSON.parse(JSON.stringify(this.vue.get_data()))
        return items
    }
}

frappe.production.ui.EmblishmentDetails = class {
    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_body();
    }
    make_body(){
        this.app = createApp(EmblishmentDetails)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    load_data(items){
        this.vue.load_items(JSON.parse(JSON.stringify(items)))
    }
    get_items(){
        let items = JSON.parse(JSON.stringify(this.vue.get_items()))
        return items
    }
}

frappe.production.ui.CuttingItemDetail = class {
    constructor(wrapper){
        this.$wrapper = $(wrapper);
        this.make_body();
    }
    make_body(){
        this.app = createApp(CuttingItemDetail)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    load_data(items){
        this.vue.load_data(items)
    }
    set_attributes(){
        this.vue.set_attributes();
    }
    get_data(){
        let items = JSON.parse(JSON.stringify(this.vue.get_data()))
        return items
    }   
}

frappe.production.ui.ClothAccessory = class {
    constructor(wrapper){
        this.$wrapper = $(wrapper);
        this.make_body();
    }
    make_body(){
        this.app = createApp(ClothAccessory)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    load_data(items){
        this.vue.load_data(items)
    }
    set_attributes(){
        this.vue.set_attributes();
    }
    get_data(){
        let items = JSON.parse(JSON.stringify(this.vue.get_data()))
        return items
    }   
}

frappe.production.ui.ClothAccessoryCombination = class {
    constructor(wrapper){
        this.$wrapper = $(wrapper);
        this.make_body();
    }
    make_body(){
        this.app = createApp(ClothAccessoryCombination)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    load_data(items){
        this.vue.load_data(items)
    }
    set_attributes(){
        this.vue.set_attributes();
    }
    get_data(){
        let items = JSON.parse(JSON.stringify(this.vue.get_data()))
        return items
    }   
}

frappe.production.ui.AccessoryItems = class {
    constructor(wrapper){
        this.$wrapper = $(wrapper);
        this.make_body();
    }
    make_body(){
        this.app = createApp(AccessoryItems)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    load_data(items){
        this.vue.load_data(JSON.parse(items))
    }
    get_data(){
        let items = JSON.parse(JSON.stringify(this.vue.get_items()))
        return items
    }
}


frappe.production.ui.BomItemAttributeMapping = BOMAttributeMappingWrapper;

frappe.production.ui.ItemPriceList = ItemPriceList;

frappe.production.ui.ItemDetail = function(wrapper, type, data) {
    let $wrapper = $(wrapper);
    let $page_container = $('<div class="item-detail frappe-control">').appendTo($wrapper);
    let app = createApp(ItemDetail)
    app.mount(this.$page_container)
    // let vue = new Vue({
    //     el: '.item-detail',
    //     render: h => h(ItemDetail, {
    //         props: {
    //             type,
    //             data
    //         }
    //     })
    // });
};

// frappe.production.ui.PurchaseOrderItem = function(wrapper) {
//     let $wrapper = $(wrapper);
//     let $page_container = $('<div class="item frappe-control">').appendTo($wrapper);
//     return new Vue({
//         el: '.item',
//         render: h => h(POItem, {
//         })
//     });
// };

frappe.production.ui.LotOrder = class {
    constructor(wrapper){
        this.$wrapper = $(wrapper)
        this.make_app()
    }
    make_app(){
        this.app = createApp(LotOrder)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    get_data(){
        let items = JSON.parse(JSON.stringify(this.vue.list_item))
        return items
    }
    load_data(item_details){
        let items = JSON.parse(JSON.stringify(item_details));
        this.vue.load_data(items)
    }
}

frappe.production.ui.TimeAction = class {
    constructor(wrapper){
        this.$wrapper = $(wrapper)
        this.make_app()
    }
    make_app(){
        this.app = createApp(TimeAction)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    get_data(){
        let get_data = this.vue.get_data()
        let items = JSON.parse(JSON.stringify(get_data.items))
        let changed = JSON.parse(JSON.stringify(get_data.changed))
        return {
            "items":items,
            "changed":changed,
        }
    }
    load_data(item_details){
        let items = JSON.parse(JSON.stringify(item_details));
        this.vue.load_data(items)
    }
}

frappe.production.ui.TimeActionReport = class {
    constructor(wrapper){
        this.$wrapper = $(wrapper)
        this.make_app()
    }
    make_app(){
        this.app = createApp(TimeActionReport)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
}

frappe.production.ui.WorkStation = class {
    constructor(wrapper){
        this.$wrapper = $(wrapper)
        this.make_app()
    }
    make_app(){
        this.app = createApp(WorkStation)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    load_data(data, type){
        let items = JSON.parse(JSON.stringify(data))
        this.vue.load_data(items, type)
    }
    set_attributes(){
        this.vue.set_attributes()
    }
    get_items(){
        return this.vue.get_items()
    }
}

frappe.production.ui.TimeActionPreview = class {
    constructor(wrapper){
        this.$wrapper = $(wrapper)
        this.make_app()
    }
    make_app(){
        this.app = createApp(TimeActionPreview)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    load_data(data){
        let items = JSON.parse(JSON.stringify(data))
        this.vue.load_data(items)
    }
}

frappe.production.ui.WorkOrderItemView = class {
    constructor(wrapper){
        this.$wrapper = $(wrapper)
        this.make_app()
    }
    make_app(){
        this.app = createApp(WorkOrderItemView)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    load_data(item_details){
        let items = JSON.parse(JSON.stringify(item_details))
        this.vue.load_data(items)
    }
    get_work_order_items(){
        let items = this.vue.get_items()
        for(let i = 0 ; i < items[0].items.length; i++){
            items[0].items[i]['entered_qty'] = {}
        }
        return items
    }
    create_input_attributes(){
        this.vue.create_input_classes()
    }
}

frappe.production.ui.CutPlanItems = class {
    constructor(wrapper){
        this.$wrapper = $(wrapper)
        this.make_app()
    }
    make_app(){
        this.app = createApp(CutPlanItems)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    load_data(item_details, length){
        let items = JSON.parse(JSON.stringify(item_details))
        this.vue.load_data(items)
        if (length > 0){
            this.vue.update_docstatus()
        }
    }
    get_items(){
        let items = this.vue.get_items()
        return items
    }
}

frappe.production.ui.GRNPurchaseOrder = class {
    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_body();
    }
    
    make_body() {
        this.app = createApp(GRNPurchaseOrder);
        SetVueGlobals(this.app)
        this.grn = this.app.mount(this.$wrapper.get(0));
    }
    
    updateWrapper(wrapper) {
        this.$wrapper = $(wrapper);
        $(this.vue.$el).appendTo(this.$wrapper)
    }
    
    get_items() {
        return this.grn.get_items();
    }
    
    load_data(data, skip_watch=false) {
        this.grn.load_data(data, skip_watch);
    }
    update_status() {
        this.grn.update_status();
    }
}

frappe.production.ui.GRNWorkOrder = class {
    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_body();
    }
    
    make_body() {
        this.app = createApp(GRNWorkOrder);
        SetVueGlobals(this.app)
        this.grn = this.app.mount(this.$wrapper.get(0));
    }
    
    updateWrapper(wrapper) {
        this.$wrapper = $(wrapper);
        $(this.vue.$el).appendTo(this.$wrapper)
    }
    
    get_items() {
        return this.grn.get_items();
    }
    
    load_data(data, skip_watch=false) {
        this.grn.load_data(data, skip_watch);
    }
    update_status() {
        this.grn.update_status();
    }
}




frappe.production.ui.CuttingCompletionDetail = class {
    constructor(wrapper){
        this.$wrapper = $(wrapper)
        this.make_app()
    }
    make_app(){
        this.app = createApp(CuttingCompletionDetail)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    load_data(item_details){
        item_details = "["+item_details+"]"
        let items = JSON.parse(JSON.stringify(item_details))
        this.vue.load_data(items)
    }
}
frappe.production.ui.CuttingIncompletionDetail = class {
    constructor(wrapper){
        this.$wrapper = $(wrapper)
        this.make_app()
    }
    make_app(){
        this.app = createApp(CuttingIncompletionDetail)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    load_data(item_details){
        item_details = "["+item_details+"]"
        let items = JSON.parse(JSON.stringify(item_details))
        this.vue.load_data(items)
    }
}

frappe.production.ui.CutPlanClothItems = class {
    constructor(wrapper){
        this.$wrapper = $(wrapper)
        this.make_app()
    }
    make_app(){
        this.app = createApp(CutPlanClothItems)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    load_data(item_details,type){
        let items = JSON.parse(JSON.stringify(item_details))
        this.vue.load_data(items,type)
    }
    get_items(){
        let items = this.vue.get_items()
        return items
    }
}

frappe.production.ui.LaySheetCloths = class {
    constructor(wrapper){
        this.$wrapper = $(wrapper)
        this.make_app()
    }
    make_app(){
        this.app = createApp(LaySheetCloths)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    load_data(item_details){
        let items = JSON.parse(JSON.stringify(item_details))
        this.vue.load_data(items)
    }
    get_items(){
        let items = this.vue.get_items()
        return items
    }
}

frappe.production.ui.PurchaseOrderItem = class {
    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_body();
    }

    make_body() {
        let $page_container = $('<div class="item frappe-control">').appendTo(this.$wrapper);
        this.app = createApp(POItem)
        SetVueGlobals(this.app);
        this.vue = this.app.mount(this.$wrapper.get(0))
        // this.vue = new Vue({
        //     el: '.item',
        //     render: h => h(POItem, {
        //     })
        // });
    }

    updateWrapper(wrapper) {
        // this.$wrapper = $(wrapper);
        // let $page_container = $('<div class="item frappe-control">').appendTo(this.$wrapper);
        // this.app.unmount();
        // this.vue = this.app.mount(this.$wrapper.get(0))
    }

    get_items() {
        // let items = JSON.parse(JSON.stringify(this.vue.$children[0].items));
        let items = JSON.parse(JSON.stringify(this.vue.items));
        for (let i = 0; i < items.length; i++) {
            for (let j = 0; j < items[i].items.length; j++) {
                if (items[i].items[j].additional_parameters) {
                    items[i].items[j].additional_parameters = JSON.stringify(items[i].items[j].additional_parameters)
                }
            }
        }
        return items;
    }

    load_data(item_details) {
        let items = JSON.parse(JSON.stringify(item_details));
        for (let i = 0; i < items.length; i++) {
            for (let j = 0; j < items[i].items.length; j++) {
                if (items[i].items[j].additional_parameters) {
                    items[i].items[j].additional_parameters = JSON.parse(items[i].items[j].additional_parameters)
                }
            }
        }
        this.vue.load_data(items);
    }

    update_status() {
        this.vue.update_status();
    }
};
frappe.production.ui.Deliverables = class {
    constructor(wrapper){
        this.$wrapper = $(wrapper);
        this.make_table();
    }
    make_table(){
        this.app = createApp(WorkOrderDeliverables)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    get_deliverables_data(){
        let items = JSON.parse(JSON.stringify(this.vue.items))
        return items
    }
    load_data(item_details){
        let items = JSON.parse(JSON.stringify(item_details));
        this.vue.load_data(items)
    }
    update_status(val) {
        this.vue.update_status(val);
    }
};

frappe.production.ui.GRNConsumed = class {
    constructor(wrapper){
        this.$wrapper = $(wrapper);
        this.make_table();
    }
    make_table(){
        this.app = createApp(GRNConsumedDetail)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    get_deliverables_data(){
        let items = JSON.parse(JSON.stringify(this.vue.items))
        return items
    }
    load_data(item_details){
        let items = JSON.parse(JSON.stringify(item_details));
        this.vue.load_data(items)
    }
    update_status(val) {
        this.vue.update_status(val);
    }
};
frappe.production.ui.Receivables = class {
    constructor(wrapper){
        this.$wrapper = $(wrapper);
        this.make_table();
    }
    make_table(){
        this.app = createApp(WorkOrderReceivables)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    get_receivables_data(){
        let items = JSON.parse(JSON.stringify(this.vue.items))
        return items
    }
    load_data(item_details){
        let items = JSON.parse(JSON.stringify(item_details));
        this.vue.load_data(items)
    }
    update_status(val) {
        this.vue.update_status(val);
    }
};

frappe.production.ui.Delivery_Challan = class {
    constructor(wrapper, items){
        this.$wrapper = $(wrapper);
        this.items = items;
        this.make_table();
    }
    make_table(){
        this.app = createApp(DeliveryChallan, {items: this.items});
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    get_data(){
        let items = JSON.parse(JSON.stringify(this.vue.deliverables_item))
        for(let i = 0 ; i < items.length ; i++){
            for(let j = 0 ; j < items[i].items.length ; j++){
                Object.keys(items[i].items[j].values).forEach(key => {
                    if(items[i].items[j].values[key].delivered_quantity == "" || items[i].items[j].values[key].delivered_quantity == null){
                        items[i].items[j].values[key].delivered_quantity = 0
                    }
                })
            }
        }
        return items
    }
    update_status() {
        this.vue.update_status();
    }

}
// Basic structure to integrate vue

// frappe.ui.production.sampleName = class {
//     constructor(wrapper){
//         this.$wrapper = $(wrapper)
//         this.make_app()
//     }
//     make_app(){
//         this.app = createApp('sample_vue_app_which_is_imported')
//         SetVueGlobals(this.app)
//         this.vue = this.app.mount(this.$wrapper.get(0))
//     }
//     get_page_data(){
//         let data = 'this.vue.variable_name_which_is_in_the_vue_page_._that_should_be_defined_inside_the_defineExpose_componenet'
//         return data
//     }
// }

frappe.production.ui.DateDialog = class {
    constructor(wrapper, items){
        this.$wrapper = $(wrapper)
        this.items = items
        this.make_body();
    }
    make_body(){
        this.app = createApp(DDItem, {items: this.items})
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    get_items(){
        let items = JSON.parse(JSON.stringify(this.vue.item_data));
        return items
    }
}

frappe.production.ui.GRNItem = GRNItemWrapper
frappe.production.ui.StockEntryItem = StockEntryWrapper
frappe.production.ui.StockReconciliationItem = StockReconciliationWrapper
frappe.production.ui.LotTransferItem = LotTransferWrapper
frappe.production.ui.EditBOMAttributeMapping = EditBOMAttributeMappingWrapper

// Product Development
frappe.production.product_development.ui.ProductFileVersions = ProductFileVersionsWrapper
frappe.production.product_development.ui.ProductCostingList = ProductCostingListWrapper


