from production_api.production_api.doctype.item_price.item_price import update_all_expired_item_price

def daily():
    update_all_expired_item_price()