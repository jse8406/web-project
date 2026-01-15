        function showTab(tabName, event) {
            // Hide all sections
            document.querySelectorAll('.section-wrapper').forEach(el => el.classList.remove('active'));
            // Remove active class from all buttons
            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));

            // Show selected section
            document.getElementById(tabName).classList.add('active');
            // Add active class to clicked button
            if (event) {
                event.target.classList.add('active');
            }
        }

        // Format numbers with commas (Optional: if not done by template filter)
        document.addEventListener("DOMContentLoaded", () => {
            document.querySelectorAll('.price-align').forEach(el => {
                const text = el.innerText.trim();
                // Check if it's a pure number string (ignoring % and space)
                if (/^-?\d+$/.test(text) || /^-?\d+\.\d+$/.test(text)) {
                    // el.innerText =  Number(text).toLocaleString();
                    // Actually django intcomma filter is better but we didn't load humanize
                    // Let's leave it for now or implement a simple JS formatter if needed
                    const num = parseFloat(text);
                    if (!isNaN(num)) {
                        el.innerText = num.toLocaleString();
                    }
                } else if (text.endsWith('%')) {
                    // It's a rate, maybe colored
                }
            });
        });
