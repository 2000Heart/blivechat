// 数据库操作模块
let db = null;
let SQL = null;
let sqlJsReady = false;

// 初始化 SQL.js
async function initSQL() {
    if (SQL) return SQL;
    
    // 检查全局 initSqlJs 是否已加载
    if (typeof initSqlJs === 'undefined') {
        throw new Error('sql.js 未加载，请检查网络连接或 CDN 是否可用');
    }
    
    SQL = await initSqlJs({
        locateFile: file => `https://cdn.jsdelivr.net/npm/sql.js@1.8.0/dist/${file}`
    });
    
    sqlJsReady = true;
    return SQL;
}

// 加载数据库文件
async function loadDatabase(file) {
    const SQL = await initSQL();
    
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = function(e) {
            try {
                const buffer = e.target.result;
                const database = new SQL.Database(new Uint8Array(buffer));
                db = database;
                resolve(database);
            } catch (error) {
                reject(error);
            }
        };
        reader.onerror = reject;
        reader.readAsArrayBuffer(file);
    });
}

// 执行查询
function query(sql, params = []) {
    if (!db) {
        throw new Error('数据库未加载');
    }
    
    const stmt = db.prepare(sql);
    stmt.bind(params);
    
    const results = [];
    while (stmt.step()) {
        results.push(stmt.getAsObject());
    }
    
    stmt.free();
    return results;
}

// 构建 WHERE 子句和参数（支持房间和时间范围）
function buildWhereClause(roomId = null, startTime = null, endTime = null) {
    const conditions = [];
    const params = [];
    
    if (roomId !== null) {
        conditions.push('room_id = ?');
        params.push(roomId);
    }
    
    if (startTime !== null) {
        conditions.push('timestamp >= ?');
        params.push(Math.floor(new Date(startTime).getTime() / 1000));
    }
    
    if (endTime !== null) {
        conditions.push('timestamp <= ?');
        params.push(Math.floor(new Date(endTime).getTime() / 1000));
    }
    
    const whereClause = conditions.length > 0 ? 'WHERE ' + conditions.join(' AND ') : '';
    return { whereClause, params };
}

// 获取房间列表
function getRooms() {
    return query('SELECT room_id, room_key_type, room_key_value, created_at FROM rooms ORDER BY created_at DESC');
}

// 获取数据的时间范围
function getDataTimeRange(roomId = null) {
    const { whereClause, params } = buildWhereClause(roomId);
    
    // 分别查询各表的时间范围，然后取最小和最大
    const queries = [
        `SELECT MIN(timestamp) as min_time, MAX(timestamp) as max_time FROM danmaku ${whereClause}`,
        `SELECT MIN(timestamp) as min_time, MAX(timestamp) as max_time FROM gifts ${whereClause}`,
        `SELECT MIN(timestamp) as min_time, MAX(timestamp) as max_time FROM members ${whereClause}`,
        `SELECT MIN(timestamp) as min_time, MAX(timestamp) as max_time FROM super_chat ${whereClause}`
    ];
    
    let minTime = null;
    let maxTime = null;
    
    queries.forEach(sql => {
        const result = query(sql, params);
        if (result.length > 0 && result[0].min_time) {
            const min = result[0].min_time;
            const max = result[0].max_time;
            if (minTime === null || min < minTime) {
                minTime = min;
            }
            if (maxTime === null || max > maxTime) {
                maxTime = max;
            }
        }
    });
    
    if (minTime !== null && maxTime !== null) {
        return {
            min: minTime * 1000,
            max: maxTime * 1000
        };
    }
    return null;
}

// 获取统计数据
function getStatistics(roomId = null, startTime = null, endTime = null) {
    const { whereClause, params } = buildWhereClause(roomId, startTime, endTime);
    
    const stats = {};
    
    // 弹幕统计
    const danmakuResult = query(
        `SELECT COUNT(*) as count FROM danmaku ${whereClause}`,
        params
    );
    stats.danmakuCount = danmakuResult[0]?.count || 0;
    
    // 礼物统计
    const giftResult = query(
        `SELECT COUNT(*) as count, SUM(total_coin) as total_coin, SUM(total_free_coin) as total_free_coin FROM gifts ${whereClause}`,
        params
    );
    stats.giftCount = giftResult[0]?.count || 0;
    stats.giftTotalCoin = giftResult[0]?.total_coin || 0;
    stats.giftTotalFreeCoin = giftResult[0]?.total_free_coin || 0;
    
    // 上舰统计
    const memberResult = query(
        `SELECT COUNT(*) as count, SUM(total_coin) as total_coin FROM members ${whereClause}`,
        params
    );
    stats.memberCount = memberResult[0]?.count || 0;
    stats.memberTotalCoin = memberResult[0]?.total_coin || 0;
    
    // 醒目留言统计
    const scResult = query(
        `SELECT COUNT(*) as count, SUM(price) as total_price FROM super_chat ${whereClause}`,
        params
    );
    stats.superChatCount = scResult[0]?.count || 0;
    stats.superChatTotalPrice = scResult[0]?.total_price || 0;
    
    return stats;
}

