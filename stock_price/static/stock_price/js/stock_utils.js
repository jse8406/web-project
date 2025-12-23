/**
 * Shared Stock Utilities & Autocomplete
 */

const StockUtils = {
    /**
     * Format number with commas
     * @param {number|string} num 
     * @returns {string}
     */
    formatNumber: function (num) {
        if (num === null || num === undefined || num === '-') return '-';
        return Number(num).toLocaleString();
    },

    /**
     * Trigger flash animation for price changes
     * @param {HTMLElement} el 
     * @param {string} type 'up' or 'down'
     */
    triggerFlash: function (el, type) {
        const flashClass = type === 'up' ? 'changed-up' : 'changed-down';

        // Prevent layout thrashing if already animating
        if (el.classList.contains('changed-up') || el.classList.contains('changed-down')) {
            return;
        }

        el.classList.add(flashClass);
        el.addEventListener('animationend', () => {
            el.classList.remove(flashClass);
        }, { once: true });
    }
};

/**
 * Shared Stock Autocomplete Logic
 */
class StockAutocomplete {
    constructor(options) {
        this.stockList = [];
        this.$input = document.getElementById(options.inputId);
        // Optional: hidden input for short code
        this.$shortCodeInput = options.shortCodeInputId ? document.getElementById(options.shortCodeInputId) : null;

        // Callback when an item is selected (clicked or Enter)
        // onSelect({ name, short_code })
        this.onSelect = options.onSelect || function () { };

        this._activeIndex = -1;

        this.init();
    }

    init() {
        if (!this.$input) {
            console.error("StockAutocomplete: Input element not found.");
            return;
        }

        this.fetchStockList();
        this.bindEvents();
    }

    fetchStockList() {
        fetch('/static/stock_price/stock_list.json')
            .then(r => r.json())
            .then(json => {
                this.stockList = json.results || [];
            })
            .catch(err => console.error('Failed to load stock list in Autocomplete', err));
    }

    bindEvents() {
        // Input event
        this.$input.addEventListener('input', (e) => {
            const q = e.target.value.trim();
            this.showAutocomplete(q);
            this._activeIndex = -1;
            if (this.$shortCodeInput) this.$shortCodeInput.value = '';
        });

        // Global click to close
        document.addEventListener('click', (e) => {
            const list = document.getElementById('autocomplete-list');
            if (list && e.target !== this.$input && !list.contains(e.target)) {
                this.hideAutocomplete();
            }
        });

        // Keyboard navigation
        this.$input.addEventListener('keydown', (e) => {
            const list = document.getElementById('autocomplete-list');
            if (!list || list.style.display === 'none') {
                return;
            }

            const items = Array.from(list.querySelectorAll('.autocomplete-item'));
            if (!items.length) return;

            if (e.key === 'ArrowDown') {
                e.preventDefault();
                this._activeIndex++;
                if (this._activeIndex >= items.length) this._activeIndex = 0;
                this.setActiveAutocomplete(items, this._activeIndex);
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                this._activeIndex--;
                if (this._activeIndex < 0) this._activeIndex = items.length - 1;
                this.setActiveAutocomplete(items, this._activeIndex);
            } else if (e.key === 'Enter') {
                e.preventDefault(); // Prevent form submission
                if (this._activeIndex >= 0 && this._activeIndex < items.length) {
                    const it = items[this._activeIndex];
                    this.selectItem(it.dataset.name, it.dataset.shortCode);
                }
            }
        });
    }

    showAutocomplete(q) {
        this.hideAutocomplete();
        if (!q || !this.stockList.length) return;

        const qUpper = q.toUpperCase();
        const matched = this.stockList.filter(
            s => (s.name && s.name.toUpperCase().includes(qUpper)) ||
                (s.short_code && s.short_code.toUpperCase().includes(qUpper))
        );

        if (!matched.length) return;

        let list = document.getElementById('autocomplete-list');
        if (!list) {
            list = document.createElement('div');
            list.id = 'autocomplete-list';
            list.className = 'autocomplete-list';
            this.$input.parentNode.appendChild(list);
        }

        list.innerHTML = '';
        // Limit to 20 items
        matched.slice(0, 20).forEach((item) => {
            const div = document.createElement('div');
            div.className = 'autocomplete-item';
            div.dataset.name = item.name;
            div.dataset.shortCode = item.short_code;
            div.textContent = `${item.name} (${item.short_code})`;

            // Mouse click
            div.addEventListener('click', (e) => {
                e.stopPropagation();
                this.selectItem(item.name, item.short_code);
            });

            list.appendChild(div);
        });

        list.style.display = 'block';
    }

    hideAutocomplete() {
        const list = document.getElementById('autocomplete-list');
        if (list) list.style.display = 'none';
        this._activeIndex = -1;
    }

    setActiveAutocomplete(items, idx) {
        items.forEach((el, i) => el.classList.toggle('active', i === idx));
        const active = items[idx];
        if (active) {
            active.scrollIntoView({ block: 'nearest' });
        }
    }

    selectItem(name, code) {
        this.$input.value = name;
        if (this.$shortCodeInput) {
            this.$shortCodeInput.value = code;
        }
        this.hideAutocomplete();

        this.onSelect({ name, short_code: code });
    }
}
