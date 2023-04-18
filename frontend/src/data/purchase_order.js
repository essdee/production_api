import { createListResource, createResource } from "frappe-ui";

export let purchaseOrderForSupplier = function (supplier) {
    return createResource({
        url: "production_api.production_api.doctype.purchase_order.purchase_order.get_po_for_supplier",
        params: {
            "supplier": supplier
        },
        initialData: [],
        onSuccess(data) {
            // console.log(data)
        },
        onerror(error) {
            console.log(error)
        },
        transform(data) {
            return data.map(purchaseOrder => {
                return {
                    label: purchaseOrder.name,
                    value: purchaseOrder.name
                }
            })
        }
    })
}


