let autocompleteInstance = null;

document.addEventListener('DOMContentLoaded', () => {
    autocompleteInstance = new StockAutocomplete({
        inputId: 'stock-code-input',
        onSelect: (item) => {
            // Redirect to detail page
            window.location.href = `/stock_price/stock/detail/${item.short_code}/`;
        }
    });

    const input = document.getElementById('stock-code-input');
    // Basic Enter support for manual typing (searchStock logic)
    input.addEventListener("keypress", function (event) {
        if (event.key === "Enter") {
            searchStock();
        }
    });
});

function searchStock() {
    const input = document.getElementById('stock-code-input');
    const val = input.value.trim();

    if (!val) {
        alert('종목을 입력해주세요.');
        return;
    }

    // 1. If it's a 6-digit code, go directly
    if (/^\d{6}$/.test(val)) {
        window.location.href = `/stock_price/stock/detail/${val}/`;
        return;
    }

    // 2. Try to resolve name using Autocomplete instance
    if (autocompleteInstance) {
        const match = autocompleteInstance.findStock(val);
        if (match) {
            window.location.href = `/stock_price/stock/detail/${match.short_code}/`;
            return;
        }
    }

    // 3. Fallback
    alert('종목을 선택하거나 올바른 종목명/코드를 입력해주세요.');
}
