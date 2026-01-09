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
import GRNReturnItem from "./GRN/components/GRNReturnItem.vue"
import GRNConsumedDetail from "./GRN/components/GRNConsumedDetail.vue"
import {
    LotOrderWrapper,
    OCRDetailWrapper,
    WorkStationWrapper,
    InwardQuantityReportWrapper,
    InhouseQuantityWrapper,
    // CadDetailWrapper,
} from "./Lot";
import TimeActionPreview from "./TimeAndAction/TimeActionPreview.vue"
import TimeAction from "./TimeAndAction/TimeAction.vue"
import TimeActionReport from "./TimeAndAction/TimeActionReport.vue"
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
import BundleGroup from "./Item_Po_detail/BundleGroup.vue"
import { StockEntryWrapper, StockReconciliationWrapper, LotTransferWrapper, StockUpdateWrapper } from "./Stock";
import {
    DeliverablesWrapper,
    WOReworkPopUpWrapper,
    WOReworkDeliverablesWrapper,
    WOReworkReceivablesWrapper,
    ReceivablesWrapper,
    ReworkPageWrapper,
    WorkOrderItemViewWrapper,
    WOSummaryWrapper,
    QualityInspectionWrapper,
    ReworkCompletionWrapper,
} from "./WorkOrder";

import LaySheetCloths from "./CuttingLaySheet/components/LaySheetCloths.vue"
import LaySheetAccessory from "./CuttingLaySheet/components/LaySheetAccessory.vue"
import DeliveryChallan from "./Delivery_Challan/components/deliverable_items.vue"
import CuttingMarker from "./Cutting_Marker/components/cutting_marker.vue"
import TimeAndActionWeeklyReport from "./TimeAndAction/TimeAndActionWeeklyReport.vue"
import TandAUpdate from "./TimeAndAction/TandAUpdate.vue"
import TimeAndActionOrderTracking from "./TimeAndAction/TimeAndActionTracking.vue"
import CutPanelMovementBundle from "./Cut_Panel_Movement/components/CutPanelMovementBundle.vue"
import StockSummary from "./components/StockSummary.vue"
import ReturnItemsPopUp from "./Delivery_Challan/components/ReturnItemsPopUp.vue"
import SuggestedVendorBillDeliveryPerson from "./VendorBillTracking/components/SuggestedVendorBillDeliveryPerson.vue";
import CutBundleEdit from "./Cut_Bundle_Edit/components/CutBundleEdit.vue";
import DailyProductionReport from "./CuttingLaySheet/components/DailyProductionReport.vue";
import DailyCutSheetReport from "./CuttingLaySheet/components/DailyCutSheetReport.vue";
import GRNPacking from "./GRN/components/GRNPacking.vue";
import {
    FinishingGRNWrapper,
    FinishingDetailWrapper,
    AlternativeItemWrapper,
    AlternativeDetailWrapper,
    FinishingInwardWrapper,
    FinishingIroningExcessWrapper,
    FinishingOCRWrapper,
    FinishingPackReturnWrapper,
    FinishingPlanCompleteTransferWrapper,
    FinishingPlanDispatchWrapper,
    FinishingOldLotTransferWrapper,
    FinishingQtyDetailWrapper,
} from "./Finishing";

import ProductionOrder from "./ProductionOrder/components/ProductionOrder.vue";
import UpdatePrice from "./ProductionOrder/components/UpdatePrice.vue";
import ActionDetail from "./ActionMaster/ActionDetail.vue"
import WorkInProgress from "./components/WorkInProgress.vue"
import MonthWiseDetailReport from "./components/MonthWiseDetailReport.vue"
import SizeWiseStockReport from "./components/SizeWiseStockDetail.vue"
import ColourWiseDiffReport from "./components/ColourWiseDiffReport.vue"
import InvoiceWoItems from "./PurchaseInvoice/components/InvoiceWOItems.vue"
import RecutPrintPanelDetail from "./CuttingPlan/components/RecutPrintPanelDetails.vue"
import RecutPrintPanelView from "./CuttingPlan/components/RecutPrintPanelView.vue"
import MultiCCR from "./CuttingPlan/components/MultiCCR.vue"

