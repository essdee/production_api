from production_api.production_api.doctype.item_price.item_price import update_all_expired_item_price
from production_api.production_api.doctype.purchase_order.purchase_order import close_delivered_po

def daily():
    update_all_expired_item_price()
    close_delivered_po()