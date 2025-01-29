import logging
from logging.handlers import RotatingFileHandler
import frappe


LOG_FILENAME = {
    "work_order":{
        "logger":None,
        "path":'../logs/wo_log_handler.log',
    },
    "delivery_challan":{
        "logger":None,
        "path":'../logs/dc_log_handler.log',
    },
    "goods_received_note":{
        "logger":None,
        "path":'../logs/grn_log_handler.log',
    }
}
module_name = __name__

def get_module_logger(doctype):
    logger = LOG_FILENAME[doctype]["logger"]
    if  logger is not None:
        return logger
    file_name = LOG_FILENAME[doctype]["path"]
    formatter = logging.Formatter('[%(levelname)s] %(asctime)s | %(message)s: %(pathname)s\n')

    handler = RotatingFileHandler(
        file_name, maxBytes=100000, backupCount=20)
    handler.setFormatter(formatter)

    logger = logging.getLogger(doctype)
    logger.setLevel(frappe.log_level or logging.DEBUG)
    logger.addHandler(handler)
    logger.propagate = False
    LOG_FILENAME[doctype]['logger'] = logger
    return logger