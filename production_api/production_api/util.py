import frappe

def send_submitted_doc(doc):
	shortned_link = frappe.new_doc("Shortened Link")
	shortned_link.document_type = "Purchase Order"
	shortned_link.document_linked = doc.name
	shortned_link.insert()
	shortned_url_domain = frappe.get_doc("MRP Settings").shortned_url_domain
	link = f"{shortned_url_domain}/{shortned_link.name}"
	# Fetch contact doc
	# If contact doc has phone number and site has SMS settings set send sms using send_sms()

	msg = f"""Dear {doc.contact_person} Bill No: {doc.name} Dt: {doc.name} L.R.No: {doc.name} Cartons dispatched: {doc.name} CARTONS. Total: {doc.total} Thank you.
	Increase the ease of doing business by downloading our app {link}
	- Essdee"""
	print(msg)
	if doc.contact_mobile:
		send_sms([doc.contact_mobile], msg)
	# TODO If contact doc has email send email with PDF attachment using frappe.sendmail() 


def send_sms(receiver_list, msg, sender_name="", success_msg=True):

	import json

	if isinstance(receiver_list, str):
		receiver_list = json.loads(receiver_list)
		if not isinstance(receiver_list, list):
			receiver_list = [receiver_list]

	receiver_list = validate_receiver_nos(receiver_list)

	arg = {
		"receiver_list": receiver_list,
		"message": frappe.safe_decode(msg).encode("utf-8"),
		"success_msg": success_msg,
	}

	if frappe.db.get_single_value("SMS Settings", "sms_gateway_url"):
		send_via_gateway(arg)
	else:
		msgprint(_("Please Update SMS Settings"))

def send_via_gateway(arg):
	ss = frappe.get_doc("SMS Settings", "SMS Settings")
	headers = get_headers(ss)
	use_json = headers.get("Content-Type") == "application/json"

	message = frappe.safe_decode(arg.get("message"))
	args = {ss.message_parameter: message}
	for d in ss.get("parameters"):
		if not d.header:
			args[d.parameter] = d.value

	success_list = []
	for d in arg.get("receiver_list"):
		args[ss.receiver_parameter] = d
		status = send_request(ss.sms_gateway_url, args, headers, ss.use_post, use_json)

		if 200 <= status < 300:
			success_list.append(d)

	if len(success_list) > 0:
		args.update(arg)
		# create_sms_log(args, success_list)
		if arg.get("success_msg"):
			frappe.msgprint(_("SMS sent to following numbers: {0}").format("\n" + "\n".join(success_list)))