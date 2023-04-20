import { createListResource } from 'frappe-ui'
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