import { createListResource, createResource } from "frappe-ui";

export let purchaseOrdersForSupplier = function (supplier) {
    return createResource({
        url: "production_api.production_api.doctype.purchase_order.purchase_order.get_po_for_supplier",
        params: {
            "supplier": supplier
        },
        onerror(error) {
            console.log(error)
        },
    })
}

export let purchaseOrderItems = function (purchaseOrder) {
    return createResource({
        url: "production_api.production_api.doctype.purchase_order.purchase_order.get_po_items",
        params: {
            "purchase_order": purchaseOrder
        },
        onerror(error) {
            console.log(error)
        },
    })
}


