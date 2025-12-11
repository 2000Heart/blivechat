# 数据分析可视化 Web 界面

这是一个静态 Web 应用，用于可视化 `data-analytics` 插件生成的 SQLite 数据库数据。

## 功能特性

- 📊 **数据概览**: 显示弹幕、礼物、上舰、醒目留言的总体统计
- 📈 **时间分布**: 弹幕数量随时间的变化趋势
- 🎁 **礼物分析**: 礼物类型统计和排行
- 👥 **用户分析**: 用户类型分布和活跃用户排行
- 💰 **收入统计**: 按类型统计的收入分布
- 📋 **排行榜**: 活跃用户和礼物排行表格

## 使用方法

### 方法一：直接在浏览器中打开

1. 打开 `index.html` 文件（双击或在浏览器中打开）
2. 点击"选择数据库文件"按钮
3. 选择插件生成的数据库文件（通常位于 `data/analytics.db`）
4. 等待数据加载完成
5. 可以选择特定房间进行查看，或查看全部房间的汇总数据

### 方法二：使用本地服务器（推荐）

由于浏览器的安全限制，建议使用本地服务器运行：

#### Python 3

```bash
cd plugins/data-analytics/web
python -m http.server 8000
```

然后在浏览器中访问：`http://localhost:8000`

#### Node.js

```bash
cd plugins/data-analytics/web
npx http-server -p 8000
```

#### PHP

```bash
cd plugins/data-analytics/web
php -S localhost:8000
```

## 数据库文件位置

插件生成的数据库文件通常位于：

- Windows: `data/plugins/data-analytics/data/analytics.db`
- 插件目录: `plugins/data-analytics/data/analytics.db`

## 技术说明

- **前端框架**: 纯 HTML/CSS/JavaScript，无需构建
- **数据库**: 使用 [sql.js](https://sql.js.org/) 在浏览器中直接读取 SQLite 数据库
- **图表库**: 使用 [Chart.js](https://www.chartjs.org/) 进行数据可视化
- **完全静态**: 不需要后端服务器，所有数据处理都在浏览器中完成

## 浏览器兼容性

- Chrome/Edge (推荐)
- Firefox
- Safari
- 需要支持 WebAssembly（现代浏览器都支持）

## 注意事项

1. **文件大小限制**: 如果数据库文件很大（>100MB），加载可能会较慢
2. **内存占用**: 数据库文件会完全加载到浏览器内存中，大文件可能占用较多内存
3. **数据安全**: 所有数据处理都在本地浏览器中完成，不会上传到任何服务器

## 故障排除

### 无法加载数据库文件

- 确保数据库文件路径正确
- 检查浏览器控制台是否有错误信息
- 尝试使用本地服务器而不是直接打开文件

### 图表不显示

- 检查浏览器控制台是否有 JavaScript 错误
- 确保网络连接正常（需要加载 CDN 资源）
- 尝试刷新页面

### 数据不更新

- 点击"刷新数据"按钮
- 确保数据库文件是最新的
- 检查选择的房间是否正确

## 开发说明

如果需要修改或扩展功能：

- `index.html`: 主页面结构
- `css/style.css`: 样式文件
- `js/db.js`: 数据库操作和查询
- `js/charts.js`: 图表初始化和更新
- `js/app.js`: 主应用逻辑

## 许可证

与主插件保持一致。

