from production_api.production_api.doctype.item_price.item_price import update_all_expired_item_price
from production_api.production_api.doctype.purchase_order.purchase_order import close_delivered_po
from production_api.production_api.doctype.process_cost.process_cost import update_expired_process_cost


def daily():
    update_all_expired_item_price()
    update_expired_process_cost()
    close_delivered_po()