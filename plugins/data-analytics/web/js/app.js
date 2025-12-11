// 主应用逻辑
let currentRoomId = null;
let currentStartTime = null;
let currentEndTime = null;

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    initCharts();
    setupEventListeners();
});

// 设置事件监听器
function setupEventListeners() {
    const fileInput = document.getElementById('dbFile');
    const selectBtn = document.getElementById('selectFileBtn');
    const roomSelect = document.getElementById('roomSelect');
    const startDate = document.getElementById('startDate');
    const endDate = document.getElementById('endDate');
    const refreshBtn = document.getElementById('refreshBtn');
    const quickButtons = document.querySelectorAll('.btn-quick');
    
    selectBtn.addEventListener('click', () => {
        fileInput.click();
    });
    
    fileInput.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (file) {
            await loadDatabaseFile(file);
        }
    });
    
    roomSelect.addEventListener('change', (e) => {
        currentRoomId = e.target.value ? parseInt(e.target.value) : null;
        refreshData();
    });
    
    startDate.addEventListener('change', () => {
        currentStartTime = startDate.value || null;
        refreshData();
    });
    
    endDate.addEventListener('change', () => {
        currentEndTime = endDate.value || null;
        refreshData();
    });
    
    refreshBtn.addEventListener('click', () => {
        refreshData();
    });
    
    // 快捷按钮
    quickButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const range = btn.dataset.range;
            setTimeRange(range);
        });
    });
}

// 设置时间范围
function setTimeRange(range) {
    const startDate = document.getElementById('startDate');
    const endDate = document.getElementById('endDate');
    const now = new Date();
    
    let start = null;
    let end = null;
    
    switch (range) {
        case 'today':
            start = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0);
            end = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 23, 59, 59);
            break;
        case 'yesterday':
            const yesterday = new Date(now);
            yesterday.setDate(yesterday.getDate() - 1);
            start = new Date(yesterday.getFullYear(), yesterday.getMonth(), yesterday.getDate(), 0, 0, 0);
            end = new Date(yesterday.getFullYear(), yesterday.getMonth(), yesterday.getDate(), 23, 59, 59);
            break;
        case 'last7days':
            start = new Date(now);
            start.setDate(start.getDate() - 7);
            start.setHours(0, 0, 0, 0);
            end = new Date(now);
            end.setHours(23, 59, 59, 999);
            break;
        case 'last30days':
            start = new Date(now);
            start.setDate(start.getDate() - 30);
            start.setHours(0, 0, 0, 0);
            end = new Date(now);
            end.setHours(23, 59, 59, 999);
            break;
        case 'all':
            start = null;
            end = null;
            break;
    }
    
    if (start) {
        startDate.value = formatDateTimeLocal(start);
        currentStartTime = startDate.value;
    } else {
        startDate.value = '';
        currentStartTime = null;
    }
    
    if (end) {
        endDate.value = formatDateTimeLocal(end);
        currentEndTime = endDate.value;
    } else {
        endDate.value = '';
        currentEndTime = null;
    }
    
    refreshData();
}

// 格式化日期时间为 datetime-local 格式
function formatDateTimeLocal(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    return `${year}-${month}-${day}T${hours}:${minutes}`;
}

// 加载数据库文件
async function loadDatabaseFile(file) {
    const loading = document.getElementById('loading');
    const content = document.getElementById('content');
    const fileName = document.getElementById('fileName');
    
    try {
        loading.style.display = 'flex';
        content.style.display = 'none';
        fileName.textContent = '';
        
        // 确保 SQL.js 已初始化
        await initSQL();
        
        await loadDatabase(file);
        fileName.textContent = `已加载: ${file.name}`;
        
        // 加载房间列表
        await loadRooms();
        
        // 刷新数据
        await refreshData();
        
        content.style.display = 'block';
    } catch (error) {
        console.error('加载数据库失败:', error);
        alert('加载数据库失败: ' + error.message);
    } finally {
        loading.style.display = 'none';
    }
}

// 加载房间列表
async function loadRooms() {
    try {
        const rooms = getRooms();
        const roomSelect = document.getElementById('roomSelect');
        
        // 清空现有选项（保留"全部房间"）
        roomSelect.innerHTML = '<option value="">全部房间</option>';
        
        rooms.forEach(room => {
            const option = document.createElement('option');
            option.value = room.room_id;
            option.textContent = `房间 ${room.room_id}`;
            roomSelect.appendChild(option);
        });
        
        // 初始化时间范围
        const timeRange = getDataTimeRange();
        if (timeRange) {
            const startDate = document.getElementById('startDate');
            const endDate = document.getElementById('endDate');
            
            // 设置默认范围为最近7天
            const end = new Date(timeRange.max);
            const start = new Date(end);
            start.setDate(start.getDate() - 7);
            
            startDate.value = formatDateTimeLocal(start);
            endDate.value = formatDateTimeLocal(end);
            
            currentStartTime = startDate.value;
            currentEndTime = endDate.value;
        }
    } catch (error) {
        console.error('加载房间列表失败:', error);
    }
}

// 刷新所有数据
async function refreshData() {
    if (!db) {
        return;
    }
    
    try {
        // 更新统计数据
        updateStatistics();
        
        // 更新图表
        updateCharts();
        
        // 更新表格
        updateTables();
    } catch (error) {
        console.error('刷新数据失败:', error);
        alert('刷新数据失败: ' + error.message);
    }
}

// 更新统计数据
function updateStatistics() {
    const stats = getStatistics(currentRoomId, currentStartTime, currentEndTime);
    
    document.getElementById('statDanmaku').textContent = stats.danmakuCount.toLocaleString();
    document.getElementById('statGift').textContent = stats.giftCount.toLocaleString();
    document.getElementById('statGiftValue').textContent = (stats.giftTotalCoin / 1000).toFixed(2);
    document.getElementById('statMember').textContent = stats.memberCount.toLocaleString();
    document.getElementById('statMemberValue').textContent = (stats.memberTotalCoin / 1000).toFixed(2);
    document.getElementById('statSuperChat').textContent = stats.superChatCount.toLocaleString();
    document.getElementById('statSuperChatValue').textContent = (stats.superChatTotalPrice || 0).toFixed(2);
}

// 更新图表
function updateCharts() {
    // 弹幕时间分布
    const danmakuTimeData = getDanmakuTimeDistribution(currentRoomId, currentStartTime, currentEndTime, 24);
    updateDanmakuTimeChart(danmakuTimeData);
    
    // 礼物统计
    const giftData = getGiftStatistics(currentRoomId, currentStartTime, currentEndTime, 10);
    updateGiftChart(giftData);
    
    // 用户类型分布
    const userTypeData = getUserTypeDistribution(currentRoomId, currentStartTime, currentEndTime);
    updateUserTypeChart(userTypeData);
    
    // 收入统计
    const revenueData = getRevenueByType(currentRoomId, currentStartTime, currentEndTime);
    updateRevenueChart(revenueData);
}

// 更新表格
function updateTables() {
    // 活跃用户排行
    const activeUsers = getActiveUsers(currentRoomId, currentStartTime, currentEndTime, 20);
    updateActiveUsersTable(activeUsers);
    
    // 礼物排行
    const giftRank = getGiftStatistics(currentRoomId, currentStartTime, currentEndTime, 20);
    updateGiftRankTable(giftRank);
}

