frappe.provide("my_app");

my_app.mount_testing_banner = function () {
    const bannerId = "my-testing-banner";
    frappe.call({
        method: "production_api.utils.get_site_config_value",
        callback: function(r) {
            if (r.message.hasOwnProperty("staging")) {
                if (!document.getElementById(bannerId)) {
                    let banner = document.createElement("div");
                    banner.id = bannerId;
            
                    banner.innerHTML = `
                        <div style="
                            position: fixed;
                            top: 10px;
                            left: 10px;
                            background: #ff4d4f;
                            color: white;
                            font-weight: bold;
                            padding: 6px 12px;
                            border-radius: 6px;
                            box-shadow: 0 2px 6px rgba(0,0,0,0.2);
                            z-index: 9999;
                            font-size: 24px;
                        ">
                            🚧 TESTING
                        </div>
            
                        <div style="
                            position: fixed;
                            top: 0;
                            right: 0;
                            width: 0;
                            height: 0;
                            border-left: 200px solid transparent;
                            border-top: 200px solid #ff4d4f;
                            z-index: 9999;
                        ">
                            <div style="
                                position: absolute;
                                top: -150px;
                                right: 17px;
                                transform: rotate(-45deg);
                                color: white;
                                font-weight: bold;
                                font-size: 30px;
                            ">
                                TEST
                            </div>
                        </div>
                    `;
            
                    document.body.appendChild(banner);
                }
            }
        }
    });
};

$(document).ready(function () {
    my_app.mount_testing_banner();
});

frappe.router.on("change", () => {
    my_app.mount_testing_banner();
});