// Product Development
import {
    ProductFileVersionsWrapper,
    ProductCostingListWrapper,
    ProductImageListWrapper,
    ProductTrimColourCombWrapper,
    ProductMeasurementWrapper,
    ProductSilhoutteWrapper,
    ProductGraphicsWrapper,
    ProductMeasurementImageWrapper,
} from "./ProductDevelopment"

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
    constructor(wrapper, items) {
        this.$wrapper = $(wrapper)
        this.items = items
        this.make_body();
    }
    make_body() {
        this.app = createApp(DDItem, { items: this.items })
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    get_items() {
        let items = JSON.parse(JSON.stringify(this.vue.item_data));
        return items
    }
}
frappe.production.ui.CombinationItemDetail = class {
    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_body();
    }
    make_body() {
        this.app = createApp(CombinationItemDetail)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    load_data(items) {
        this.vue.load_data(JSON.parse(JSON.stringify(items)))
    }
    set_attributes() {
        this.vue.set_attributes();
    }
    get_data() {
        let items = JSON.parse(JSON.stringify(this.vue.get_data()))
        return items
    }
}

frappe.production.ui.EmblishmentDetails = class {
    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_body();
    }
    make_body() {
        this.app = createApp(EmblishmentDetails)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    load_data(items) {
        this.vue.load_items(JSON.parse(JSON.stringify(items)))
    }
    get_items() {
        let items = JSON.parse(JSON.stringify(this.vue.get_items()))
        return items
    }
}

frappe.production.ui.CuttingItemDetail = class {
    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_body();
    }
    make_body() {
        this.app = createApp(CuttingItemDetail)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    load_data(items) {
        this.vue.load_data(items)
    }
    set_attributes() {
        this.vue.set_attributes();
    }
    get_data() {
        let items = JSON.parse(JSON.stringify(this.vue.get_data()))
        return items
    }
}

frappe.production.ui.ClothAccessory = class {
    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_body();
    }
    make_body() {
        this.app = createApp(ClothAccessory)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    load_data(items) {
        this.vue.load_data(items)
    }
    set_attributes() {
        this.vue.set_attributes();
    }
    get_data() {
        let items = JSON.parse(JSON.stringify(this.vue.get_data()))
        return items
    }
}

frappe.production.ui.ClothAccessoryCombination = class {
    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_body();
    }
    make_body() {
        this.app = createApp(ClothAccessoryCombination)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    load_data(items) {
        this.vue.load_data(items)
    }
    set_attributes() {
        this.vue.set_attributes();
    }
    get_data() {
        let items = JSON.parse(JSON.stringify(this.vue.get_data()))
        return items
    }
}

frappe.production.ui.AccessoryItems = class {
    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_body();
    }
    make_body() {
        this.app = createApp(AccessoryItems)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    load_data(items) {
        this.vue.load_data(JSON.parse(items))
    }
    get_data() {
        let items = JSON.parse(JSON.stringify(this.vue.get_items()))
        return items
    }
}

frappe.production.ui.BundleGroup = class {
    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_app()
    }
    make_app() {
        this.app = createApp(BundleGroup)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    get_items() {
        return this.vue.get_items()
    }
}

frappe.production.ui.BomItemAttributeMapping = BOMAttributeMappingWrapper;

frappe.production.ui.ItemPriceList = ItemPriceList;

