const StockApp = {
    stockList: [], // 자동완성용 종목 리스트
    version: "1.1", // For cache verification
    socket: null,
    stockCode: null,


    init: function () {
        console.log(`StockApp Initialized (Version ${this.version})`);
        this.cacheDOM();
        this.bindEvents();
        // 종목 리스트 json 불러오기
        fetch('/static/api/stock_list.json')
            .then(r => r.json())
            .then(json => {
                this.stockList = json.results || [];
                this.setupAutocomplete();
                // input의 기본값이 있을 때 자동으로 코드 세팅
                if (this.$input && this.$selectedShortCode && this.$input.value) {
                    const match = this.stockList.find(
                        s => s.name === this.$input.value || s.short_code === this.$input.value
                    );
                    if (match) this.$selectedShortCode.value = match.short_code;
                }
                this.connectWS(); // 종목코드 세팅 후에만 연결
            })
            .catch(err => {
                console.error('자동완성 종목 리스트 로드 실패', err);
                this.setupAutocomplete();
                this.connectWS(); // 실패 시에도 연결 시도
            });
    },

    setupAutocomplete: function () {
        if (!this.$input) return;
        this.$input.addEventListener('input', (e) => {
            const q = e.target.value.trim();
            this.showAutocomplete(q);
            this._activeIndex = -1;
            if (this.$selectedShortCode) this.$selectedShortCode.value = '';
        });
        // 자동완성 목록 클릭 시 입력창에 반영
        document.body.addEventListener('mousedown', (e) => {
            if (e.target.classList.contains('autocomplete-item')) {
                this.$input.value = e.target.dataset.name;
                this.hideAutocomplete();
            } else {
                this.hideAutocomplete();
            }
        });
        // 키보드 네비게이션
        this.$input.addEventListener('keydown', (e) => {
            const list = document.getElementById('autocomplete-list');
            if (!list || list.style.display === 'none') return;
            const items = Array.from(list.querySelectorAll('.autocomplete-item'));
            if (!items.length) return;
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                this._activeIndex = (typeof this._activeIndex === 'number') ? this._activeIndex + 1 : 0;
                if (this._activeIndex >= items.length) this._activeIndex = 0;
                this.setActiveAutocomplete(items, this._activeIndex);
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                this._activeIndex = (typeof this._activeIndex === 'number') ? this._activeIndex - 1 : items.length - 1;
                if (this._activeIndex < 0) this._activeIndex = items.length - 1;
                this.setActiveAutocomplete(items, this._activeIndex);
            } else if (e.key === 'Enter') {
                if (typeof this._activeIndex === 'number' && this._activeIndex >= 0) {
                    e.preventDefault();
                    const it = items[this._activeIndex];
                    if (it) {
                        this.$input.value = it.dataset.name;
                        if (this.$selectedShortCode) this.$selectedShortCode.value = it.dataset.shortCode;
                        this.hideAutocomplete();
                        this.connectWS();
                    }
                }
            }
        });
    },
    setActiveAutocomplete: function(items, idx) {
        items.forEach((el, i) => el.classList.toggle('active', i === idx));
        const active = items[idx];
        if (active) active.scrollIntoView({block: 'nearest'});
    },

    showAutocomplete: function (q) {
        this.hideAutocomplete();
        if (!q || !this.stockList.length) return;
        const matched = this.stockList.filter(
            s => s.name.includes(q) || s.short_code.includes(q)
        ).slice(0, 10);
        if (!matched.length) return;
        let list = document.getElementById('autocomplete-list');
        if (!list) {
            list = document.createElement('div');
            list.id = 'autocomplete-list';
            list.className = 'autocomplete-list';
            this.$input.parentNode.appendChild(list);
        }
        list.innerHTML = '';
        matched.forEach(item => {
            const div = document.createElement('div');
            div.className = 'autocomplete-item';
            div.dataset.name = item.name;
            div.dataset.shortCode = item.short_code;
            div.textContent = `${item.name} (${item.short_code})`;
            list.appendChild(div);
        });
        list.style.display = 'block';
    },

    hideAutocomplete: function () {
        const list = document.getElementById('autocomplete-list');
        if (list) list.style.display = 'none';
    },

    cacheDOM: function () {
        this.$input = document.getElementById('stock-code-input');
        this.$selectedShortCode = document.getElementById('selected-short-code');
        this.$connectBtn = document.getElementById('connect-btn');
        this.$disconnectBtn = document.getElementById('disconnect-btn');
        this.$status = document.getElementById('status');
        this.$askTable = document.getElementById('ask-table-body');
        this.$bidTable = document.getElementById('bid-table-body');
        this.$currentPrice = document.getElementById('current-price');
        this.$currentPriceDiff = document.getElementById('current-price-diff');
    },

    bindEvents: function () {
        this.$connectBtn.addEventListener('click', () => this.connectWS());
        this.$disconnectBtn.addEventListener('click', () => this.disconnectWS());

        // 엔터키 입력 시 연결
        this.$input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.connectWS();
            }
        });
    },

    disconnectWS: function () {
        if (this.socket) {
            console.log("Disconnecting current socket...");
            this.socket.close();
            this.socket = null;
            this.updateStatus('연결 종료됨');
        }
    },

    connectWS: function () {
        // prefer selected short code (from autocomplete). If absent, use raw input.
        const code = (this.$selectedShortCode && this.$selectedShortCode.value) ? this.$selectedShortCode.value : this.$input.value.trim();
        if (!code) {
            alert('종목코드를 입력해주세요.');
            return;
        }

        console.log(`Attempting to connect to stock: ${code}`);

        // UI 초기화 및 호가 테이블 구조 미리 생성
        this.initHogaTables();
        this.$currentPrice.textContent = '-';
        this.$currentPriceDiff.textContent = '-';
        this.$currentPrice.className = 'current-price-value';
        this.$currentPriceDiff.className = 'diff';

        this.stockCode = code;
        this.disconnectWS();

        this.updateStatus('연결 시도 중...');
        this.socket = new WebSocket('ws://' + window.location.host + '/ws/stock/' + code + '/');

        this.socket.onopen = () => this.updateStatus(`연결됨 (${code})`);
        this.socket.onmessage = (event) => this.handleMessage(event);
        this.socket.onclose = () => this.updateStatus('연결 끊김');
        this.socket.onerror = (error) => {
            console.error('WebSocket Error:', error);
            this.updateStatus('에러 발생');
        };
    },

    initHogaTables: function () {
        // 매도 호가 테이블 초기화 (10행)
        let askHtml = '';
        for (let i = 10; i >= 1; i--) {
            askHtml += `
                <tr class="ask-row" data-index="${i}">
                    <td class="volume">-</td>
                    <td class="price">-</td>
                    <td class="rate"></td>
                </tr>
            `;
        }
        this.$askTable.innerHTML = askHtml;

        // 매수 호가 테이블 초기화 (10행)
        let bidHtml = '';
        for (let i = 1; i <= 10; i++) {
            bidHtml += `
                <tr class="bid-row" data-index="${i}">
                    <td class="rate"></td>
                    <td class="price">-</td>
                    <td class="volume">-</td>
                </tr>
            `;
        }
        this.$bidTable.innerHTML = bidHtml;
    },

    updateStatus: function (msg) {
        this.$status.textContent = msg;
    },

    handleMessage: function (event) {
        try {
            const data = JSON.parse(event.data);

            // 1. 호가 데이터
            if (data.ASKP1 !== undefined && data.BIDP1 !== undefined) {
                this.renderHoga(data);
            }

            // 2. 체결 데이터
            if (data.STCK_PRPR !== undefined && data.STCK_CNTG_HOUR) {
                this.renderExecution(data);
            }
        } catch (e) {
            console.error("Parse Error", e);
        }
    },

    renderExecution: function (data) {
        const price = data.STCK_PRPR;
        const diff = data.PRDY_VRSS;
        const rate = data.PRDY_CTRT;

        this.updateCurrentPrice(price, diff, rate);

        // 체결 목록 추가 (최근 15개 유지)
        const $tradeList = document.getElementById('trade-list');
        if ($tradeList) {
            const row = document.createElement('tr');
            let timeStr = data.STCK_CNTG_HOUR || '000000';
            if (timeStr.length >= 6) {
                timeStr = `${timeStr.substring(0, 2)}:${timeStr.substring(2, 4)}:${timeStr.substring(4, 6)}`;
            }

            row.innerHTML = `
                <td>${timeStr}</td>
                <td class="${diff > 0 ? 'up' : (diff < 0 ? 'down' : '')}">${this.formatNumber(price)}</td>
                <td>${this.formatNumber(data.CNTG_VOL)}</td>
            `;
            $tradeList.prepend(row);
            if ($tradeList.children.length > 15) {
                $tradeList.lastElementChild.remove();
            }
        }
    },

    updateCurrentPrice: function (price, diff, rate, sign) {
        const formattedPrice = this.formatNumber(price);
        if (this.$currentPrice.textContent !== formattedPrice) {
            // 가격이 변했을 때만 업데이트 및 효과
            const prevPrice = parseInt(this.$currentPrice.textContent.replace(/,/g, '')) || 0;
            this.$currentPrice.textContent = formattedPrice;

            if (price > prevPrice) this.triggerFlash(this.$currentPrice, 'up');
            else if (price < prevPrice) this.triggerFlash(this.$currentPrice, 'down');
        }

        let diffSign = '';
        if (sign) {
            if (sign === '1' || sign === '2') diffSign = '▲';
            else if (sign === '4' || sign === '5') diffSign = '▼';
        } else {
            diffSign = diff > 0 ? '+' : '';
        }

        const diffText = `${diffSign}${this.formatNumber(Math.abs(diff))} (${rate}%)`;
        if (this.$currentPriceDiff.textContent !== diffText) {
            this.$currentPriceDiff.textContent = diffText;
        }

        // 색상 처리
        let colorClass = '';
        if (sign) {
            if (sign === '1' || sign === '2') colorClass = 'up';
            else if (sign === '4' || sign === '5') colorClass = 'down';
        } else {
            if (diff > 0) colorClass = 'up';
            else if (diff < 0) colorClass = 'down';
        }

        this.$currentPrice.className = `current-price-value ${colorClass}`;
        this.$currentPriceDiff.className = `diff ${colorClass}`;
    },

    triggerFlash: function (el, type) {
        const now = Date.now();
        // 100ms 이내의 연속된 깜빡임은 무시하여 피로도 감소
        if (el._lastFlash && now - el._lastFlash < 100) return;

        const flashClass = type === 'up' ? 'changed-up' : 'changed-down';
        el.classList.remove('changed-up', 'changed-down');
        void el.offsetWidth; // trigger reflow
        el.classList.add(flashClass);
        el._lastFlash = now;
    },

    formatNumber: function (num) {
        if (num === null || num === undefined || num === '-') return '-';
        return Number(num).toLocaleString();
    },

    renderHoga: function (data) {
        // 매도 호가 업데이트
        for (let i = 1; i <= 10; i++) {
            this.updateHogaRow(this.$askTable, i, data[`ASKP${i}`], data[`ASKP_RSQN${i}`], 'ask');
        }

        // 매수 호가 업데이트
        for (let i = 1; i <= 10; i++) {
            this.updateHogaRow(this.$bidTable, i, data[`BIDP${i}`], data[`BIDP_RSQN${i}`], 'bid');
        }

        // 현재가/예상체결가 정보 업데이트
        const currentPrice = data.ANTC_CNPR || data.BIDP1 || data.ASKP1;
        const diff = data.ANTC_CNTG_VRSS || 0;
        const sign = data.ANTC_CNTG_VRSS_SIGN || '3';
        const prevPrice = currentPrice - diff;
        const rate = prevPrice > 0 ? ((diff / prevPrice) * 100).toFixed(2) : '0.00';

        if (currentPrice) {
            this.updateCurrentPrice(currentPrice, diff, rate, sign);
        }
    },

    updateHogaRow: function ($container, index, price, volume, type) {
        const row = $container.querySelector(`tr[data-index="${index}"]`);
        if (!row) return;

        const priceEl = row.querySelector('.price');
        const volumeEl = row.querySelector('.volume');

        const formattedPrice = this.formatNumber(price);
        const formattedVolume = this.formatNumber(volume);

        if (priceEl.textContent !== formattedPrice) {
            const prevPrice = parseInt(priceEl.textContent.replace(/,/g, '')) || 0;
            priceEl.textContent = formattedPrice;
            if (prevPrice !== 0) {
                this.triggerFlash(priceEl, price > prevPrice ? 'up' : 'down');
            }
        }

        if (volumeEl.textContent !== formattedVolume) {
            const prevVol = parseInt(volumeEl.textContent.replace(/,/g, '')) || 0;
            volumeEl.textContent = formattedVolume;
            if (prevVol !== 0) {
                this.triggerFlash(volumeEl, volume > prevVol ? 'up' : 'down');
            }
        }
    }
};

document.addEventListener('DOMContentLoaded', () => {
    StockApp.init();
});
