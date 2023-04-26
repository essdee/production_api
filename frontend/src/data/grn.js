import { createListResource, createResource } from 'frappe-ui'
import { computed } from 'vue'

export let grns = createListResource({
    doctype: "Goods Received Note",
    fields: ["name", "supplier", "against", "against_id", "modified"],
    auto: true,
    onSuccess(data) {
        console.log("Data: ", data)
    },
    onerror(error) {
        console.log(error)
    },
})

export let grnCreate = function (against, purchaseOrder, deliveryLocation, deliveryDate, items) { 
    return createResource({
        url: "production_api.production_api.doctype.goods_received_note.goods_received_note.save_goods_received_note",
        method: "POST",
        params: {
            "against": against,
            "purchase_order": purchaseOrder,
            "delivery_date": deliveryDate,
            "delivery_location": deliveryLocation,
            "items": items
        },
        onerror(error) {
            console.log(error)
        },
    })
}