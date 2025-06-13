import pymysql
import frappe

class MySQLConnection:
	
	def __init__(self):
		self.connection = None
		self.create_connection()

	def create_connection(self):
  
		required_keys = ["sms_old_database_host", "sms_old_database_name", "sms_old_database_port", "sms_old_database_user", "sms_old_database_password"]
		
		doc = frappe.get_single("Stock Settings")
		
		for key in required_keys:
			if not getattr(doc,key):
				frappe.throw(f"Please Set The Migration Properties")

		try:
			self.connection = pymysql.connect(
				host = getattr(doc,"sms_old_database_host"),
				user = getattr(doc,"sms_old_database_user"),
				password = doc.get_password("sms_old_database_password"),
				db = getattr(doc,"sms_old_database_name"),
				port = int(getattr(doc,"sms_old_database_port"))
			)
		except Exception as e:
			frappe.throw(f"Can't Make Connection: {str(e)}")

	def get_connection(self):
		if not self.connection or not self.connection.open:
			self.create_connection()
		return self.connection

def get_connection():
	
	mysql_connection = MySQLConnection()
	connection =  mysql_connection.get_connection()
	
	return connection
