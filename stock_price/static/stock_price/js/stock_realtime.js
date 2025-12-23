const StockApp = {
    stockList: [], // 자동완성용 종목 리스트
    version: "1.1", // For cache verification
    socket: null,
    stockCode: null,


    init: function () {
        console.log(`StockApp Initialized (Version ${this.version})`);
        this.cacheDOM();
        this.bindEvents();

        // Initialize Autocomplete
        this.autocomplete = new StockAutocomplete({
            inputId: 'stock-code-input',
            shortCodeInputId: 'selected-short-code',
            onSelect: (item) => {
                // When item selected, connect immediately
                this.connectWS();
            }
        });

        // Pre-fill if input has value (reload case)
        // Note: StockAutocomplete fetches list asynchronously, so we might need to wait or just let it happen.
        // The original code tried to set selectedShortCode if input had value.
        // We can leave that to the user re-selecting or just let the manual connect work.
        // But for "Automatic code setting" if string matches:
        // We can add a method to StockAutocomplete to "resolve" current input?
        // Or just keep simple logic here once list is loaded?
        // Actually, StockAutocomplete manages the list internally now.
        // If we want to support "reload page -> input has 'Samsung' -> auto set code",
        // we might rely on the user pressing connect or selecting again.
        // Or we can ask StockAutocomplete to check?
        // For now, let's trust the user or the hidden input if it was preserved (it usually isn't across refresh unless autocomplete=on?).

        // If the browser restored the visible input value, we might want to ensure short-code is set.
        // The original code did this after fetching list. 
        // We can leave it for now or rely on manual interaction.
    },

    // Old autocomplete methods removed
    // setupAutocomplete, showAutocomplete, hideAutocomplete, doc click, keydown... removed.


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

            // 1. 호가 데이터 (10호가가 모두 있어야 진짜 호가 데이터임)
            // 체결 데이터에도 ASKP1, BIDP1은 포함되어 있어서 오동작함 -> ASKP10, BIDP10 체크로 구분
            if (data.ASKP10 !== undefined && data.BIDP10 !== undefined) {
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
                <td class="${diff > 0 ? 'up' : (diff < 0 ? 'down' : '')}">${StockUtils.formatNumber(price)}</td>
                <td>${StockUtils.formatNumber(data.CNTG_VOL)}</td>
            `;
            $tradeList.prepend(row);
            if ($tradeList.children.length > 15) {
                $tradeList.lastElementChild.remove();
            }
        }
    },

    updateCurrentPrice: function (price, diff, rate, sign) {
        const formattedPrice = StockUtils.formatNumber(price);
        if (this.$currentPrice.textContent !== formattedPrice) {
            // 가격이 변했을 때만 업데이트 및 효과
            const prevPrice = parseInt(this.$currentPrice.textContent.replace(/,/g, '')) || 0;
            this.$currentPrice.textContent = formattedPrice;

            if (price > prevPrice) StockUtils.triggerFlash(this.$currentPrice, 'up');
            else if (price < prevPrice) StockUtils.triggerFlash(this.$currentPrice, 'down');
        }

        let diffSign = '';
        if (sign) {
            if (sign === '1' || sign === '2') diffSign = '▲';
            else if (sign === '4' || sign === '5') diffSign = '▼';
        } else {
            diffSign = diff > 0 ? '+' : '';
        }

        const diffText = `${diffSign}${StockUtils.formatNumber(Math.abs(diff))} (${rate}%)`;
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

    // triggerFlash removed (using StockUtils)

    // formatNumber removed (using StockUtils)

    renderHoga: function (data) {
        // 매도 호가 업데이트
        for (let i = 1; i <= 10; i++) {
            this.updateHogaRow(this.$askTable, i, data[`ASKP${i}`], data[`ASKP_RSQN${i}`], 'ask');
        }

        // 매수 호가 업데이트
        for (let i = 1; i <= 10; i++) {
            this.updateHogaRow(this.$bidTable, i, data[`BIDP${i}`], data[`BIDP_RSQN${i}`], 'bid');
        }
    },

    updateHogaRow: function ($container, index, price, volume, type) {
        const row = $container.querySelector(`tr[data-index="${index}"]`);
        if (!row) return;

        const priceEl = row.querySelector('.price');
        const volumeEl = row.querySelector('.volume');

        const formattedPrice = StockUtils.formatNumber(price);
        const formattedVolume = StockUtils.formatNumber(volume);

        if (priceEl.textContent !== formattedPrice) {
            const prevPrice = parseInt(priceEl.textContent.replace(/,/g, '')) || 0;
            priceEl.textContent = formattedPrice;
            if (prevPrice !== 0) {
                StockUtils.triggerFlash(priceEl, price > prevPrice ? 'up' : 'down');
            }
        }

        if (volumeEl.textContent !== formattedVolume) {
            const prevVol = parseInt(volumeEl.textContent.replace(/,/g, '')) || 0;
            volumeEl.textContent = formattedVolume;
            if (prevVol !== 0) {
                StockUtils.triggerFlash(volumeEl, volume > prevVol ? 'up' : 'down');
            }
        }
    }
};

document.addEventListener('DOMContentLoaded', () => {
    StockApp.init();
});
