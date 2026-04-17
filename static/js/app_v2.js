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

    // 指标解释数据
    const INDICATOR_EXPLANATIONS = {
        'MA': '移动平均线 - 衡量一定时期内平均价格，用于判断趋势方向。MA5代表5天均线，MA10代表10天均线。',
        'EMA': '指数移动平均线 - 对近期价格赋予更高权重，反应更灵敏，适合短线分析。',
        'BOLL': '布林带 - 由三条轨道线组成，中轨为均线，上下轨为标准差范围。价格突破上轨可能超买，跌破下轨可能超卖。',
        'DMI': '趋向指标 - 衡量趋势强度和方向，由+DI、-DI和ADX组成。ADX越高趋势越强。',
        'SAR': '抛物线指标 - 止损止盈参考点，价格在SAR上方为多头市场，下方为空头市场。',
        'RSI': '相对强弱指标 - 0-100区间，衡量多空力量对比。>70超买，<30超卖。',
        'KDJ': '随机指标 - 短线交易信号，由K、D、J三条线组成。金叉看多，死叉看空。',
        'WR': '威廉指标 - 0-100区间，衡量当前价格在近期高低点中的相对位置。>80超卖，<20超买。',
        'CCI': '顺势指标 - 检测异常波动，>100超买，<-100超卖，适合捕捉极端行情。',
        'BIAS': '乖离率 - 衡量当前价格偏离均线的程度，偏离过大可能出现回归。',
        'VOL': '成交量 - 衡量交易活跃程度，成交量放大通常伴随价格趋势确认。',
        'OBV': '能量潮 - 将成交量与价格结合，量价配合验证趋势可靠性。',
        'VR': '成交量比率 - 衡量市场活跃度，>150过热，<40过冷。',
        '量比': '量比 - 当日成交量与近5日均量的比值，>1放量，<1缩量。',
        'MAVOL': '成交量均线 - 成交量的移动平均，用于判断成交量趋势。',
        'ATR': '平均真实波幅 - 衡量价格波动性，ATR越大波动越剧烈。',
        'TR': '真实波幅 - 当日最高价与最低价、昨收价的最大差值。'
    };

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
            const indexData = data.index_data || {};
            
            const shData = indexData['sh000001'];
            const szData = indexData['sz399001'];
            const cybData = indexData['sz399006'];
            
            const shEl = document.getElementById('shIndex');
            const szEl = document.getElementById('szIndex');
            const cybEl = document.getElementById('cybIndex');
            const adEl = document.getElementById('advanceDecline');
            
            if (shEl && shData && shData.price) {
                const changeSign = shData.change >= 0 ? '+' : '';
                const colorClass = shData.change >= 0 ? 'price-up' : 'price-down';
                shEl.innerHTML = `<span class="${colorClass}">${shData.price} ${changeSign}${shData.change}%</span>`;
            }
            if (szEl && szData && szData.price) {
                const changeSign = szData.change >= 0 ? '+' : '';
                const colorClass = szData.change >= 0 ? 'price-up' : 'price-down';
                szEl.innerHTML = `<span class="${colorClass}">${szData.price} ${changeSign}${szData.change}%</span>`;
            }
            if (cybEl && cybData && cybData.price) {
                const changeSign = cybData.change >= 0 ? '+' : '';
                const colorClass = cybData.change >= 0 ? 'price-up' : 'price-down';
                cybEl.innerHTML = `<span class="${colorClass}">${cybData.price} ${changeSign}${cybData.change}%</span>`;
            }
            if (adEl) {
                const changes = [shData, szData, cybData].filter(d => d && d.change !== null);
                if (changes.length > 0) {
                    const upCount = changes.filter(d => d.change >= 0).length;
                    adEl.textContent = `${upCount}:${changes.length - upCount}`;
                }
            }
            
            const proInsight = document.getElementById('marketProInsight');
            if (proInsight) {
                const isPro = checkProStatus();
                if (!isPro) {
                    proInsight.classList.remove('hidden');
                }
            }
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

            const isPro = checkProStatus();
            let url = `/api/indicators/${code}?is_pro=${isPro}`;
            
            if (isPro) {
                const savedParams = getIndicatorParams();
                if (savedParams && Object.keys(savedParams).length > 0) {
                    url += `&user_params=${encodeURIComponent(JSON.stringify(savedParams))}`;
                }
            }

            const response = await fetch(url, {
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

        const isPro = checkProStatus();
        const priceChangeClass = (data.change || 0) >= 0 ? 'price-up' : 'price-down';
        const changePrefix = (data.change || 0) >= 0 ? '+' : '';

        let indicatorsHtml = '';

        if (data.indicators && data.indicators.length > 0) {
            const freeIndicators = data.indicators.filter(i => !i.is_pro_only);
            const proIndicators = data.indicators.filter(i => i.is_pro_only);

            const freeTrend = freeIndicators.filter(i => i.category === 'trend');
            const freeOsc = freeIndicators.filter(i => i.category === 'oscillator');

            if (freeTrend.length > 0) {
                indicatorsHtml += buildIndicatorSection('📈 趋势类指标', freeTrend, isPro);
            }
            if (freeOsc.length > 0) {
                indicatorsHtml += buildIndicatorSection('📊 摆动类指标', freeOsc, isPro);
            }

            if (isPro && proIndicators.length > 0) {
                const proTrend = proIndicators.filter(i => i.category === 'trend');
                const proOsc = proIndicators.filter(i => i.category === 'oscillator');
                const proVol = proIndicators.filter(i => i.category === 'volume');
                const proPrice = proIndicators.filter(i => i.category === 'price');

                if (proTrend.length > 0) {
                    indicatorsHtml += buildIndicatorSection('📈 趋势类指标（高级）', proTrend, isPro);
                }
                if (proOsc.length > 0) {
                    indicatorsHtml += buildIndicatorSection('📊 摆动类指标（高级）', proOsc, isPro);
                }
                if (proVol.length > 0) {
                    indicatorsHtml += buildIndicatorSection('💰 成交量类指标', proVol, isPro);
                }
                if (proPrice.length > 0) {
                    indicatorsHtml += buildIndicatorSection('📐 价格形态指标', proPrice, isPro);
                }
            }

            if (!isPro && proIndicators.length > 0) {
                indicatorsHtml += `
                    <div class="indicators-section pro-locked-section">
                        <h4>🔒 专业版指标 <span class="pro-badge">PRO</span></h4>
                        <div class="indicator-grid pro-locked">
                            ${proIndicators.map(ind => `
                                <div class="indicator-item locked" onclick="showUpgradeInfo()">
                                    <span class="indicator-name">${ind.name}</span>
                                    <span class="indicator-value">🔒</span>
                                    <span class="indicator-status status-locked">专业版</span>
                                </div>
                            `).join('')}
                        </div>
                        <p class="pro-hint">升级专业版解锁全部 ${data.indicators.length} 个技术指标 →</p>
                    </div>
                `;
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

            <div style="margin-top:16px; text-align:center; display:flex; gap:8px; justify-content:center; flex-wrap:wrap;">
                <button onclick="generateReport('${data.stock_code || data.code || ''}')" class="btn-secondary">📋 生成完整报告</button>
                <button onclick="addToPortfolioFromResult('${data.stock_code || data.code || ''}', '${escapeHtml(data.stock_name || data.name || '')}')" class="btn-secondary">⭐ 加入自选</button>
            </div>
        `;
    }

    window.addToPortfolioFromResult = function(code, name) {
        fetch('/api/portfolio', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                stock_code: code,
                stock_name: name,
                group_name: '跟踪中'
            })
        })
        .then(r => r.json())
        .then(result => {
            if (result.success) {
                showToast(`已将 ${name || code} 加入自选`, 'success');
            } else if (result.already_exists) {
                showToast(`${name || code} 已在自选列表中`, 'warning');
            } else {
                showToast(result.message || '添加失败', 'warning');
            }
        })
        .catch(() => showToast('网络错误', 'error'));
    };

    function buildIndicatorSection(title, indicators, isPro) {
        const items = indicators.map(ind => {
            const statusClass = getStatusClass(ind.status);
            const isProOnly = ind.is_pro_only === true;
            const indicatorName = ind.name || '';
            const baseName = indicatorName.replace(/\(.*\)/g, '').trim();
            const hasExplanation = INDICATOR_EXPLANATIONS[baseName] !== undefined;
            
            if (!isPro && isProOnly) {
                const blurredValue = blurValue(ind.value);
                return `
                    <div class="indicator-item pro-blurred" onclick="showUpgradeInfo()">
                        <span class="indicator-name">
                            ${indicatorName} <span class="mini-pro-badge">PRO</span>
                        </span>
                        <span class="indicator-value blurred">${blurredValue}</span>
                        <span class="indicator-status status-locked">解锁查看</span>
                    </div>
                `;
            }
            
            let displayValue = '--';
            if (ind.value !== null && ind.value !== undefined) {
                if (typeof ind.value === 'number') {
                    displayValue = formatValue(ind.value);
                } else {
                    displayValue = String(ind.value);
                }
            }
            
            const helpIcon = hasExplanation ? `<span class="indicator-help" data-indicator="${baseName}" onclick="event.stopPropagation();showIndicatorExplanation(event, '${baseName}')">?</span>` : '';
            
            return `
                <div class="indicator-item ${hasExplanation ? 'has-help' : ''}">
                    <span class="indicator-name">
                        ${indicatorName}
                        ${helpIcon}
                    </span>
                    <span class="indicator-value">${displayValue}</span>
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

    function blurValue(value) {
        if (value === null || value === undefined) return '●●.●●';
        if (typeof value === 'number') {
            const intPart = Math.floor(Math.abs(value));
            const len = String(intPart).length;
            return '●'.repeat(Math.min(len, 3)) + '.●●';
        }
        return '●●.●●';
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
        window.location.href = `/report_page?code=${code}`;
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

    window.showAboutModal = function() {
        const isPro = checkProStatus();
        const modal = document.createElement('div');
        modal.className = 'modal-overlay';
        modal.id = 'aboutModal';
        modal.onclick = function(e) { if (e.target === modal) closeModal('aboutModal'); };
        modal.innerHTML = `
            <div class="modal-content" onclick="event.stopPropagation()">
                <div class="modal-header">
                    <h3>📊 股票分析工具</h3>
                    <button onclick="closeModal('aboutModal')" class="modal-close">×</button>
                </div>
                <div class="modal-body" style="text-align:center;">
                    <p style="font-size:18px;font-weight:700;margin-bottom:4px;">股票技术分析工具 v2.0</p>
                    <p style="color:var(--text-secondary);margin-bottom:16px;">当前版本: ${isPro ? '👑 专业版' : '🆓 免费版'}</p>
                    <div style="text-align:left;background:var(--bg-input);padding:16px;border-radius:12px;margin-bottom:16px;">
                        <p style="margin-bottom:8px;">✅ 17+ 技术指标客观计算</p>
                        <p style="margin-bottom:8px;">✅ 市场环境实时感知</p>
                        <p style="margin-bottom:8px;">✅ 综合分析报告生成</p>
                        <p style="margin-bottom:8px;">✅ 自选股管理</p>
                        <p>✅ 多数据源容错</p>
                    </div>
                    <p style="font-size:12px;color:var(--text-tertiary);">数据来源: 东方财富/新浪财经/腾讯财经</p>
                    <p style="font-size:12px;color:var(--text-tertiary);margin-top:4px;">联系开发者: nimeipo@126.com</p>
                </div>
                <div class="modal-footer">
                    ${!isPro ? '<button onclick="closeModal(\'aboutModal\');showUpgradeInfo()" class="btn-primary btn-block">⭐ 升级专业版</button>' : '<button onclick="closeModal(\'aboutModal\')" class="btn-secondary btn-block">关闭</button>'}
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        modal.classList.remove('hidden');
        document.body.style.overflow = 'hidden';
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
            alert('在真实App中，这里会调用Apple IAP进行购买。\n\n价格: ¥12.00\n购买后解锁全部高级功能！');
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
                        const changeDisplay = (stock.change_pct === 0 || stock.change_pct === null) ? '--' : `${changeSign}${stock.change_pct}%`;
                        return `
                            <div class="recommended-item" onclick="quickQuery('${stock.code}')">
                                <span class="recommended-code">${stock.code}</span>
                                <span class="recommended-name">${escapeHtml(stock.name)}</span>
                                <span class="recommended-change ${changeClass}">${changeDisplay}</span>
                            </div>
                        `;
                    }).join('');
                    container.innerHTML = html;
                    console.log('推荐股票加载完成:', data.stocks.length, '只');
                } else {
                    showDefaultStocks(container);
                }
            })
            .catch(error => {
                console.error('获取推荐股票失败:', error);
                const container = document.getElementById('recommendedGrid');
                if (container) {
                    showDefaultStocks(container);
                }
            });
    }

    function showDefaultStocks(container) {
        const defaultStocks = [
            { code: '600519', name: '贵州茅台' },
            { code: '601318', name: '中国平安' },
            { code: '600036', name: '招商银行' },
            { code: '000333', name: '美的集团' }
        ];
        const html = defaultStocks.map(stock => `
            <div class="recommended-item" onclick="quickQuery('${stock.code}')">
                <span class="recommended-code">${stock.code}</span>
                <span class="recommended-name">${escapeHtml(stock.name)}</span>
                <span class="recommended-change">--</span>
            </div>
        `).join('');
        container.innerHTML = html;
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // ==================== 合规弹窗 ====================

    function checkCompliance() {
        var accepted = null;
        try { accepted = localStorage.getItem('compliance_accepted'); } catch(e) {}
        if (!accepted) {
            var modal = document.getElementById('complianceModal');
            if (modal) modal.style.display = 'block';
        }
    }

    window.acceptCompliance = function() {
        try { localStorage.setItem('compliance_accepted', 'true'); } catch(e) {}
        var modal = document.getElementById('complianceModal');
        if (modal) modal.style.display = 'none';
    };

    // ==================== 数据状态标识 ====================

    function updateDataStatusBadge() {
        var status = getEffectiveUserStatus();
        var badge = document.getElementById('dataStatusBadge');
        if (!badge) return;
        
        if (status.status === 'pro') {
            badge.className = 'data-status-badge status-pro';
            badge.innerHTML = '🟢 实时数据';
        } else if (status.status === 'trial') {
            badge.className = 'data-status-badge status-trial';
            badge.innerHTML = '🟡 试用中 · 实时数据';
        } else {
            badge.className = 'data-status-badge status-free';
            badge.innerHTML = '🔴 数据延迟15分钟';
        }
    }

    // ==================== 试用期管理 ====================

    function showTrialBadge(userStatus) {
        var badge = document.getElementById('trialBadge');
        
        if (!badge) return;
        
        if (userStatus.status === 'trial') {
            badge.style.display = 'inline-flex';
            
            var daysLeftEl = document.getElementById('trialDaysLeft');
            if (daysLeftEl) {
                daysLeftEl.textContent = userStatus.daysLeft;
            }
            
            var progressEl = document.getElementById('trialProgress');
            if (progressEl) {
                progressEl.style.width = userStatus.progress + '%';
            }
            
            console.log('[试用期] 剩余 ' + userStatus.daysLeft + ' 天, 进度 ' + userStatus.progress.toFixed(1) + '%');
        } else {
            badge.style.display = 'none';
        }
    }

    function showUpgradePrompt(reason) {
        var message = reason || '升级专业版(¥12终身)解锁更多功能';
        var toast = document.createElement('div');
        toast.className = 'upgrade-toast';
        toast.style.cssText = 'position:fixed;top:80px;left:50%;transform:translateX(-50%);background:var(--warning-color);color:white;padding:12px 24px;border-radius:var(--radius-md);font-size:var(--font-size-sm);z-index:300;box-shadow:var(--shadow-lg);max-width:90%;text-align:center;';
        toast.textContent = message;
        document.body.appendChild(toast);
        setTimeout(function() {
            if (toast.parentNode) toast.parentNode.removeChild(toast);
        }, 3000);
    }

    function showTrialExpiredModal() {
        var modalHTML = '<div id="trialExpiredModal" class="modal-overlay" style="display:flex;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.5);z-index:1000;justify-content:center;align-items:center;">' +
            '<div class="modal-content" style="max-width:400px;background:var(--bg-card);border-radius:var(--radius-lg);padding:24px;margin:16px;">' +
                '<div class="modal-header" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">' +
                    '<h3 style="margin:0;">⏰ 试用期结束</h3>' +
                    '<button onclick="closeTrialExpiredModal()" style="background:none;border:none;font-size:24px;cursor:pointer;color:var(--text-secondary);">&times;</button>' +
                '</div>' +
                '<div class="modal-body">' +
                    '<p style="margin-bottom:15px;">感谢您体验专业版功能!</p>' +
                    '<div style="background:var(--bg-input);padding:15px;border-radius:8px;margin-bottom:15px;">' +
                        '<h4 style="margin-top:0;">🎁 升级专业版(¥12终身)即可继续使用:</h4>' +
                        '<ul style="margin:0;padding-left:20px;">' +
                            '<li>✅ <strong>17个技术指标</strong>(含MACD、KDJ等)</li>' +
                            '<li>✅ <strong>10只自选股</strong>(免费版仅5只)</li>' +
                            '<li>✅ <strong>FC云端算力</strong>(实时计算)</li>' +
                            '<li>✅ <strong>无广告</strong>清爽体验</li>' +
                        '</ul>' +
                    '</div>' +
                    '<p style="font-size:13px;color:var(--text-secondary);text-align:center;">📢 一杯咖啡的钱,终身使用,无需续费!</p>' +
                '</div>' +
                '<div style="display:flex;gap:10px;justify-content:center;margin-top:16px;">' +
                    '<button onclick="handleUpgradeClick()" class="btn-primary" style="flex:1;">💎 立即升级 ¥12</button>' +
                    '<button onclick="closeTrialExpiredModal()" class="btn-secondary" style="flex:1;">稍后再说</button>' +
                '</div>' +
            '</div>' +
        '</div>';
        
        document.body.insertAdjacentHTML('beforeend', modalHTML);
    }

    window.closeTrialExpiredModal = function() {
        var modal = document.getElementById('trialExpiredModal');
        if (modal) modal.remove();
    };

    window.handleUpgradeClick = function() {
        closeTrialExpiredModal();
        if (typeof handlePurchase === 'function') {
            handlePurchase();
        } else {
            showUpgradeInfo();
        }
    };

    function checkTrialStatus() {
        const TRIAL_DURATION_HOURS = 48;
        
        let firstLaunch = null;
        try {
            firstLaunch = localStorage.getItem('firstLaunchDate');
        } catch (e) {}
        
        if (!firstLaunch) {
            try {
                const now = new Date().toISOString();
                localStorage.setItem('firstLaunchDate', now);
            } catch (e) {}
            
            return {
                isTrial: true,
                daysLeft: 2,
                hoursLeft: TRIAL_DURATION_HOURS,
                totalHours: TRIAL_DURATION_HOURS,
                progress: 0,
                firstLaunch: true
            };
        }
        
        const launchDate = new Date(firstLaunch);
        const now = new Date();
        const hoursPassed = Math.floor((now - launchDate) / (1000 * 60 * 60));
        const hoursLeft = Math.max(0, TRIAL_DURATION_HOURS - hoursPassed);
        
        return {
            isTrial: hoursLeft > 0,
            daysLeft: Math.ceil(hoursLeft / 24),
            hoursLeft: hoursLeft,
            totalHours: TRIAL_DURATION_HOURS,
            progress: Math.min(100, (hoursPassed / TRIAL_DURATION_HOURS) * 100),
            firstLaunch: false
        };
    }

    function getEffectiveUserStatus() {
        const trialInfo = checkTrialStatus();
        let isPurchased = false;
        try {
            isPurchased = localStorage.getItem('isProUser') === 'true';
        } catch (e) {}
        
        if (isPurchased) {
            return { 
                status: 'pro', 
                canUseAllFeatures: true,
                isLifetimePro: true
            };
        } else if (trialInfo.isTrial) {
            return { 
                status: 'trial', 
                canUseAllFeatures: true,
                ...trialInfo
            };
        } else {
            return { 
                status: 'free', 
                canUseAllFeatures: false
            };
        }
    }

    // ==================== 版本管理 ====================

    /**
     * 检查用户是否为专业版
     * :return: boolean
     */
    function checkProStatus() {
        const userStatus = getEffectiveUserStatus();
        const isPro = userStatus.canUseAllFeatures;
        console.log('专业版状态:', isPro, '(用户类型:', userStatus.status + ')');
        return isPro;
    }

    /**
     * 更新UI显示版本状态
     */
    function updateVersionUI() {
        const userStatus = getEffectiveUserStatus();
        const versionBadge = document.getElementById('versionBadge');
        const upgradeBtn = document.getElementById('upgradeBtn');

        if (userStatus.status === 'pro') {
            if (versionBadge) {
                versionBadge.textContent = '专业版';
                versionBadge.classList.add('pro');
            }
            if (upgradeBtn) {
                upgradeBtn.classList.add('hidden');
            }
            console.log('✅ 专业版用户');
        } else if (userStatus.status === 'trial') {
            if (versionBadge) {
                versionBadge.textContent = '试用版';
                versionBadge.classList.add('pro');
            }
            if (upgradeBtn) {
                upgradeBtn.classList.remove('hidden');
            }
            console.log('⏱️ 试用期用户，剩余', userStatus.daysLeft, '天');
        } else {
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
                const confirmed = confirm('在真实App中，这里会调用Apple IAP进行购买。\n\n价格: ¥12.00\n购买后解锁全部高级功能！\n\n是否模拟购买成功？');
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
        checkCompliance();
        updateVersionUI();
        updateParamsButton();
        loadSavedParams();
        updateDataStatusBadge();

        var userStatus = getEffectiveUserStatus();
        if (userStatus.status === 'trial') {
            showTrialBadge(userStatus);
        }
        if (userStatus.status === 'free' && !userStatus.firstLaunch) {
            var lastStatus = null;
            try { lastStatus = sessionStorage.getItem('lastUserStatus'); } catch(e) {}
            if (lastStatus === 'trial') {
                showTrialExpiredModal();
            }
        }
        try { sessionStorage.setItem('lastUserStatus', userStatus.status); } catch(e) {}
    });

    // ==================== 参数设置功能 ====================

    /**
     * 更新参数设置按钮显示状态
     */
    function updateParamsButton() {
        const isPro = checkProStatus();
        const paramsBtn = document.getElementById('paramsBtn');
        
        if (paramsBtn) {
            if (isPro) {
                paramsBtn.classList.remove('hidden');
            } else {
                paramsBtn.classList.add('hidden');
            }
        }
    }

    /**
     * 显示参数设置弹窗
     */
    window.showParamsModal = function() {
        if (!checkProStatus()) {
            showToast('参数设置仅限专业版用户', 'warning');
            return;
        }
        showModal('paramsModal');
    };

    /**
     * 更新参数显示值
     */
    window.updateParamDisplay = function(input) {
        const valueSpan = document.getElementById(input.id + '_value');
        if (valueSpan) {
            valueSpan.textContent = input.value;
        }
    };

    /**
     * 加载已保存的参数
     */
    function loadSavedParams() {
        const savedParams = localStorage.getItem('indicatorParams');
        if (savedParams) {
            try {
                const params = JSON.parse(savedParams);
                Object.keys(params).forEach(key => {
                    const input = document.getElementById(key);
                    if (input) {
                        input.value = params[key];
                        const valueSpan = document.getElementById(key + '_value');
                        if (valueSpan) {
                            valueSpan.textContent = params[key];
                        }
                    }
                });
                console.log('已加载保存的参数设置');
            } catch (e) {
                console.error('加载参数失败:', e);
            }
        }
    }

    /**
     * 保存参数设置
     */
    window.saveParams = function() {
        const params = {};
        const paramInputs = [
            'rsi_period', 'kdj_n', 'kdj_m1', 'kdj_m2',
            'wr_period', 'cci_period', 'boll_period', 'boll_std_dev', 'atr_period'
        ];
        
        paramInputs.forEach(id => {
            const input = document.getElementById(id);
            if (input) {
                params[id] = parseFloat(input.value);
            }
        });
        
        localStorage.setItem('indicatorParams', JSON.stringify(params));
        closeModal('paramsModal');
        showToast('参数设置已保存', 'success');
        console.log('保存参数:', params);
    };

    /**
     * 重置参数为默认值
     */
    window.resetParams = function() {
        const defaults = {
            rsi_period: 14,
            kdj_n: 9,
            kdj_m1: 3,
            kdj_m2: 3,
            wr_period: 14,
            cci_period: 20,
            boll_period: 20,
            boll_std_dev: 2.0,
            atr_period: 14
        };
        
        Object.keys(defaults).forEach(key => {
            const input = document.getElementById(key);
            if (input) {
                input.value = defaults[key];
                const valueSpan = document.getElementById(key + '_value');
                if (valueSpan) {
                    valueSpan.textContent = defaults[key];
                }
            }
        });
        
        showToast('已恢复默认值', 'info');
    };

    /**
     * 获取当前参数（用于API请求）
     */
    function getIndicatorParams() {
        const savedParams = localStorage.getItem('indicatorParams');
        if (savedParams) {
            try {
                return JSON.parse(savedParams);
            } catch (e) {
                return null;
            }
        }
        return null;
    }

    // 指标解释气泡功能
    let activeTooltip = null;

    window.showIndicatorExplanation = function(event, indicatorName) {
        event.preventDefault();
        event.stopPropagation();

        // 关闭已有的气泡
        if (activeTooltip) {
            activeTooltip.remove();
            activeTooltip = null;
        }

        const explanation = INDICATOR_EXPLANATIONS[indicatorName];
        if (!explanation) return;

        const tooltip = document.createElement('div');
        tooltip.className = 'indicator-tooltip';
        tooltip.innerHTML = `
            <div class="tooltip-header">
                <strong>${indicatorName}</strong>
                <button class="tooltip-close" onclick="closeIndicatorTooltip()">×</button>
            </div>
            <div class="tooltip-content">
                ${explanation}
            </div>
        `;

        document.body.appendChild(tooltip);
        activeTooltip = tooltip;

        // 定位气泡
        const targetRect = event.target.getBoundingClientRect();
        const tooltipRect = tooltip.getBoundingClientRect();
        
        let top = targetRect.bottom + 8;
        let left = targetRect.left;
        
        // 确保气泡不超出屏幕
        if (left + tooltipRect.width > window.innerWidth) {
            left = window.innerWidth - tooltipRect.width - 16;
        }
        if (top + tooltipRect.height > window.innerHeight) {
            top = targetRect.top - tooltipRect.height - 8;
        }
        if (left < 16) left = 16;
        
        tooltip.style.top = top + 'px';
        tooltip.style.left = left + 'px';

        // 点击其他地方关闭气泡
        setTimeout(() => {
            document.addEventListener('click', closeIndicatorTooltipOnOutside);
        }, 10);
    };

    window.closeIndicatorTooltip = function() {
        if (activeTooltip) {
            activeTooltip.remove();
            activeTooltip = null;
        }
        document.removeEventListener('click', closeIndicatorTooltipOnOutside);
    };

    function closeIndicatorTooltipOnOutside(event) {
        if (activeTooltip && !activeTooltip.contains(event.target) && !event.target.classList.contains('indicator-help')) {
            closeIndicatorTooltip();
        }
    }

})();
