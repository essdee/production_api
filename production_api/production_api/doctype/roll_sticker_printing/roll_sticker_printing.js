// Copyright (c) 2023, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on('Roll Sticker Printing', {

    open_fun: function (frm) {
        frappe.ui.form
            .qz_connect()
            .then(function () {
                var f1 = [];
                window.weight = [];
                console.log("connected")
                qz.serial.setSerialCallbacks(function (evt) {
                    if (evt.type !== 'ERROR') {
                        window.weight.unshift(evt.output)
                        if (window.weight.length == 8) {
                            window.weight.pop()
                        }
                        // window.weight=evt.output
                        console.log(window.weight);

                        frm.set_value('roll_weight', window.weight[0]);
                    } else {
                        console.error(evt.exception);
                    }
                });

                qz.serial.findPorts().then(function (ports) {
                    var options = {
                        baudRate: 9600,
                        dataBits: 8,
                        stopBits: 1,
                        parity: 'NONE',
                        flowControl: 'NONE',
                        encoding: 'UTF-8',
                        rx: {
                            start: null,
                            end: null,
                            width: null,
                            untilNewline: false,
                            lengthBytes: null,
                            crcBytes: null,
                            includeHeader: false,
                            encoding: 'UTF-8'
                        }
                    };
                    if (ports.length == 0) {
                        console.log('COM1 port closed');
                    }
                    else {
                        window.port = ports[0]
                        qz.serial.openPort(ports[0], options).then(function () {
                            console.log("connected")

                        }).catch(function (err) {
                            console.error(err);
                        });
                    }
                }).catch((err) => {
                    console.log(err)
                    frappe.ui.form.qz_fail(err);
                });

            })
            .then(frappe.ui.form.qz_success)
            .catch((err) => {
                console.log(err)
                frappe.ui.form.qz_fail(err);
            });
    },
    close_fun: function (frm) {
        frappe.ui.form
            .qz_connect()
            .then(function () {
                console.log("connected")
                qz.serial.setSerialCallbacks(function (evt) {
                    if (evt.type !== 'ERROR') {
                        console.log('Serial', evt.portName, 'received output', evt.output);
                    } else {
                        console.error(evt.exception);
                    }
                });

                qz.serial.findPorts().then(function (ports) {
                    console.log(ports);
                    var options = {
                        baudRate: 9600,
                        dataBits: 8,
                        stopBits: 1,
                        parity: 'NONE',
                        flowControl: 'NONE',
                        encoding: 'UTF-8',
                        rx: {
                            start: null,
                            end: null,
                            width: null,
                            untilNewline: true,
                            lengthBytes: null,
                            crcBytes: null,
                            includeHeader: false,
                            encoding: 'UTF-8'
                        }
                    };
                    if (ports.length == 0) {
                        console.log('COM1 port closed');
                    }
                    else {
                        qz.serial.closePort(ports[0], options).then(function () { // or '/dev/ttyUSB0', etc
                            console.log("connected")

                        }).catch(function (err) {
                            console.error(err);
                        });
                    }
                }).catch((err) => {
                    console.log(err)
                    frappe.ui.form.qz_fail(err);
                });

            })
            .then(frappe.ui.form.qz_success)
            .catch((err) => {
                console.log(err)
                frappe.ui.form.qz_fail(err);
            });

    },
    refresh: function (frm) {
        cur_frm.page.btn_primary.hide()
        frm.add_custom_button('open', function () {

            frm.events.open_fun(frm)
        });
        frm.add_custom_button('close', function () {
            frm.events.close_fun(frm)

        });
        frm.add_custom_button('print', function () {

            frm.events.print1(frm)
        });


    },
    get_weight: function (frm) {
        frm.set_value('roll_weight', window.weight[0]);

    },

    clear_weight: function (frm) {

        frm.set_value('roll_no', "");
        frm.set_value('roll_weight', "");

    },

    clear: function (frm) {

        frm.set_value('lot', "");
        frm.set_value('date', "");
        frm.set_value('fabric', "");
        frm.set_value('dia', "");
        frm.set_value('color', "");
        frm.set_value('gsm', "");

    },
    print: function (frm) {
    frm.doc.lot
    frm.doc.date
    frm.doc.fabric
    frm.doc.roll_number
    frm.doc.roll_weight
    frm.doc.dia
    frm.doc.color
    frm.doc.gsm
    doc = frappe.new_doc('Task')
    doc.title = 'New Task 2'
doc.insert()


        
        // frappe.ui.form
        //     .qz_connect()
        //     .then(function () {
        //         console.log("connected")
        //         qz.serial.findPorts().then(function (ports) {
        //             console.log(ports);
        //             qz.printers.find("zebra").then(function (found) {
        //                 alert("Printer: " + found);
        //             });
        //             var config = qz.configs.create("Zebra LP2844-Z");               // Exact printer name from OS
        //             var data = ['^XA^FO50,50^ADN,36,20^FDRAW ZPL EXAMPLE^FS^XZ'];

        //             qz.print(config, data).then(function () {
        //                 alert("Sent data to printer");
        //             });

        //         }).catch((err) => {
        //             console.log(err)
        //             frappe.ui.form.qz_fail(err);
        //         });

        //     })
        //     .then(frappe.ui.form.qz_success)
        //     .catch((err) => {
        //         console.log(err)
        //         frappe.ui.form.qz_fail(err);
        //     });

    },
    print1: function (frm) {
        frappe.ui.form.qz_init().then(() => {

            qz.websocket.connect().then(function () {
                alert("Connected!");
                return qz.printers.find("zebra");
            }).then(function (printer) {
                alert("Printer: " + printer);
                var config = qz.configs.create(printer);
                var data = ['^XA^FO50,50^ADN,36,20^FDRAW ZPL EXAMPLE^FS^XZ'];
                return qz.print(config, data);
            }).catch(function (e) { console.error(e); });

        });

    }

});


//    refresh:function(frm){cur_frm.page.btn_primary.hide()},



// frm.add_custom_button('Create Membership', () => {
// 	frappe.new_doc('Library Membership', {
// 		library_member: frm.doc.date
// 	})
// })


