# 打包说明

## 打包为 exe 文件

### 前置要求

1. **操作系统**: 建议在 Windows 系统上打包，因为 exe 文件是 Windows 专用的
   - 在 macOS/Linux 上无法直接打包 Windows exe 文件
   - 如果必须在 macOS/Linux 上打包，需要使用 Wine 或虚拟机

2. 安装 PyInstaller:
   ```bash
   pip install pyinstaller
   ```
   或者
   ```bash
   python3 -m pip install pyinstaller
   ```

3. 确保在 blivechat 项目根目录下运行打包命令

### macOS/Linux 用户注意事项

如果你在 macOS 或 Linux 系统上：
- **无法直接打包 Windows exe**: PyInstaller 只能打包当前操作系统的可执行文件
- **替代方案**:
  1. 使用 Windows 虚拟机或 Wine 环境打包
  2. 直接使用 Python 脚本运行（修改 `plugin.json` 中的 `run` 为 `"python -u main.py"`）
  3. 在 Windows 系统上打包后分发

### 打包步骤

1. **进入插件目录**
   ```bash
   cd plugins/data-analytics
   ```

2. **运行 PyInstaller**
   
   在 Windows 上:
   ```bash
   pyinstaller data-analytics.spec
   ```
   
   或者使用 Python 模块方式:
   ```bash
   python -m PyInstaller data-analytics.spec
   ```
   
   如果 `pyinstaller` 命令找不到，使用:
   ```bash
   python3 -m PyInstaller data-analytics.spec
   ```

3. **打包结果**
   - exe 文件位于: `dist/data-analytics/data-analytics.exe`
   - 打包后的目录: `dist/data-analytics/`
   - 压缩包: `dist/data-analytics.zip`

### 使用打包后的文件

1. **方法一：使用压缩包**
   - 解压 `data-analytics.zip` 到 `data/plugins/data-analytics/`
   - 确保目录结构如下：
     ```
     data/plugins/data-analytics/
     ├── data-analytics.exe
     ├── plugin.json
     ├── log/
     └── data/
     ```

2. **方法二：直接复制目录**
   - 将 `dist/data-analytics/` 目录复制到 `data/plugins/data-analytics/`

### 注意事项

- 打包后的 exe 文件需要和 `plugin.json` 在同一目录
- `log/` 和 `data/` 目录会自动创建，但建议在打包时包含 `.gitkeep` 文件
- 确保 blivechat 项目在打包时可以被找到（通过 PYTHONPATH 设置）
- 打包后的 exe 文件较大（通常几十MB），因为包含了 Python 解释器和所有依赖

### 验证打包

打包完成后，可以手动运行 exe 文件测试：

```bash
cd dist/data-analytics
./data-analytics.exe
```

如果出现错误，检查：
1. 是否正确包含了所有依赖
2. blcsdk 模块是否正确打包
3. 数据文件（plugin.json）是否正确包含

### 常见问题

**Q: 在 macOS/Linux 上无法打包 Windows exe**
A: PyInstaller 只能打包当前操作系统的可执行文件。如果需要 Windows exe，请在 Windows 系统上打包，或使用虚拟机/Wine。

**Q: 提示 "Python was built without a shared library"**
A: 这通常发生在 macOS 上。解决方案：
- 使用 Homebrew 安装的 Python: `brew install python`
- 或使用 conda 环境: `conda install python`
- 或直接在 Windows 系统上打包

**Q: 打包后无法找到 blcsdk 模块**
A: 确保在 blivechat 项目根目录下运行打包命令，PYTHONPATH 会指向项目根目录

**Q: 打包后的 exe 文件很大**
A: 这是正常的，PyInstaller 会打包 Python 解释器和所有依赖。可以使用 `--onefile` 选项创建单文件版本，但启动会稍慢。

**Q: 打包后无法创建数据库文件**
A: 确保 `data/` 目录有写权限，或者检查 exe 文件是否在正确的目录下运行

**Q: 不想打包，直接使用 Python 脚本可以吗？**
A: 可以！修改 `plugin.json` 中的 `run` 字段为 `"run": "python -u main.py"`，然后确保从 blivechat 项目根目录运行即可。

