frappe.ui.form.on("Time and Action Gantt Chart", {
    setup(frm) {
        frm.set_query("work_station", (doc) => {
            return {
                filters: {
                    action: doc.action
                }
            };
        });
    },
    refresh(frm) {
        frm.disable_save()
        frm.set_df_property("gantt_chart_html", "options", `<div id="chart_div"></div>`);
    },
    generate_gantt_chart(frm){
        if(!frm.doc.action){
            frappe.msgprint("Select an Action")
            return
        }
        else{
            loadGanttChart(frm);
        }
    }
});

function loadGanttChart(frm) {
    frappe.call({
        method:"production_api.essdee_production.doctype.time_and_action_gantt_chart.time_and_action_gantt_chart.get_chart_data",
        args :{
            action: frm.doc.action,
            work_station:frm.doc.work_station,
        },
        callback: function(r){
            const chartHTML = `
                <p class="chart-label">Gantt Chart <span id="current-timescale">Day</span> View</p>
                <div> 
                    <svg id="gantt" xmlns="http://www.w3.org/2000/svg"></svg>
                </div>
                 <div class="chart-controls">
                    <div class="button-cont">
                        <button id="day-btn">Day</button>
                        <button id="week-btn">Week</button>
                        <button id="month-btn">Month</button>
                    </div>
                </div>
                `;
                const container = frm.fields_dict.gantt_chart_html.wrapper;
                container.innerHTML = chartHTML;
                renderGanttChart(r.message);
        }
    })
}

function renderGanttChart(data) {
    const style = document.createElement("style");
    style.innerHTML = get_css();
    document.head.appendChild(style);
    const gantt = new Gantt("#gantt", data, {
        custom_popup_html: function (task) {
            return `
                <div class='details-container'>
                    <h5>${task.name}</h5>
                    <br>
                    <p>Task started on: ${task.start}</p>
                    <p>Expected to finish by ${task.end}</p>
                </div>
          `;
        },
    });

    document.getElementById("day-btn").addEventListener("click", () => {
        gantt.change_view_mode("Day");
        document.getElementById("current-timescale").innerText = "Day";
    });
    document.getElementById("week-btn").addEventListener("click", () => {
        gantt.change_view_mode("Week");
        document.getElementById("current-timescale").innerText = "Week";
    });
    document.getElementById("month-btn").addEventListener("click", () => {
        gantt.change_view_mode("Month");
        document.getElementById("current-timescale").innerText = "Month";
    });
}

function get_css(){
    return `
        .gantt .upper-text{
            font-size: 15px !important;
        }
        .gantt .lower-text{
            font-size: 14px !important;
        }
        .button-cont {
            gap: 10px;
            margin-top: 0;
        }
        .button-cont button {
            background-color: #0056b3; 
            color: white; 
            border: none; 
            border-radius: 8px; 
            padding: 5px 10px;
            font-size: 16px;
            font-family: Arial, sans-serif; 
            cursor: pointer; 
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
            transition: all 0.3s ease;
        }
        .button-cont button:hover {
            background-color: #003d80;
            box-shadow: 0 6px 12px rgba(0, 0, 0, 0.3); 
        }
        .button-cont button:active {
            background-color: #002b5c;
            transform: scale(0.95); 
        }
        .bar-label {
            font-size:14px !important;
            color : black !important;
            font-weight : 600 !important;
        }
        .popup-wrapper {
            width:300px !important;
        }
        .details-container {
            background-color: #f9f9f9;
            color: #333;
            border: 1px solid #ccc;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            max-width: 1000px;
            font-family: Arial, sans-serif;
            z-index: 1000;
        }
        .details-container h5 {
            margin: 0 0 10px 0;
            font-size: 16px;
            color: #0056b3;
        }
        .details-container p {
            margin: 5px 0;
            font-size: 14px;
            line-height: 1.5;
        }
        .chart-controls {
            text-align: right;
        }
        .chart-label {
            padding-top: 20px;
            font-size: 1.2rem;
            text-align: left;
            font-weight: 500;
            text-decoration:underline;
        }
    `;
}
