/**
 * 股票分析工具 v2.0 - 前端交互逻辑
 * 功能：市场温度计、股票查询、结果渲染、弹窗管理
 */

(function() {
    'use strict';

    // 自动切换API环境（本地开发 vs 阿里云生产）
    const API_BASE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
        ? ''  // 本地开发环境 - 使用相对路径，同端口
        : 'https://stock-qamkwqdxbb.cn-hangzhou-vpc.fcapp.run';  // 阿里云生产环境

    console.log('API环境:', API_BASE);

    let recentQueries = [];
    const MAX_RECENT = 10;

    document.addEventListener('DOMContentLoaded', function() {
        initApp();
        loadRecentQueries();
        refreshMarket();
        setupInputHandler();
        initRecommendedStocks();
    });

    function initApp() {
        console.log('📊 股票分析工具 v2.0 初始化完成');
    }

    function setupInputHandler() {
        const input = document.getElementById('stockCodeInput');
        if (!input) return;

        input.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                queryStock();
            }
        });

        input.addEventListener('input', function(e) {
            this.value = this.value.replace(/[^0-9]/g, '').slice(0, 6);
        });
    }

    async function refreshMarket() {
        try {
            showMarketLoading();
            
            // 优先使用本地API
            const response = await fetch(`/api/market/thermometer`, {
                method: 'GET',
                headers: { 'Accept': 'application/json' }
            });

            if (!response.ok) throw new Error('网络请求失败');
            
            const data = await response.json();
            
            if (data.success) {
                renderMarketData(data);
            } else {
                showMarketFallback();
            }
        } catch (error) {
            console.warn('市场数据加载失败:', error);
            showMarketFallback();
        }
    }

    function showMarketLoading() {
        const loading = document.getElementById('marketLoading');
        const display = document.getElementById('tempDisplay');
        const barContainer = document.getElementById('tempBarContainer');
        const metrics = document.getElementById('marketMetrics');

        if (loading) loading.classList.remove('hidden');
        if (display) display.classList.add('hidden');
        if (barContainer) barContainer.classList.add('hidden');
        if (metrics) metrics.classList.add('hidden');
    }

    function showMarketFallback() {
        const loading = document.getElementById('marketLoading');
        const display = document.getElementById('tempDisplay');
        const barContainer = document.getElementById('tempBarContainer');

        if (loading) loading.classList.add('hidden');
        
        if (display) {
            display.classList.remove('hidden');
            document.getElementById('marketIcon').textContent = '🟡';
            document.getElementById('marketLabel').textContent = '震荡市';
            document.getElementById('marketScore').textContent = '65分';
        }

        if (barContainer) {
            barContainer.classList.remove('hidden');
        }

        const metrics = document.getElementById('marketMetrics');
        if (metrics) {
            metrics.classList.remove('hidden');
            document.getElementById('shIndex').textContent = '--';
            document.getElementById('szIndex').textContent = '--';
            document.getElementById('cybIndex').textContent = '--';
            document.getElementById('advanceDecline').textContent = '--';
        }
    }

    function renderMarketData(data) {
        const loading = document.getElementById('marketLoading');
        const display = document.getElementById('tempDisplay');
        const barContainer = document.getElementById('tempBarContainer');
        const metrics = document.getElementById('marketMetrics');

        if (loading) loading.classList.add('hidden');

        const score = data.score || 65;
        const label = data.label || '震荡格局';
        const icon = data.icon || getMarketIcon(score);

        if (display) {
            display.classList.remove('hidden');
            document.getElementById('marketIcon').textContent = icon;
            document.getElementById('marketLabel').textContent = label;
            document.getElementById('marketScore').textContent = score + '分';
        }

        if (barContainer) {
            barContainer.classList.remove('hidden');
            const bar = document.getElementById('tempBar');
            const indicator = document.getElementById('tempIndicator');
            if (bar) bar.style.width = score + '%';
            if (indicator) indicator.style.left = score + '%';
        }

        if (metrics) {
            metrics.classList.remove('hidden');
            // 显示指数数据
            const indexData = data.index_data || {};
            document.getElementById('shIndex').textContent = indexData['sh000001']?.price || '--';
            document.getElementById('szIndex').textContent = indexData['sz399001']?.price || '--';
            document.getElementById('cybIndex').textContent = indexData['sz399006']?.price || '--';
            document.getElementById('advanceDecline').textContent = '--';
        }
    }

    function getMarketIcon(score) {
        if (score < 35) return '🔴';
        if (score < 50) return '🟠';
        if (score < 70) return '🟡';
        if (score < 85) return '🟢';
        return '🟢';
    }

    window.refreshMarket = refreshMarket;

    async function queryStock() {
        const input = document.getElementById('stockCodeInput');
        const code = input ? input.value.trim() : '';

        if (!code || code.length !== 6) {
            showToast('请输入6位股票代码', 'warning');
            return;
        }

        const btn = document.getElementById('queryBtn');
        if (btn) {
            btn.disabled = true;
            btn.textContent = '查询中...';
        }

        try {
            showResultLoading();

            // 使用本地API
            const response = await fetch(`/api/indicators/${code}`, {
                method: 'GET',
                headers: { 'Accept': 'application/json' }
            });

            if (!response.ok) {
                if (response.status === 404) {
                    throw new Error('未找到该股票数据');
                }
                throw new Error('查询失败，请稍后重试');
            }

            const result = await response.json();

            if (result.success) {
                renderQueryResult(result);
                addToRecent(code, result.stock_name || result.name || code);
                hideEmptyState();
            } else {
                throw new Error(result.message || '数据处理失败');
            }

        } catch (error) {
            console.error('查询错误:', error);
            showErrorState(error.message);
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.textContent = '查询指标';
            }
        }
    }

    window.queryStock = queryStock;

    function showResultLoading() {
        const resultArea = document.getElementById('queryResult');
        const emptyState = document.getElementById('emptyState');

        if (resultArea) {
            resultArea.classList.remove('hidden');
            resultArea.innerHTML = `
                <div class="loading-state">
                    <div class="spinner"></div>
                    <p>正在计算技术指标...</p>
                </div>
            `;
        }

        if (emptyState) emptyState.classList.add('hidden');
    }

    function hideEmptyState() {
        const emptyState = document.getElementById('emptyState');
        if (emptyState) emptyState.classList.add('hidden');
    }

    function showErrorState(message) {
        const resultArea = document.getElementById('queryResult');
        const emptyState = document.getElementById('emptyState');

        if (resultArea) {
            resultArea.classList.remove('hidden');
            resultArea.innerHTML = `
                <div class="error-state">
                    <div class="error-icon">⚠️</div>
                    <p class="error-message">${escapeHtml(message)}</p>
                    <button onclick="queryStock()" class="btn-secondary">重新查询</button>
                </div>
            `;
        }

        if (emptyState) emptyState.classList.add('hidden');
    }

    function renderQueryResult(data) {
        const resultArea = document.getElementById('queryResult');
        if (!resultArea) return;

        const priceChangeClass = (data.change || 0) >= 0 ? 'price-up' : 'price-down';
        const changePrefix = (data.change || 0) >= 0 ? '+' : '';

        let indicatorsHtml = '';

        if (data.indicators && data.indicators.length > 0) {
            const trendIndicators = data.indicators.filter(i => i.category === 'trend');
            const oscillatorIndicators = data.indicators.filter(i => i.category === 'oscillator');
            const volumeIndicators = data.indicators.filter(i => i.category === 'volume');

            if (trendIndicators.length > 0) {
                indicatorsHtml += buildIndicatorSection('📈 趋势类指标', trendIndicators);
            }
            if (oscillatorIndicators.length > 0) {
                indicatorsHtml += buildIndicatorSection('📊 摆动类指标', oscillatorIndicators);
            }
            if (volumeIndicators.length > 0) {
                indicatorsHtml += buildIndicatorSection('💰 成交量类指标', volumeIndicators);
            }
        }

        const scoreHtml = data.comprehensive_score ? `
            <div class="comprehensive-score">
                <div class="score-number">${data.comprehensive_score}</div>
                <div class="score-label">${getScoreLabel(data.comprehensive_score)}</div>
                ${data.signals ? `
                    <div class="signal-summary">
                        ${data.signals.bullish_count > 0 ? `<p class="signal-bullish">✅ 看多信号 ${data.signals.bullish_count}个</p>` : ''}
                        ${data.signals.bearish_count > 0 ? `<p class="signal-bearish">⚠️ 谨慎信号 ${data.signals.bearish_count}个</p>` : ''}
                    </div>
                ` : ''}
            </div>
        ` : '';

        resultArea.innerHTML = `
            <div class="stock-result-header">
                <div class="stock-info">
                    <h3>${escapeHtml(data.stock_name || data.name || data.stock_code || '未知')}</h3>
                    <span class="stock-code">${data.stock_code || data.code || '未知'}</span>
                </div>
                <div class="stock-price">
                    <div class="price-current ${priceChangeClass}">${data.price || '--'}</div>
                    <div class="price-change ${priceChangeClass}">${changePrefix}${data.change || 0}%</div>
                </div>
            </div>

            ${indicatorsHtml}

            ${scoreHtml}

            <div style="margin-top:16px; text-align:center;">
                <button onclick="generateReport('${data.stock_code || data.code || ''}')" class="btn-secondary">📋 生成完整报告</button>
            </div>
        `;
    }

    function buildIndicatorSection(title, indicators) {
        const items = indicators.map(ind => {
            const statusClass = getStatusClass(ind.status);
            return `
                <div class="indicator-item">
                    <span class="indicator-name">${ind.name}</span>
                    <span class="indicator-value">${formatValue(ind.value)}</span>
                    <span class="indicator-status ${statusClass}">${ind.status_text || ''}</span>
                </div>
            `;
        }).join('');

        return `
            <div class="indicators-section">
                <h4>${title}</h4>
                <div class="indicator-grid">
                    ${items}
                </div>
            </div>
        `;
    }

    function formatValue(value) {
        if (value === null || value === undefined) return '--';
        if (typeof value === 'number') {
            if (Math.abs(value) >= 100) {
                return value.toFixed(1);
            } else if (Math.abs(value) >= 10) {
                return value.toFixed(2);
            } else {
                return value.toFixed(3);
            }
        }
        return String(value);
    }

    function getStatusClass(status) {
        switch(status) {
            case 'strong': return 'status-strong';
            case 'weak': return 'status-weak';
            default: return 'status-neutral';
        }
    }

    function getScoreLabel(score) {
        if (score >= 80) return '偏强';
        if (score >= 60) return '偏多';
        if (score >= 40) return '震荡';
        if (score >= 20) return '偏空';
        return '偏弱';
    }

    function addToRecent(code, name) {
        const existing = recentQueries.findIndex(q => q.code === code);
        if (existing !== -1) {
            recentQueries.splice(existing, 1);
        }

        recentQueries.unshift({
            code: code,
            name: name,
            time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
        });

        if (recentQueries.length > MAX_RECENT) {
            recentQueries.pop();
        }

        saveRecentQueries();
        renderRecentList();
    }

    function saveRecentQueries() {
        try {
            localStorage.setItem('stock_recent_queries', JSON.stringify(recentQueries));
        } catch (e) {}
    }

    function loadRecentQueries() {
        try {
            const saved = localStorage.getItem('stock_recent_queries');
            if (saved) {
                recentQueries = JSON.parse(saved);
                renderRecentList();
            }
        } catch (e) {}
    }

    function renderRecentList() {
        const container = document.getElementById('recentList');
        const section = document.getElementById('recentQueries');

        if (!container || !section) return;

        if (recentQueries.length === 0) {
            section.classList.add('hidden');
            return;
        }

        section.classList.remove('hidden');

        container.innerHTML = recentQueries.map(q => `
            <div class="recent-item" onclick="quickQuery('${q.code}')">
                <span>
                    <span class="recent-code">${q.code}</span>
                    ${q.name !== q.code ? `<small>${escapeHtml(q.name)}</small>` : ''}
                </span>
                <span class="recent-time">${q.time}</span>
            </div>
        `).join('');
    }

    window.clearRecentQueries = function() {
        recentQueries = [];
        saveRecentQueries();
        renderRecentList();
        showToast('最近查询已清除', 'success');
    };

    window.quickQuery = function(code) {
        const input = document.getElementById('stockCodeInput');
        if (input) {
            input.value = code;
            queryStock();
        }
    };

    function clearResult() {
        const input = document.getElementById('stockCodeInput');
        const resultArea = document.getElementById('queryResult');
        const emptyState = document.getElementById('emptyState');

        if (input) input.value = '';
        if (resultArea) {
            resultArea.classList.add('hidden');
            resultArea.innerHTML = '';
        }
        if (emptyState) emptyState.classList.remove('hidden');
    }

    window.clearResult = clearResult;

    function generateReport(codeParam) {
        const code = codeParam || (document.getElementById('stockCodeInput') ? 
                       document.getElementById('stockCodeInput').value.trim() : '');

        if (!code) {
            showToast('请先查询一只股票', 'warning');
            return;
        }

        // 跳转到报告页面
        window.location.href = `/report?code=${code}`;
    }

    window.generateReport = generateReport;

    function showReportModal(reportData) {
        const modalId = 'reportModal';
        let modal = document.getElementById(modalId);

        if (!modal) {
            modal = document.createElement('div');
            modal.className = 'modal-overlay';
            modal.id = modalId;
            modal.onclick = function(e) {
                if (e.target === modal) closeModal(modalId);
            };
            document.body.appendChild(modal);
        }

        const signalsHtml = reportData.signals ? reportData.signals.map(s => 
            `<li><strong>${s.indicator}</strong>: ${s.description}</li>`
        ).join('') : '';

        modal.innerHTML = `
            <div class="modal-content" onclick="event.stopPropagation()">
                <div class="modal-header">
                    <h3>📋 综合分析报告</h3>
                    <button onclick="closeModal('${modalId}')" class="modal-close">×</button>
                </div>
                <div class="modal-body" style="max-height:70vh;overflow-y:auto;">
                    <div class="report-header">
                        <h4>${reportData.stock_name || '股票'} (${reportData.code || code})</h4>
                        <p class="report-market-env">市场环境: ${reportData.market_env || '--'}</p>
                    </div>

                    <div class="report-score">
                        <strong>综合评分:</strong> 
                        <span class="score-number" style="font-size:36px;">${reportData.score || '--'}</span>/100
                        <span style="margin-left:8px;color:var(--text-secondary);">${getScoreLabel(reportData.score || 0)}</span>
                    </div>

                    ${signalsHtml ? `
                        <div class="report-signals">
                            <h4>主要信号</h4>
                            <ul>${signalsHtml}</ul>
                        </div>
                    ` : ''}

                    <div class="report-conclusion">
                        <h4>综合结论</h4>
                        <p>${reportData.conclusion || '暂无结论'}</p>
                    </div>

                    <div class="disclaimer-box" style="margin-top:16px;">
                        <strong>⚠️ 免责声明</strong>
                        <p>本报告基于技术指标的客观数值计算生成。</p>
                        <p><strong>所有内容仅供参考，不构成任何投资建议。</strong></p>
                    </div>
                </div>
                <div class="modal-footer">
                    <button onclick="closeModal('${modalId}')" class="btn-primary btn-block">关闭</button>
                </div>
            </div>
        `;

        modal.classList.remove('hidden');
    }

    window.showModal = function(id) {
        const modal = document.getElementById(id);
        if (modal) {
            modal.classList.remove('hidden');
            document.body.style.overflow = 'hidden';
        }
    };

    window.showUpgradeInfo = function() {
        showModal('upgradeModal');
    };

    window.showIndicatorList = function() {
        showModal('indicatorModal');
    };

    window.showSettings = function() {
        showToast('设置功能将在后续版本中推出', 'info');
    };

    window.closeModal = function(id) {
        const modal = document.getElementById(id);
        if (modal) {
            modal.classList.add('hidden');
            document.body.style.overflow = '';
        }
    };

    window.purchasePro = function() {
        showToast('正在跳转至App Store购买页面...', 'info');
        setTimeout(() => {
            alert('在真实App中，这里会调用Apple IAP进行购买。\n\n价格: ¥15.00\n购买后解锁全部高级功能！');
        }, 500);
    };

    function showToast(message, type) {
        type = type || 'info';

        const toast = document.createElement('div');
        toast.style.cssText = `
            position: fixed;
            top: 80px;
            left: 50%;
            transform: translateX(-50%);
            background: ${type === 'error' ? 'var(--danger-color)' : type === 'warning' ? 'var(--warning-color)' : 'var(--text-primary)'};
            color: white;
            padding: 12px 24px;
            border-radius: var(--radius-md);
            font-size: var(--font-size-sm);
            z-index: 300;
            box-shadow: var(--shadow-lg);
            animation: slideDown 0.3s ease;
            max-width: 90%;
            text-align: center;
        `;
        toast.textContent = message;
        document.body.appendChild(toast);

        setTimeout(() => {
            toast.style.animation = 'fadeOut 0.3s ease forwards';
            setTimeout(() => {
                if (toast.parentNode) toast.parentNode.removeChild(toast);
            }, 300);
        }, 2500);
    }

    const style = document.createElement('style');
    style.textContent = `
        @keyframes slideDown {
            from { opacity: 0; transform: translateX(-50%) translateY(-20px); }
            to { opacity: 1; transform: translateX(-50%) translateY(0); }
        }
        @keyframes fadeOut {
            from { opacity: 1; }
            to { opacity: 0; }
        }
        .error-state { text-align: center; padding: 40px 20px; }
        .error-icon { font-size: 48px; margin-bottom: 12px; }
        .error-message { color: var(--danger-color); margin-bottom: 16px; }
        .report-header h4 { font-size: var(--font-size-xl); margin-bottom: 4px; }
        .report-market-env { color: var(--text-secondary); font-size: var(--font-size-sm); margin-bottom: 16px; }
        .report-score { text-align: center; padding: 16px; background: var(--bg-input); border-radius: var(--radius-md); margin-bottom: 16px; }
        .report-signals h4, .report-conclusion h4 { margin-bottom: 8px; }
        .report-signals ul { padding-left: 20px; }
        .report-signals li { margin-bottom: 6px; font-size: var(--font-size-sm); }
        .report-conclusion p { line-height: 1.6; color: var(--text-secondary); }
    `;
    document.head.appendChild(style);

    function initRecommendedStocks() {
        console.log('初始化推荐股票...');
        
        // 从API动态获取推荐股票
        fetch('/api/market/recommended')
            .then(response => response.json())
            .then(data => {
                const container = document.getElementById('recommendedGrid');
                if (!container) {
                    console.error('未找到推荐股票容器');
                    return;
                }
                
                if (data.success && data.stocks && data.stocks.length > 0) {
                    const html = data.stocks.map(stock => {
                        const changeClass = stock.change_pct >= 0 ? 'positive' : 'negative';
                        const changeSign = stock.change_pct >= 0 ? '+' : '';
                        return `
                            <div class="recommended-item" onclick="quickQuery('${stock.code}')">
                                <span class="recommended-code">${stock.code}</span>
                                <span class="recommended-name">${escapeHtml(stock.name)}</span>
                                <span class="recommended-change ${changeClass}">${changeSign}${stock.change_pct}%</span>
                            </div>
                        `;
                    }).join('');
                    container.innerHTML = html;
                    console.log('推荐股票加载完成:', data.stocks.length, '只');
                } else {
                    // API失败时使用默认数据
                    const defaultStocks = [
                        { code: '000729', name: '燕京啤酒' },
                        { code: '000301', name: '东方市场' },
                        { code: '000078', name: '海王生物' },
                        { code: '000650', name: '仁和药业' }
                    ];
                    const html = defaultStocks.map(stock => `
                        <div class="recommended-item" onclick="quickQuery('${stock.code}')">
                            <span class="recommended-code">${stock.code}</span>
                            <span class="recommended-name">${escapeHtml(stock.name)}</span>
                        </div>
                    `).join('');
                    container.innerHTML = html;
                }
            })
            .catch(error => {
                console.error('获取推荐股票失败:', error);
                // 使用默认数据
                const container = document.getElementById('recommendedGrid');
                if (container) {
                    const defaultStocks = [
                        { code: '000729', name: '燕京啤酒' },
                        { code: '000301', name: '东方市场' },
                        { code: '000078', name: '海王生物' },
                        { code: '000650', name: '仁和药业' }
                    ];
                    const html = defaultStocks.map(stock => `
                        <div class="recommended-item" onclick="quickQuery('${stock.code}')">
                            <span class="recommended-code">${stock.code}</span>
                            <span class="recommended-name">${escapeHtml(stock.name)}</span>
                        </div>
                    `).join('');
                    container.innerHTML = html;
                }
            });
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // ==================== 版本管理 ====================

    /**
     * 检查用户是否为专业版
     * :return: boolean
     */
    function checkProStatus() {
        const isPro = localStorage.getItem('isProUser') === 'true';
        console.log('专业版状态:', isPro);
        return isPro;
    }

    /**
     * 更新UI显示版本状态
     */
    function updateVersionUI() {
        const isPro = checkProStatus();
        const versionBadge = document.getElementById('versionBadge');
        const upgradeBtn = document.getElementById('upgradeBtn');

        if (isPro) {
            // 专业版用户
            if (versionBadge) {
                versionBadge.textContent = '专业版';
                versionBadge.classList.add('pro');
            }
            if (upgradeBtn) {
                upgradeBtn.classList.add('hidden');
            }
            console.log('✅ 专业版用户');
        } else {
            // 免费版用户
            if (versionBadge) {
                versionBadge.textContent = '免费版';
                versionBadge.classList.remove('pro');
            }
            if (upgradeBtn) {
                upgradeBtn.classList.remove('hidden');
            }
            console.log('ℹ️ 免费版用户');
        }
    }

    /**
     * 显示升级弹窗
     */
    window.showUpgradeModal = function() {
        showModal('upgradeModal');
    };

    /**
     * 购买专业版（iOS IAP）
     */
    window.purchasePro = function() {
        // 尝试调用iOS原生IAP
        if (window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.purchasePro) {
            console.log('调用iOS IAP购买...');
            window.webkit.messageHandlers.purchasePro.postMessage({
                product_id: 'com.stockanalysis.pro.lifetime'
            });
        } else {
            // 非iOS环境或测试环境
            console.log('模拟购买流程...');
            showToast('正在跳转至App Store购买页面...', 'info');
            setTimeout(() => {
                const confirmed = confirm('在真实App中，这里会调用Apple IAP进行购买。\n\n价格: ¥15.00\n购买后解锁全部高级功能！\n\n是否模拟购买成功？');
                if (confirmed) {
                    activateProVersion();
                }
            }, 500);
        }
    };

    /**
     * 激活专业版（购买成功后调用）
     */
    window.activateProVersion = function() {
        localStorage.setItem('isProUser', 'true');
        localStorage.setItem('purchaseDate', new Date().toISOString());
        updateVersionUI();
        closeModal('upgradeModal');
        showToast('🎉 恭喜！已升级为专业版用户', 'success');
        console.log('✅ 专业版已激活');
    };

    /**
     * 恢复购买
     */
    window.restorePurchase = function() {
        if (window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.restorePurchase) {
            console.log('调用iOS恢复购买...');
            window.webkit.messageHandlers.restorePurchase.postMessage({});
        } else {
            // 模拟恢复购买
            const purchaseDate = localStorage.getItem('purchaseDate');
            if (purchaseDate) {
                showToast('✅ 已恢复购买', 'success');
            } else {
                showToast('未找到购买记录', 'warning');
            }
        }
    };

    // 页面加载时检查版本状态
    document.addEventListener('DOMContentLoaded', function() {
        updateVersionUI();
    });

})();