// 获取弹幕时间分布
function getDanmakuTimeDistribution(roomId = null, startTime = null, endTime = null, hours = 24) {
    const { whereClause, params } = buildWhereClause(roomId, startTime, endTime);
    
    // 如果有时间范围，不使用 LIMIT，而是按时间范围分组
    if (startTime && endTime) {
        return query(`
            SELECT 
                strftime('%Y-%m-%d %H:00:00', datetime(timestamp, 'unixepoch')) as hour,
                COUNT(*) as count
            FROM danmaku
            ${whereClause}
            GROUP BY hour
            ORDER BY hour ASC
        `, params);
    }
    
    return query(`
        SELECT 
            strftime('%Y-%m-%d %H:00:00', datetime(timestamp, 'unixepoch')) as hour,
            COUNT(*) as count
        FROM danmaku
        ${whereClause}
        GROUP BY hour
        ORDER BY hour DESC
        LIMIT ?
    `, [...params, hours]);
}

// 获取礼物统计
function getGiftStatistics(roomId = null, startTime = null, endTime = null, limit = 10) {
    const { whereClause, params } = buildWhereClause(roomId, startTime, endTime);
    
    return query(`
        SELECT 
            gift_name,
            SUM(num) as total_num,
            SUM(total_coin) as total_coin
        FROM gifts
        ${whereClause}
        GROUP BY gift_name
        ORDER BY total_coin DESC
        LIMIT ?
    `, [...params, limit]);
}

// 获取用户类型分布
function getUserTypeDistribution(roomId = null, startTime = null, endTime = null) {
    const { whereClause, params } = buildWhereClause(roomId, startTime, endTime);
    
    return query(`
        SELECT 
            CASE author_type
                WHEN 0 THEN '普通用户'
                WHEN 1 THEN '舰队'
                WHEN 2 THEN '房管'
                WHEN 3 THEN '主播'
                ELSE '未知'
            END as type_name,
            author_type,
            COUNT(*) as count
        FROM danmaku
        ${whereClause}
        GROUP BY author_type
        ORDER BY count DESC
    `, params);
}

// 获取活跃用户排行
function getActiveUsers(roomId = null, startTime = null, endTime = null, limit = 20) {
    const { whereClause, params } = buildWhereClause(roomId, startTime, endTime);
    
    return query(`
        SELECT 
            author_name,
            COUNT(*) as count
        FROM danmaku
        ${whereClause}
        GROUP BY uid, author_name
        ORDER BY count DESC
        LIMIT ?
    `, [...params, limit]);
}

// 获取收入统计（按类型）
function getRevenueByType(roomId = null, startTime = null, endTime = null) {
    const { whereClause, params } = buildWhereClause(roomId, startTime, endTime);
    
    const results = [];
    
    // 礼物收入
    const giftRevenue = query(
        `SELECT SUM(total_coin) as total FROM gifts ${whereClause}`,
        params
    );
    if (giftRevenue[0]?.total) {
        results.push({
            type: '礼物',
            value: giftRevenue[0].total / 1000
        });
    }
    
    // 上舰收入
    const memberRevenue = query(
        `SELECT SUM(total_coin) as total FROM members ${whereClause}`,
        params
    );
    if (memberRevenue[0]?.total) {
        results.push({
            type: '上舰',
            value: memberRevenue[0].total / 1000
        });
    }
    
    // 醒目留言收入
    const scRevenue = query(
        `SELECT SUM(price) as total FROM super_chat ${whereClause}`,
        params
    );
    if (scRevenue[0]?.total) {
        results.push({
            type: '醒目留言',
            value: scRevenue[0].total
        });
    }
    
    return results;
}

