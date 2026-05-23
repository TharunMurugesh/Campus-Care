// static/js/app.js
"use strict";
document.addEventListener("DOMContentLoaded", function () {
    // 1. Clickable Rows for Tables
    var rows = document.querySelectorAll(".clickable-row");
    rows.forEach(function (row) {
        row.addEventListener("click", function (e) {
            // Prevent navigating if a button/form inside the row was clicked
            if (e.target.tagName !== 'BUTTON' && e.target.tagName !== 'A') {
                var href = row.getAttribute("data-href");
                if (href) {
                    window.location.href = href;
                }
            }
        });
    });
    // 2. Claim Ticket Confirmation
    var claimButtons = document.querySelectorAll(".confirm-claim");
    claimButtons.forEach(function (btn) {
        btn.addEventListener("click", function (e) {
            if (confirm("Are you sure you want to claim this ticket? You will be fully responsible for its resolution.")) {
                var form = btn.closest(".claim-form");
                if (form)
                    form.submit();
            }
        });
    });
    // 3. Dynamic Form Field Toggling for Status Update (Escalation Reason)
    var statusSelect = document.querySelector(".status-select");
    var escalationReasonField = document.getElementById("escalationReasonField");
    if (statusSelect && escalationReasonField) {
        statusSelect.addEventListener("change", function () {
            if (statusSelect.value === "ESCALATED") {
                escalationReasonField.style.display = "block";
                var input = escalationReasonField.querySelector("input");
                if (input)
                    input.required = true;
            }
            else {
                escalationReasonField.style.display = "none";
                var input = escalationReasonField.querySelector("input");
                if (input)
                    input.required = false;
            }
        });
    }
    // 4. Dynamic Form Field for User Registration (Role -> Department)
    var roleSelect = document.getElementById("roleSelect");
    var departmentField = document.getElementById("departmentField");
    if (roleSelect && departmentField) {
        roleSelect.addEventListener("change", function () {
            if (roleSelect.value === "staff") {
                departmentField.style.display = "block";
                var select = departmentField.querySelector("select");
                if (select)
                    select.required = true;
            }
            else {
                departmentField.style.display = "none";
                var select = departmentField.querySelector("select");
                if (select)
                    select.required = false;
            }
        });
    }
});
