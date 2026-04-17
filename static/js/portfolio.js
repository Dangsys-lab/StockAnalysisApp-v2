/**
 * 自选股管理页面交互脚本
 * 
 * 功能:
 * - 加载自选股票列表
 * - 添加/删除自选股
 * - 分组筛选
 * - 导入/导出
 */

// 页面加载
document.addEventListener('DOMContentLoaded', function() {
    loadPortfolio();
    loadGroups();
});

/**
 * 加载自选列表
 */
async function loadPortfolio(groupName = null) {
    const listDiv = document.getElementById('portfolioList');
    listDiv.innerHTML = '<p class="loading">⏳ 加载中...</p>';
    
    try {
        let url = '/api/portfolio';
        if (groupName && groupName !== 'all') {
            url += `?group=${encodeURIComponent(groupName)}`;
        }
        
        const response = await fetch(url);
        const data = await response.json();
        
        if (data.success) {
            renderPortfolioList(data.stocks, data.total_count);
            updateGroupFilter(data.groups, groupName);
        } else {
            listDiv.innerHTML = '<p class="error">❌ 加载失败</p>';
        }
    } catch (error) {
        console.error('加载自选列表失败:', error);
        listDiv.innerHTML = '<p class="error">网络错误，请刷新重试</p>';
    }
}

/**
 * 渲染自选列表
 */
