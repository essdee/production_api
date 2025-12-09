<template>
    <div ref="root">
        <h5>Product Graphics</h5>
        <div>
            <div class="card card-body m-1" v-for="(row, idx) in files" :key="idx">
                <div style="display: flex;">
                    <div>
                        <strong>{{ row.upload_name }}: </strong> 
                        <a :href="row.graphic_image" target="_blank">{{ row.graphic_image }}</a>
                    </div>
                    <div v-if="doctype != 'Product Release'">
                        <button class="btn btn-danger btn-sm ml-2" @click="removeImage(idx, row)">
                            Remove
                        </button>
                    </div>
                </div>
            </div>
        </div>
        <div class="row" v-if="doctype != 'Product Release'">
            <div class="upload-type-control col-md-6"></div>
            <div class="attach-control col-md-6"></div>
        </div>
    </div>
</template>

<script setup>

import { ref, onMounted, computed, watch } from 'vue';

const root = ref(null)

let upload_type_input = null
let attach = null
let upload_promise = null
let doctype = cur_frm.doc.doctype
let box_detail = ref(false)

const attach_input = ref(null)
const file = ref({})
const method = 'production_api.product_development.doctype.product.product.upload_graphics_file'
const files = ref(cur_frm.doc.product_designs)
const visible_files = ref([])

onMounted(() => {
    if(doctype != 'Product Release'){
        create_upload_type_input()
    }
});

function create_upload_type_input() {
    let $el = root.value
    $($el).find('.upload-type-control').html("");
    upload_type_input = frappe.ui.form.make_control({
        parent: $($el).find('.upload-type-control'),
        df: {
            fieldtype: 'Data',
            label: 'Upload Type',
            reqd: true,
            onchange: () => {
                create_attach_control();
            }
        },
        render_input: true,
    });
}

async function create_attach_control() {
    let $el = root.value
    $($el).find('.attach-control').html("");
    if (!upload_type_input.get_value()) {
        attach = null;
        return;
    }
    let upload_type = upload_type_input.get_value();
    let options = {
        restrictions: {},
        doctype: cur_frm.doc.doctype,
        docname: cur_frm.doc.name,
        fieldname: 'file',
        as_dataurl: true,
        on_success: (f) => {
            file.value = f;
            upload_promise = upload_file(file, upload_type);
        }
    };
    
    attach = frappe.ui.form.make_control({
        parent: $($el).find('.attach-control'),
        df: {
            fieldtype: 'Attach Image',
            label: 'Attach',
            reqd: true,
            options: options,
            on_attach: () => {
                attach.set_value(upload_type_input.get_value());
            }
        },
        render_input: true,
    });
}

function frappeConfirm(message) {
    return new Promise((resolve) => {
        frappe.confirm(
            message,
            () => resolve(true), 
            () => resolve(false) 
        );
    });
}


async function removeImage(idx, row) {
    let yes = await frappeConfirm(`Remove ${row.upload_name}?`);
    if (!yes) return;

    frappe.call({
        method: "production_api.product_development.doctype.product.product.remove_graphic_image",
        args: {
            detail: row,
            docname: cur_frm.doc.name
        },
        callback: function () {
            cur_frm.reload_doc();
        }
    });
}

function upload_file(file, type) {
    return new Promise((resolve, reject) => {
        let xhr = new XMLHttpRequest();
        xhr.upload.addEventListener('loadstart', (e) => {
            file.value.uploading = true;
        })
        xhr.upload.addEventListener('progress', (e) => {
            if (e.lengthComputable) {
                frappe.show_progress('Uploading',e.loaded,e.total,e.loaded + "/" + e.total,true)
                file.value.progress = e.loaded;
                file.value.total = e.total;
            }
        })
        xhr.upload.addEventListener('load', (e) => {
            file.value.uploading = false;
            resolve();
        })
        xhr.addEventListener('error', (e) => {
            file.value.failed = true;
            reject();
        })
        xhr.onreadystatechange = () => {
            if (xhr.readyState == XMLHttpRequest.DONE) {
                if (xhr.status === 200) {
                    file.value.request_succeeded = true;
                    let r = null;
                    let file_doc = null;
                    try {
                        r = JSON.parse(xhr.responseText);
                        if (r.message.doctype === 'File') {
                            file_doc = r.message;
                        }
                    } catch(e) {
                        r = xhr.responseText;
                    }
                    file.value.doc = file_doc;
                } else if (xhr.status === 403) {
                    file.value.failed = true;
                    let response = JSON.parse(xhr.responseText);
                    file.value.error_message = `Not permitted. ${response._error_message || ''}`;

                } else if (xhr.status === 413) {
                    file.value.failed = true;
                    file.value.error_message = 'Size exceeds the maximum allowed file size.';

                } else {
                    file.value.failed = true;
                    file.value.error_message = xhr.status === 0 ? 'XMLHttpRequest Error' : `${xhr.status} : ${xhr.statusText}`;

                    let error = null;
                    try {
                        error = JSON.parse(xhr.responseText);
                    } catch(e) {
                        // pass
                    }
                    frappe.request.cleanup({}, error);
                }
            }
        }
        xhr.open('POST', '/api/method/upload_file', true);
        xhr.setRequestHeader('Accept', 'application/json');
        xhr.setRequestHeader('X-Frappe-CSRF-Token', frappe.csrf_token);

        let form_data = new FormData();
        if (file.value.file_obj) {
            form_data.append('file', file.value.file_obj, file.value.name);
        }
        form_data.append('is_private', +file.value.private);
        if (file.value.file_url) {
            form_data.append('file_url', file.value.file_url);
        }
        let filename = cur_frm.doc.name + '_' + type + '_' + file.value.name;
        form_data.append('file_name', filename);
        form_data.append('doctype', cur_frm.doc.doctype);
        form_data.append('docname', cur_frm.doc.name);
        form_data.append('fieldname', 'file');
        form_data.append('method', method);
        form_data.append('box_data', "accessory")

        if (file.value.optimize) {
            form_data.append('optimize', true);
        }
        xhr.send(form_data);
    });
}

function load_data(value){
    if(value){
        box_detail.value = true
        files.value = cur_frm.doc.product_box_details
    }
}

defineExpose({
    load_data
})

</script>
<style scoped>
.card {
    background-color: var(--card-bg);
    border-color: var(--border-color);
}
</style>

