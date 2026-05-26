// Simple TS for basic client-side validation
document.addEventListener('DOMContentLoaded', () => {
    
    // File size and type validation for CSV
    const csvForm = document.getElementById('csvForm') as HTMLFormElement;
    const csvFile = document.getElementById('csvFile') as HTMLInputElement;

    if (csvForm && csvFile) {
        csvForm.addEventListener('submit', (e) => {
            const file = csvFile.files?.[0];
            if (!file) {
                e.preventDefault();
                csvFile.classList.add('is-invalid');
                return;
            }
            
            // Check file type
            if (file.type && file.type !== 'text/csv' && !file.name.endsWith('.csv')) {
                e.preventDefault();
                csvFile.classList.add('is-invalid');
                alert('Please upload a valid CSV file.');
                return;
            }

            // Check file size (max 5MB)
            const maxSize = 5 * 1024 * 1024;
            if (file.size > maxSize) {
                e.preventDefault();
                csvFile.classList.add('is-invalid');
                alert('File size exceeds 5MB limit.');
                return;
            }

            csvFile.classList.remove('is-invalid');
            
            // Show loading state
            const btn = document.getElementById('uploadBtn') as HTMLButtonElement;
            if (btn) {
                btn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Uploading...';
                btn.disabled = true;
            }
        });
    }

});