function renderPortfolioList(stocks, totalCount) {
    const listDiv = document.getElementById('portfolioList');
    
    if (!stocks || stocks.length === 0) {
        listDiv.innerHTML = `
            <div class="empty-state">
                <p>📭 暂无自选股票</p>
                <button onclick="showAddDialog()" class="btn-primary mt-2">
                    添加第一只股票
                </button>
            </div>
        `;
        return;
    }
    
    let html = `<p class="list-summary">共 ${totalCount} 只股票</p>`;
    
    html += '<div class="stock-cards">';
    
    stocks.forEach(stock => {
        const displayName = stock.stock_name && stock.stock_name !== stock.stock_code 
            ? stock.stock_name 
            : '加载中...';
        html += `
            <div class="stock-card" data-code="${stock.stock_code}">
                <div class="card-header-row">
                    <span class="stock-code">${stock.stock_code}</span>
                    <span class="stock-name" id="name-${stock.stock_code}">${displayName}</span>
                    <span class="group-tag">${stock.group_name || '默认'}</span>
                </div>
                
                <div class="card-info">
                    <span class="current-price" id="price-${stock.stock_code}">加载中...</span>
                    ${stock.add_price ? `<span>添加价格: ¥${stock.add_price.toFixed(2)}</span>` : ''}
                    ${stock.add_date ? `<span>添加日期: ${stock.add_date.split(' ')[0]}</span>` : ''}
                    ${stock.note ? `<span class="note-text">备注: ${stock.note}</span>` : ''}
                </div>
                
                <div class="card-actions">
                    <a href="/report?code=${stock.stock_code}" class="action-link">查看报告</a>
                    <button onclick="removeStock('${stock.stock_code}')" class="btn-danger-sm">
                        移除
                    </button>
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    
    listDiv.innerHTML = html;
    
    // 异步加载当前价格
    stocks.forEach(stock => {
        loadCurrentPrice(stock.stock_code);
    });
}

/**
 * 加载单只股票当前价格
 */
async function loadCurrentPrice(stockCode) {
    try {
        const response = await fetch(`/api/stock/${stockCode}/basic`);
        const data = await response.json();
        
        const priceEl = document.getElementById(`price-${stockCode}`);
        const nameEl = document.getElementById(`name-${stockCode}`);
        
        if (priceEl && data.success && data.data) {
            const price = data.data.price;
            const change = data.data.change || 0;
            const changeClass = change >= 0 ? 'text-success' : 'text-danger';
            const changePrefix = change >= 0 ? '+' : '';
            
            if (price) {
                priceEl.innerHTML = `当前: ¥${price.toFixed(2)} <span class="${changeClass}">(${changePrefix}${change.toFixed(2)}%)</span>`;
            } else {
                priceEl.innerHTML = '当前: --';
            }
        }
        
        if (nameEl && data.success && data.data && data.data.name) {
            nameEl.textContent = data.data.name;
        }
    } catch (e) {
        const priceEl = document.getElementById(`price-${stockCode}`);
        if (priceEl) {
            priceEl.innerHTML = '当前: --';
        }
    }
}

/**
 * 加载分组列表
 */
async function loadGroups() {
    try {
        const response = await fetch('/api/portfolio/groups');
        const data = await response.json();
        
        if (data.success && data.groups) {
            const select = document.getElementById('addGroupName');
            
            // 清空现有选项（保留默认）
            select.innerHTML = '<option value="默认">默认</option>';
            
            // 添加已有分组
            data.groups.forEach(g => {
                if (g.group_name !== '默认') {
                    select.innerHTML += `<option value="${g.group_name}">${g.group_name}</option>`;
                }
            });
        }
    } catch (error) {
        console.error('加载分组失败:', error);
    }
}

/**
 * 更新分组筛选按钮
 */
function updateGroupFilter(groups, currentGroup) {
    const filterBar = document.getElementById('groupFilter');
    
    let html = `
        <button onclick="filterGroup('all')" class="filter-btn ${currentGroup === 'all' ? 'active' : ''}" data-group="all">
            全部 (${groups.reduce((sum, g) => sum + g.count, 0)})
        </button>
    `;
    
    groups.forEach(g => {
        html += `
            <button onclick="filterGroup('${g.group_name}')" 
                    class="filter-btn ${currentGroup === g.group_name ? 'active' : ''}" 
                    data-group="${g.group_name}">
                ${g.group_name} (${g.count})
            </button>
        `;
    });
    
    filterBar.innerHTML = html;
}

/**
 * 筛选分组
 */
function filterGroup(groupName) {
    loadPortfolio(groupName);
}

/**
 * 显示添加弹窗
 */
function showAddDialog() {
    document.getElementById('addModal').classList.remove('hidden');
    document.getElementById('addStockCode').focus();
}

/**
 * 关闭弹窗
 */
function closeModal() {
    document.getElementById('addModal').classList.add('hidden');
    document.getElementById('addStockCode').value = '';
    document.getElementById('addStockName').value = '';
    document.getElementById('addNote').value = '';
}

/**
 * 处理添加股票
 */
async function handleAddStock(event) {
    event.preventDefault();
    
    const stockCode = document.getElementById('addStockCode').value.trim();
    const stockName = document.getElementById('addStockName').value.trim();
    const groupName = document.getElementById('addGroupName').value;
    const note = document.getElementById('addNote').value.trim();
    
    if (!stockCode || stockCode.length !== 6) {
        alert('请输入有效的6位股票代码');
        return false;
    }
    
    try {
        const response = await fetch('/api/portfolio', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                stock_code: stockCode,
                stock_name: stockName,
                group_name: groupName,
                note: note
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert(`✅ ${stockCode} 已添加到自选列表`);
            closeModal();
            loadPortfolio();
            loadGroups();
        } else if (data.already_exists) {
            alert(`ℹ️ ${stockCode} 已在自选列表中`);
            closeModal();
        } else {
            alert(`❌ 添加失败: ${data.message}`);
        }
    } catch (error) {
        console.error('添加失败:', error);
        alert('网络错误，请重试');
    }
    
    return false;
}

/**
 * 移除股票
 */
async function removeStock(stockCode) {
    if (!confirm(`确定要从自选列表移除 ${stockCode} 吗？`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/portfolio/${stockCode}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert(`✅ ${stockCode} 已从自选列表移除`);
            loadPortfolio();
            loadGroups();
        } else {
            alert(`❌ 移除失败: ${data.message}`);
        }
    } catch (error) {
        console.error('移除失败:', error);
        alert('网络错误，请重试');
    }
}
