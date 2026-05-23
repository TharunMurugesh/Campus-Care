// static/js/app.ts

document.addEventListener("DOMContentLoaded", () => {

    // 1. Clickable Rows for Tables
    const rows = document.querySelectorAll(".clickable-row") as NodeListOf<HTMLElement>;
    rows.forEach(row => {
        row.addEventListener("click", (e) => {
            // Prevent navigating if a button/form inside the row was clicked
            if ((e.target as HTMLElement).tagName !== 'BUTTON' && (e.target as HTMLElement).tagName !== 'A') {
                const href = row.getAttribute("data-href");
                if (href) {
                    window.location.href = href;
                }
            }
        });
    });

    // 2. Claim Ticket Confirmation
    const claimButtons = document.querySelectorAll(".confirm-claim") as NodeListOf<HTMLButtonElement>;
    claimButtons.forEach(btn => {
        btn.addEventListener("click", (e) => {
            if (confirm("Are you sure you want to claim this ticket? You will be fully responsible for its resolution.")) {
                const form = btn.closest(".claim-form") as HTMLFormElement;
                if (form) form.submit();
            }
        });
    });

    // 3. Dynamic Form Field Toggling for Status Update (Escalation Reason)
    const statusSelect = document.querySelector(".status-select") as HTMLSelectElement | null;
    const escalationReasonField = document.getElementById("escalationReasonField") as HTMLElement | null;

    if (statusSelect && escalationReasonField) {
        statusSelect.addEventListener("change", () => {
            if (statusSelect.value === "ESCALATED") {
                escalationReasonField.style.display = "block";
                const input = escalationReasonField.querySelector("input") as HTMLInputElement;
                if(input) input.required = true;
            } else {
                escalationReasonField.style.display = "none";
                const input = escalationReasonField.querySelector("input") as HTMLInputElement;
                if(input) input.required = false;
            }
        });
    }

    // 4. Dynamic Form Field for User Registration (Role -> Department)
    const roleSelect = document.getElementById("roleSelect") as HTMLSelectElement | null;
    const departmentField = document.getElementById("departmentField") as HTMLElement | null;

    if (roleSelect && departmentField) {
        roleSelect.addEventListener("change", () => {
            if (roleSelect.value === "staff") {
                departmentField.style.display = "block";
                const select = departmentField.querySelector("select") as HTMLSelectElement;
                if(select) select.required = true;
            } else {
                departmentField.style.display = "none";
                const select = departmentField.querySelector("select") as HTMLSelectElement;
                if(select) select.required = false;
            }
        });
    }
});
