// 图表管理模块
let charts = {};

// 初始化所有图表
function initCharts() {
    // 弹幕时间分布图
    const danmakuTimeCtx = document.getElementById('danmakuTimeChart').getContext('2d');
    charts.danmakuTime = new Chart(danmakuTimeCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: '弹幕数量',
                data: [],
                borderColor: '#6366f1',
                backgroundColor: 'rgba(99, 102, 241, 0.1)',
                tension: 0.4,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
    
    // 礼物统计图
    const giftCtx = document.getElementById('giftChart').getContext('2d');
    charts.gift = new Chart(giftCtx, {
        type: 'bar',
        data: {
            labels: [],
            datasets: [{
                label: '价值(元)',
                data: [],
                backgroundColor: '#8b5cf6',
                borderRadius: 8
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
    
    // 用户类型分布图
    const userTypeCtx = document.getElementById('userTypeChart').getContext('2d');
    charts.userType = new Chart(userTypeCtx, {
        type: 'doughnut',
        data: {
            labels: [],
            datasets: [{
                data: [],
                backgroundColor: [
                    '#6366f1',
                    '#8b5cf6',
                    '#10b981',
                    '#f59e0b',
                    '#ef4444'
                ]
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        }
    });
    
    // 收入统计图
    const revenueCtx = document.getElementById('revenueChart').getContext('2d');
    charts.revenue = new Chart(revenueCtx, {
        type: 'pie',
        data: {
            labels: [],
            datasets: [{
                data: [],
                backgroundColor: [
                    '#6366f1',
                    '#8b5cf6',
                    '#10b981'
                ]
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        }
    });
}

// 更新弹幕时间分布图
function updateDanmakuTimeChart(data) {
    const labels = data.map(item => {
        const date = new Date(item.hour);
        return date.toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit' });
    }).reverse();
    const counts = data.map(item => item.count).reverse();
    
    charts.danmakuTime.data.labels = labels;
    charts.danmakuTime.data.datasets[0].data = counts;
    charts.danmakuTime.update();
}

// 更新礼物统计图
function updateGiftChart(data) {
    const labels = data.map(item => item.gift_name);
    const values = data.map(item => (item.total_coin || 0) / 1000);
    
    charts.gift.data.labels = labels;
    charts.gift.data.datasets[0].data = values;
    charts.gift.update();
}

// 更新用户类型分布图
function updateUserTypeChart(data) {
    const labels = data.map(item => item.type_name);
    const counts = data.map(item => item.count);
    
    charts.userType.data.labels = labels;
    charts.userType.data.datasets[0].data = counts;
    charts.userType.update();
}

// 更新收入统计图
function updateRevenueChart(data) {
    const labels = data.map(item => item.type);
    const values = data.map(item => item.value);
    
    charts.revenue.data.labels = labels;
    charts.revenue.data.datasets[0].data = values;
    charts.revenue.update();
}

// 更新活跃用户表格
function updateActiveUsersTable(data) {
    const tbody = document.querySelector('#activeUsersTable tbody');
    tbody.innerHTML = '';
    
    data.forEach((user, index) => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${index + 1}</td>
            <td>${escapeHtml(user.author_name)}</td>
            <td>${user.count.toLocaleString()}</td>
        `;
        tbody.appendChild(row);
    });
}

// 更新礼物排行表格
function updateGiftRankTable(data) {
    const tbody = document.querySelector('#giftRankTable tbody');
    tbody.innerHTML = '';
    
    data.forEach((gift, index) => {
        const row = document.createElement('tr');
        const value = (gift.total_coin || 0) / 1000;
        row.innerHTML = `
            <td>${index + 1}</td>
            <td>${escapeHtml(gift.gift_name)}</td>
            <td>${gift.total_num.toLocaleString()}</td>
            <td>${value.toFixed(2)}</td>
        `;
        tbody.appendChild(row);
    });
}

// HTML 转义
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

