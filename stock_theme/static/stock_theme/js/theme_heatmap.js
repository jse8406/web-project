document.addEventListener('DOMContentLoaded', () => {
    console.log("Real-time Heatmap JS Initialized (External File) 🚀");

    // Init Data
    const targetStockCodesElement = document.getElementById('target-stocks-data');
    const top30ListElement = document.getElementById('top-30-list-data');
    const initialPriceElement = document.getElementById('initial-price-data');

    let targetStockCodes = [];
    let top30List = [];
    let initialPriceData = {};

    try {
        if (targetStockCodesElement) targetStockCodes = JSON.parse(targetStockCodesElement.textContent);
        if (top30ListElement) top30List = JSON.parse(top30ListElement.textContent);
        if (initialPriceElement) initialPriceData = JSON.parse(initialPriceElement.textContent);
    } catch (e) {
        console.error("Failed to parse initial data", e);
    }

    console.log("Target Stocks:", targetStockCodes);
    console.log("Initial Price Data Keys:", Object.keys(initialPriceData).length);

    // [UI] Initial Render: Left Panel Mini Heatmap
    const leftPanelContainer = document.getElementById('top-30-container');
    if (leftPanelContainer) {
        leftPanelContainer.innerHTML = '';

        // Use Top 30 List from Server if available (Preferred)
        if (top30List && top30List.length > 0) {
            top30List.forEach(item => {
                const code = item.code;
                const name = item.name;
                const rate = item.rate;
                const price = item.price; // Optional display

                const block = document.createElement('div');
                block.className = 'mini-block';
                block.id = `mini-block-${code}`;
                block.innerHTML = `
                    <div class="code" id="mini-name-${code}">${name}</div>
                    <div class="rate" id="mini-rate-${code}">${rate}%</div>
                `;
                // Apply color class immediately
                updateBlockStyle(block, parseFloat(rate), 0);
                leftPanelContainer.appendChild(block);
            });
        }
        // Fallback: Use targetStockCodes (Legacy/Backup)
        else if (targetStockCodes.length > 0) {
            targetStockCodes.forEach(code => {
                let name = code;
                const centerBlock = document.querySelector(`.stock-block[data-code="${code}"]`);
                if (centerBlock) name = centerBlock.dataset.name;

                // Try to find price data in initialPriceData
                let displayRate = "0.00";
                let numericRate = 0.0;

                if (initialPriceData && initialPriceData[code]) {
                    const data = initialPriceData[code];
                    numericRate = parseFloat(data.rate || data.prdy_ctrt || 0);
                    displayRate = `${numericRate > 0 ? '+' : ''}${numericRate.toFixed(2)}`;
                }

                const block = document.createElement('div');
                block.className = 'mini-block';
                block.id = `mini-block-${code}`;
                block.innerHTML = `
                    <div class="code" id="mini-name-${code}">${name}</div>
                    <div class="rate" id="mini-rate-${code}">${displayRate}%</div>
                `;

                // Remove existing color classes first if any (though new element)
                updateBlockStyle(block, numericRate, 0);

                leftPanelContainer.appendChild(block);
            });
        }
    }

    // [UI] Initial Render: Main Heatmap Prices
    if (initialPriceData) {
        Object.keys(initialPriceData).forEach(code => {
            const data = initialPriceData[code];
            const rate = parseFloat(data.rate || data.prdy_ctrt || 0); // Handle different key naming if any
            const volume = parseInt(data.volume || 0);

            // Update Main Heatmap Block
            document.querySelectorAll(`#rate-${code}`).forEach(el => {
                el.textContent = `${rate > 0 ? '+' : ''}${rate}%`;
                const block = el.closest('.stock-block');
                if (block) updateBlockStyle(block, rate, volume);
            });
        });
    }

    // [WebSocket]
    // 1. Check Market Status
    const isMarketOpenElement = document.getElementById('is-market-open');
    let isMarketOpen = true; // Default to open if missing
    if (isMarketOpenElement) {
        try {
            isMarketOpen = JSON.parse(isMarketOpenElement.textContent);
        } catch (e) { console.error("Failed to parse market status", e); }
    }

    if (isMarketOpen) {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/stock/`;
        const socket = new WebSocket(wsUrl);

        socket.onopen = function (e) {
            console.log("[WS] Connected");
            if (targetStockCodes.length > 0) {
                targetStockCodes.forEach(code => {
                    socket.send(JSON.stringify({ 'type': 'subscribe', 'code': code }));
                });
            }
        };

        socket.onmessage = function (e) {
            const data = JSON.parse(e.data);
            if (data.type === 'stock_update') {
                updateStockBlock(data.data);
            } else if (data.type === 'theme_update') {
                console.log("[WS] Theme Update Received! Reloading...", data);
                // Simple sync strategy: Reload page to fetch new structure
                // Use a short delay or toast in future
                window.location.reload();
            }
        };
    } else {
        console.log("[WS] Market is Closed. WebSocket connection skipped.");
    }

    function updateStockBlock(data) {
        const code = data.stock_code;
        const priceData = data.output;
        if (!priceData) return;

        const rate = parseFloat(priceData.prdy_ctrt);
        const volume = parseInt(priceData.acml_vol);

        document.querySelectorAll(`#rate-${code}`).forEach(el => {
            el.textContent = `${rate > 0 ? '+' : ''}${rate}%`;
            const block = el.closest('.stock-block');
            if (block) updateBlockStyle(block, rate, volume);
        });

        const miniRate = document.getElementById(`mini-rate-${code}`);
        if (miniRate) {
            miniRate.textContent = `${rate > 0 ? '+' : ''}${rate}%`;
            const miniBlock = document.getElementById(`mini-block-${code}`);
            if (miniBlock) updateBlockStyle(miniBlock, rate, volume);
        }
    }

    function updateBlockStyle(element, rate, volume) {
        element.classList.remove('bg-up-1', 'bg-up-2', 'bg-up-3', 'bg-up-4', 'bg-down-1', 'bg-down-2');
        if (rate >= 15) element.classList.add('bg-up-4');
        else if (rate >= 10) element.classList.add('bg-up-3');
        else if (rate >= 5) element.classList.add('bg-up-2');
        else if (rate > 0) element.classList.add('bg-up-1');
        else if (rate > -3) element.classList.add('bg-down-1');
        else element.classList.add('bg-down-2');

        const weight = Math.max(1, Math.min(Math.abs(rate) * 3, 20));
        element.style.flexGrow = weight;
    }

    // [INTERACTION] - VISUAL FEEDBACK
    // Using delegation to ensure it works even if elements change or load late
    document.body.addEventListener('click', function (e) {
        // 1. Theme Header Click
        const themeHeader = e.target.closest('.theme-header');
        if (themeHeader) {
            e.preventDefault();
            console.log("Theme Header Clicked");

            document.querySelectorAll('.theme-card').forEach(c => c.style.borderColor = '#1e1e1e'); // Default border color (from css var usually, hardcoding for safety)
            const card = themeHeader.closest('.theme-card');
            card.style.borderColor = '#00e676'; // Accent color

            const themeName = card.querySelector('.theme-title').textContent.trim();
            const stocks = card.querySelectorAll('.stock-block');

            let analysisHtml = `<h3 class="detail-title"> ${themeName}</h3><div class="detail-body">`;
            if (stocks.length > 0) {
                analysisHtml += `<ul class="guide-list">`;
                stocks.forEach(stock => {
                    const name = stock.dataset.name;
                    const reason = stock.dataset.reason || "상세 분석 내용이 없습니다.";
                    analysisHtml += `<li class="guide-item"><strong class="guide-name">${name}</strong> <br> ${reason}</li>`;
                });
                analysisHtml += `</ul>`;
            } else {
                analysisHtml += `<p class="detail-text">포함된 종목이 없습니다.</p>`;
            }
            analysisHtml += `</div>`;
            document.getElementById('analysis-detail').innerHTML = analysisHtml;
            return;
        }

        // 2. Stock Block Click
        const stockBlock = e.target.closest('.stock-block');
        if (stockBlock) {
            e.stopPropagation();
            console.log("Stock Block Clicked");

            document.querySelectorAll('.theme-card').forEach(c => c.style.borderColor = '#1e1e1e');
            stockBlock.closest('.theme-card').style.borderColor = '#00e676';

            const name = stockBlock.dataset.name;
            const code = stockBlock.dataset.code;
            const reason = stockBlock.dataset.reason || "AI 분석 중입니다...";
            const currentRate = stockBlock.querySelector('.stock-rate').textContent;

            const detailHtml = `
                <h3 class="detail-title">⚡ ${name} (${code})</h3>
                <span class="detail-rate ${currentRate.includes('-') ? 'rate-down' : 'rate-up'}">${currentRate}</span>
                
                <div class="detail-body">
                    <h4 class="detail-subtitle">📈 상승 배경 (AI 분석)</h4>
                    <p class="detail-text">${reason}</p>
                    
                    <a href="/stock_price/stock/detail/${code}/" class="detail-btn">
                        👉 차트/호가 자세히 보기
                    </a>
                </div>
            `;
            document.getElementById('analysis-detail').innerHTML = detailHtml;
        }
    });

});
