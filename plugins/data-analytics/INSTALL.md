# 安装指南

## 快速开始

1. **复制插件目录**
   ```bash
   # 将插件目录复制到blivechat的插件目录
   cp -r data-analytics /path/to/blivechat/data/plugins/
   ```

2. **启用插件**
   - 启动blivechat
   - 打开插件管理页面
   - 找到"数据分析"插件
   - 点击启用

3. **查看数据**
   - 数据会自动保存到 `data/plugins/data-analytics/data/analytics.db`
   - 使用 `python analyze.py` 查看统计数据

## 目录结构

```
data-analytics/
├── plugin.json          # 插件配置文件
├── main.py              # 主程序入口
├── listener.py          # 消息监听器
├── database.py          # 数据库操作
├── config.py            # 配置管理
├── analyze.py           # 数据分析脚本
├── requirements.txt     # 依赖（通常为空，使用项目自带的blcsdk）
├── README.md            # 详细文档
└── INSTALL.md           # 本文件
```

## 注意事项

1. **Python版本**: 需要Python 3.12+
2. **blcsdk依赖**: 插件需要能够导入blcsdk，确保从blivechat项目根目录运行
3. **数据库位置**: 数据库文件位于 `data/plugins/data-analytics/data/analytics.db`
4. **日志位置**: 日志文件位于 `data/plugins/data-analytics/log/data-analytics.log`

## 故障排除

### 问题：无法导入blcsdk

**解决方案1**: 确保从blivechat项目根目录运行blivechat

**解决方案2**: 修改 `plugin.json` 中的运行命令，添加Python路径：
```json
{
  "run": "python -c \"import sys; sys.path.insert(0, '/absolute/path/to/blivechat'); exec(open('main.py').read())\""
}
```

### 问题：数据库文件未创建

- 检查 `data/plugins/data-analytics/data/` 目录是否有写权限
- 查看日志文件 `log/data-analytics.log` 了解错误信息

### 问题：插件无法启动

- 检查Python版本是否符合要求
- 查看blivechat主日志文件
- 确保插件目录结构完整

