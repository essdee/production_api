<template>
    <div ref="root">
        <h5>Product File Versions</h5>
        <div class="d-flex flex-row flex-wrap">
            <div class="card card-body m-1" v-for="(files, upload_type) in files_by_upload_type">
                <h5>{{ upload_type }}</h5>
                <span>
                    Latest version: <a :href="files[0].file_url" target="_blank">{{ files[0].filename }}</a>
                </span>
                <div>
                    <a @click.prevent="toggle_display(upload_type)">
                        Show all versions
                    </a>
                    <div v-show="visible_files.includes(upload_type)">
                        <div class="address-box">
                            <div v-for="file in files_except_first(files)">
                                <a :href="file.file_url" target="_blank">{{ file.filename }}</a>
                            </div>
                        </div>
                    </div>
                </div>
                <!-- <div v-for="file in files_except_first(files)">
                    <a :href="file.file_url" target="_blank">{{ file.filename }}</a>
                </div> -->
            </div>
        </div>
        <div class="row">
            <div class="upload-type-control col-md-6"></div>
            <div class="attach-control col-md-6"></div>
        </div>
        <div v-show="file.uploading">
            {{ file['progress'] }} {{ file['total'] }}
            <!-- Add Progress Bar Component-->
            <div class="progress">
                <div class="progress-bar" :style="{ width: progress + '%' }">
                    <span>{{ progress }}%</span>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup>

import { ref, onMounted, computed, watch } from 'vue';

const root = ref(null)

let upload_type_input = null
let attach = null
let upload_promise = null

const attach_input = ref(null)
const file = ref({})
const method = 'production_api.product_development.doctype.product.product.upload_product_file'
const files = ref(cur_frm.doc.product_file_versions)
const visible_files = ref([])

onMounted(() => {
    create_upload_type_input()
});

const progress = computed(() => {
    return Math.round(file.value.progress / file.value.total * 100);
});

// Get files grouped by upload type and sorted by version
const files_by_upload_type = computed(() => {
    let files_by_upload_type = {};
    for (let file of files.value) {
        if (!files_by_upload_type[file.product_upload_type]) {
            files_by_upload_type[file.product_upload_type] = [];
        }
        files_by_upload_type[file.product_upload_type].push(file);
    }
    for (let upload_type in files_by_upload_type) {
        files_by_upload_type[upload_type].sort((a, b) => {
            return b.version_number - a.version_number;
        });
    }
    return files_by_upload_type;
})

function files_except_first(files) {
    return files.slice(1);
}

function toggle_display(upload_type) {
    if (visible_files.value.includes(upload_type)) {
        visible_files.value = visible_files.value.filter((item) => {
            return item != upload_type;
        });
    } else {
        visible_files.value.push(upload_type);
    }
}

function create_upload_type_input() {
    let $el = root.value
    $($el).find('.upload-type-control').html("");
    upload_type_input = frappe.ui.form.make_control({
        parent: $($el).find('.upload-type-control'),
        df: {
            fieldtype: 'Link',
            options: 'Product Upload Type',
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
    // let me = this;
    let $el = root.value
    $($el).find('.attach-control').html("");
    if (!upload_type_input.get_value()) {
        attach = null;
        return;
    }
    let upload_type = upload_type_input.get_value();
    let allowed_file_types = (await frappe.db.get_value('Product Upload Type', upload_type, 'allowed_upload_types')).message.allowed_upload_types;
    console.log(allowed_file_types);
    let options = {
        restrictions: {},
        doctype: cur_frm.doc.doctype,
        docname: cur_frm.doc.name,
        fieldname: 'file',
        as_dataurl: true,
        // method: 'production_api.product_development.doctype.product.product.upload_product_file',
        on_success: (f) => {
            file.value = f;
            console.log(f);
            upload_promise = upload_file(file, upload_type);
        }
    };
    if (allowed_file_types) {
        allowed_file_types = JSON.parse(allowed_file_types);
        console.log(allowed_file_types);
        options.restrictions['allowed_file_types'] = allowed_file_types;
    }
    attach = frappe.ui.form.make_control({
        parent: $($el).find('.attach-control'),
        df: {
            fieldtype: 'Attach',
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

                    // if (this.on_success) {
                    // 	this.on_success(file_doc, r);
                    // }

                    // if (i == this.files.length - 1 && this.files.every(file => file.request_succeeded)) {
                    // 	this.close_dialog = true;
                    // }

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


        if (file.value.optimize) {
            form_data.append('optimize', true);
        }

        xhr.send(form_data);
    });
}
</script>

<style scoped>
    .shell {
        height: 6px;
        width: 250px;
        border: 1px solid #aaa;
        border-radius: 13px;
        /* padding: 3px; */
    }

    .bar {
        background: linear-gradient(to right, #B993D6, #8CA6DB);
        height: 6px;
        width: 15px;
        border-radius: 13px;
    }

    /* .bar span {
        float: right;
        padding: 4px 5px;
        color: #fff;
        font-size: 0.7em
    } */

    .card {
        background-color: var(--card-bg);
        border-color: var(--border-color);
    }
</style>