frappe.production.ui.ItemDetail = function (wrapper, type, data) {
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

frappe.production.ui.TimeAction = class {
    constructor(wrapper) {
        this.$wrapper = $(wrapper)
        this.make_app()
    }
    make_app() {
        this.app = createApp(TimeAction)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    async get_data() {
        let get_data = await this.vue.get_data()
        let items = JSON.parse(JSON.stringify(get_data.items))
        let changed = get_data.changed
        return new Promise((resolve) => {
            resolve({
                "items": items,
                "changed": changed,
            })
        })
    }
    load_data(item_details) {
        let items = JSON.parse(JSON.stringify(item_details));
        this.vue.load_data(items)
    }
}

frappe.production.ui.TimeActionReport = class {
    constructor(wrapper) {
        this.$wrapper = $(wrapper)
        this.make_app()
    }
    make_app() {
        this.app = createApp(TimeActionReport)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
}

frappe.production.ui.GRNPacking = class {
    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_app()
    }
    make_app() {
        this.app = createApp(GRNPacking)
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

frappe.production.ui.ProductionOrder = class {
    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_app()
    }
    make_app() {
        this.app = createApp(ProductionOrder)
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

frappe.production.ui.UpdatePrice = class {
    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_app()
    }
    make_app() {
        this.app = createApp(UpdatePrice)
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

frappe.production.ui.InvoiceWoItems = class {
    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_app()
    }
    make_app() {
        this.app = createApp(InvoiceWoItems)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    load_data(data) {
        this.vue.load_data(data)
    }
}

frappe.production.ui.TimeAndActionWeeklyReport = class {
    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_app()
    }
    make_app() {
        this.app = createApp(TimeAndActionWeeklyReport)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
}

frappe.production.ui.ActionDetail = class {
    constructor(wrapper) {
        this.$wrapper = $(wrapper)
        this.make_app()
    }
    make_app() {
        this.app = createApp(ActionDetail)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    load_data(data, options, preview = false) {
        this.vue.load_data(JSON.parse(JSON.stringify(data)), options, preview)
    }
    get_data() {
        return this.vue.get_items()
    }
}

frappe.production.ui.TandAUpdate = class {
    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_app()
    }
    make_app() {
        this.app = createApp(TandAUpdate)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
}

frappe.production.ui.TimeAndActionOrderTracking = class {
    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_app()
    }
    make_app() {
        this.app = createApp(TimeAndActionOrderTracking)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
}

frappe.production.ui.DailyProductionReport = class {
    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_app()
    }
    make_app() {
        this.app = createApp(DailyProductionReport)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
}

frappe.production.ui.DailyCutSheetReport = class {
    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_app()
    }
    make_app() {
        this.app = createApp(DailyCutSheetReport)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
}

frappe.production.ui.StockSummary = class {
    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_app()
    }
    make_app() {
        this.app = createApp(StockSummary)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
}

frappe.production.ui.TimeActionPreview = class {
    constructor(wrapper) {
        this.$wrapper = $(wrapper)
        this.make_app()
    }
    make_app() {
        this.app = createApp(TimeActionPreview)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    load_data(data, start_date) {
        let items = JSON.parse(JSON.stringify(data))
        this.vue.load_data(items, start_date)
    }
}

frappe.production.ui.WorkInProgress = class {
    constructor(wrapper) {
        this.$wrapper = $(wrapper)
        this.make_app()
    }
    make_app() {
        this.app = createApp(WorkInProgress)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
}

frappe.production.ui.MonthWiseDetailReport = class {
    constructor(wrapper) {
        this.$wrapper = $(wrapper)
        this.make_app()
    }
    make_app() {
        this.app = createApp(MonthWiseDetailReport)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
}

frappe.production.ui.SizeWiseStockReport = class {
    constructor(wrapper) {
        this.$wrapper = $(wrapper)
        this.make_app()
    }
    make_app() {
        this.app = createApp(SizeWiseStockReport)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
}

frappe.production.ui.ColourWiseDiffReport = class {
    constructor(wrapper) {
        this.$wrapper = $(wrapper)
        this.make_app()
    }
    make_app() {
        this.app = createApp(ColourWiseDiffReport)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
}

frappe.production.ui.CutPlanItems = class {
    constructor(wrapper) {
        this.$wrapper = $(wrapper)
        this.make_app()
    }
    make_app() {
        this.app = createApp(CutPlanItems)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    load_data(item_details, length) {
        let items = JSON.parse(JSON.stringify(item_details))
        this.vue.load_data(items)
        if (length > 0) {
            this.update_status()
        }
    }
    get_items() {
        let items = this.vue.get_items()
        return items
    }
    update_status() {
        this.vue.update_docstatus()
    }
}

frappe.production.ui.CuttingMarker = class {
    constructor(wrapper) {
        this.$wrapper = $(wrapper)
        this.make_app()
    }
    make_app() {
        this.app = createApp(CuttingMarker)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    load_data(items) {
        let items_all = JSON.parse(JSON.stringify(items))
        this.vue.load_data(items_all)
    }
    get_items() {
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
    load_data(data, skip_watch = false) {
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
    load_data(data, skip_watch = false) {
        this.grn.load_data(data, skip_watch);
    }
    update_status() {
        this.grn.update_status();
    }
}

frappe.production.ui.GRNReturnItem = class {
    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_body();
    }
    make_body() {
        this.app = createApp(GRNReturnItem);
        SetVueGlobals(this.app)
        this.grn = this.app.mount(this.$wrapper.get(0));
    }
    load_data(data, skip_watch = false) {
        this.grn.load_data(data, skip_watch);
    }
}

frappe.production.ui.CuttingCompletionDetail = class {
    constructor(wrapper) {
        this.$wrapper = $(wrapper)
        this.make_app()
    }
    make_app() {
        this.app = createApp(CuttingCompletionDetail)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    load_data(item_details, pop_up) {
        item_details = "[" + item_details + "]"
        let items = JSON.parse(JSON.stringify(item_details))
        this.vue.load_data(items, pop_up)
    }
    get_items() {
        let items = this.vue.get_items()
        console.log(items)
        return items
    }
}
frappe.production.ui.CuttingIncompletionDetail = class {
    constructor(wrapper) {
        this.$wrapper = $(wrapper)
        this.make_app()
    }
    make_app() {
        this.app = createApp(CuttingIncompletionDetail)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    load_data(item_details) {
        item_details = "[" + item_details + "]"
        let items = JSON.parse(JSON.stringify(item_details))
        this.vue.load_data(items)
    }
}

frappe.production.ui.RecutPrintPanelDetail = class {
    constructor(wrapper) {
        this.$wrapper = $(wrapper)
        this.make_app()
    }
    make_app() {
        this.app = createApp(RecutPrintPanelDetail)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    get_items() {
        return this.vue.get_items()
    }
    load_data() {
        this.vue.load_data()
    }
}

frappe.production.ui.RecutPrintPanelView = class {
    constructor(wrapper) {
        this.$wrapper = $(wrapper)
        this.make_app()
    }
    make_app() {
        this.app = createApp(RecutPrintPanelView)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    load_data(type) {
        this.vue.load_data(type)
    }
}

frappe.production.ui.MultiCCR = class {
    constructor(wrapper) {
        this.$wrapper = $(wrapper)
        this.make_app()
    }
    make_app() {
        this.app = createApp(MultiCCR)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
}

frappe.production.ui.CutPlanClothItems = class {
    constructor(wrapper) {
        this.$wrapper = $(wrapper)
        this.make_app()
    }
    make_app() {
        this.app = createApp(CutPlanClothItems)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    load_data(item_details, type) {
        let items = JSON.parse(JSON.stringify(item_details))
        this.vue.load_data(items, type)
    }
    get_items() {
        let items = this.vue.get_items()
        return items
    }
}

frappe.production.ui.LaySheetCloths = class {
    constructor(wrapper) {
        this.$wrapper = $(wrapper)
        this.make_app()
    }
    make_app() {
        this.app = createApp(LaySheetCloths)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    load_data(item_details) {
        let items = JSON.parse(JSON.stringify(item_details))
        this.vue.load_data(items)
    }
    get_items() {
        let items = this.vue.get_items()
        return items
    }
}

frappe.production.ui.LaySheetAccessory = class {
    constructor(wrapper) {
        this.$wrapper = $(wrapper)
        this.make_app()
    }
    make_app() {
        this.app = createApp(LaySheetAccessory)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    load_data(item_details) {
        let items = JSON.parse(JSON.stringify(item_details))
        this.vue.load_data(items)
    }
    get_items() {
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

frappe.production.ui.GRNConsumed = class {
    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_table();
    }
    make_table() {
        this.app = createApp(GRNConsumedDetail)
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

frappe.production.ui.Delivery_Challan = class {
    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_table();
    }
    make_table() {
        this.app = createApp(DeliveryChallan);
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    get_data() {
        let items = this.vue.get_items()
        return items
    }
    update_status() {
        this.vue.update_status();
    }
    load_data(item) {
        let items = JSON.parse(JSON.stringify(item))
        this.vue.load_data(items)
    }
}

frappe.production.ui.ReturnItemsPopUp = class {
    constructor(wrapper) {
        this.$wrapper = $(wrapper);
        this.make_table();
    }
    make_table() {
        this.app = createApp(ReturnItemsPopUp);
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    load_data(item) {
        let items = JSON.parse(JSON.stringify(item));
        this.vue.load_data(items);
    }
    get_data() {
        let items = this.vue.get_items()
        return items
    }
}

frappe.production.ui.CutPanelMovementBundle = class {
    constructor(wrapper) {
        this.$wrapper = $(wrapper)
        this.make_app()
    }
    make_app() {
        this.app = createApp(CutPanelMovementBundle)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    load_data(item) {
        let items = JSON.parse(JSON.stringify(item))
        this.vue.load_data(items)
    }
    get_items() {
        return this.vue.get_items()
    }
}

frappe.production.ui.CutBundleEdit = class {
    constructor(wrapper) {
        this.$wrapper = $(wrapper)
        this.make_app()
    }
    make_app() {
        this.app = createApp(CutBundleEdit)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    load_data(item) {
        let items = JSON.parse(JSON.stringify(item))
        this.vue.load_data(items)
    }
    get_items() {
        return this.vue.get_items()
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
    constructor(wrapper, items) {
        this.$wrapper = $(wrapper)
        this.items = items
        this.make_body();
    }
    make_body() {
        this.app = createApp(DDItem, { items: this.items })
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    get_items() {
        let items = JSON.parse(JSON.stringify(this.vue.item_data));
        return items
    }
}

frappe.production.ui.SuggestedVendorBillDeliveryPerson = class {
    constructor(wrapper) {
        this.$wrapper = $(wrapper)
        this.make_body()
    }
    make_body() {
        this.app = createApp(SuggestedVendorBillDeliveryPerson)
        SetVueGlobals(this.app)
        this.vue = this.app.mount(this.$wrapper.get(0))
    }
    update_for_new_supplier(supplier) {
        this.vue.update_for_new_supplier(supplier);
    }
}

frappe.production.ui.GRNItem = GRNItemWrapper
frappe.production.ui.StockEntryItem = StockEntryWrapper
frappe.production.ui.StockReconciliationItem = StockReconciliationWrapper
frappe.production.ui.LotTransferItem = LotTransferWrapper
frappe.production.ui.StockUpdateItem = StockUpdateWrapper
frappe.production.ui.EditBOMAttributeMapping = EditBOMAttributeMappingWrapper

// Lot components
frappe.production.ui.LotOrder = LotOrderWrapper
frappe.production.ui.OCRDetail = OCRDetailWrapper
frappe.production.ui.WorkStation = WorkStationWrapper
frappe.production.ui.InwardQuantityReport = InwardQuantityReportWrapper
frappe.production.ui.InhouseQuantity = InhouseQuantityWrapper
// frappe.production.ui.CadDetail = CadDetailWrapper;

// WorkOrder components
frappe.production.ui.Deliverables = DeliverablesWrapper
frappe.production.ui.WOReworkPopUp = WOReworkPopUpWrapper
frappe.production.ui.WOReworkDeliverables = WOReworkDeliverablesWrapper
frappe.production.ui.WOReworkReceivables = WOReworkReceivablesWrapper
frappe.production.ui.Receivables = ReceivablesWrapper
frappe.production.ui.ReworkPage = ReworkPageWrapper
frappe.production.ui.WorkOrderItemView = WorkOrderItemViewWrapper
frappe.production.ui.WOSummary = WOSummaryWrapper
frappe.production.ui.QualityInspection = QualityInspectionWrapper
frappe.production.ui.ReworkCompletion = ReworkCompletionWrapper

// Finishing components
frappe.production.ui.FinishingGRN = FinishingGRNWrapper
frappe.production.ui.FinishingDetail = FinishingDetailWrapper
frappe.production.ui.AlternativeItem = AlternativeItemWrapper
frappe.production.ui.AlternativeDetail = AlternativeDetailWrapper
frappe.production.ui.FinishingInward = FinishingInwardWrapper
frappe.production.ui.FinishingIroningExcess = FinishingIroningExcessWrapper
frappe.production.ui.FinishingOCR = FinishingOCRWrapper
frappe.production.ui.FinishingPackReturn = FinishingPackReturnWrapper
frappe.production.ui.FinishingPlanCompleteTransfer = FinishingPlanCompleteTransferWrapper
frappe.production.ui.FinishingPlanDispatch = FinishingPlanDispatchWrapper
frappe.production.ui.FinishingOldLotTransfer = FinishingOldLotTransferWrapper
frappe.production.ui.FinishingQtyDetail = FinishingQtyDetailWrapper

// Product Development
frappe.production.product_development.ui.ProductFileVersions = ProductFileVersionsWrapper
frappe.production.product_development.ui.ProductCostingList = ProductCostingListWrapper
frappe.production.product_development.ui.ProductImageList = ProductImageListWrapper
frappe.production.product_development.ui.ProductTrimColourComb = ProductTrimColourCombWrapper
frappe.production.product_development.ui.ProductMeasurement = ProductMeasurementWrapper
frappe.production.product_development.ui.ProductSilhoutte = ProductSilhoutteWrapper
frappe.production.product_development.ui.ProductGraphics = ProductGraphicsWrapper
frappe.production.product_development.ui.ProductMeasurementImage = ProductMeasurementImageWrapper
