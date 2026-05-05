# Changelog

## [1.1.0] — 2026-05-05

### Added
- 原生 tkinter 桌面 UI (`native_ui.py`)，零浏览器依赖
- Canvas 渲染卡片列表，widget 数从 ~600 降至 ~50
- 异步头像加载：后台线程下载 + 磁盘缓存 + 占位圆秒显
- 自定义应用图标 (`BP.ico`)，exe 和窗口标题栏均显示
- 头像图片缓存目录 `data/img_cache/`

### Changed
- `desktop_app.py`：不再启动 Chrome，改为打开 tkinter 原生窗口
- UI 配色全面改为紫-蓝-青绿色系
- Scrollbar 自定义 ttk 样式（窄条深槽）
- 仅重建当前可见 tab，切换 tab 时按需渲染
- 计时器独立 1s 刷新，数据轮询 2s 间隔

### Fixed
- 终端窗口反复闪烁（`subprocess` 添加 `CREATE_NO_WINDOW`）
- UI 卡顿（状态指纹跳过 + Canvas 替代 Frame 嵌套 + 只重建可见 tab）

## [2.1.0] — 2026-05-03

### Added
- 项目打包基础设施：`requirements.txt`, `pyproject.toml`, `__init__.py`
- 版本管理系统：`version.py` 统一版本源，UI 和终端显示版本号
- 配置系统：`config.py` + 自动生成 `config.ini`，所有硬编码值可配置
- 日志系统：`logging_config.py`，文件轮转 + 控制台双输出
- 自动更新检查：`updater.py`，后台定时检查 GitHub Releases
- 更新通知 UI：顶部显示新版本下载条
- 优雅关闭：SIGINT/SIGTERM 信号处理
- 归档 `ai-draft-assistant` 项目

### Changed
- `app.py`: 所有 `print()` 替换为 `logging`，硬编码值改为从 config 读取
- `champion_data.py`: 同上
- `meta_fetcher.py`: 同上
- `desktop_app.py`: 使用 config 获取 host/port，添加日志
- `build_exe.py`: 读取 version.py 生成版本化 exe 文件名
- `启动工具.bat`: 改用 `pip install -r requirements.txt`
- `README.md`: 重写，增加配置/日志/开发章节

## [2.0.0] — 2026-05-02

### Added
- 从 Data Dragon 16.9.1 拉取 172 英雄数据
- 集成 OP.GG MCP API 获取实时胜率/pick率/ban率/tier
- 版本变化自动触发数据更新，缓存 24 小时
- champion_archetypes.json（172英雄 → 30种原型标签）
- 原型间协同规则（25条）/ 冲突规则（5条）
- 标签克制矩阵 TAG_COUNTER_MATRIX（19条标签配对）
- 38 热门英雄精确协同/克制关系
- 7 维度评分推荐引擎
- 原型驱动协同计算，覆盖全部 172 英雄
- 标签 + 原型双通道克制检测
- 双向冲突处理
- 阵容平衡：重复角色扣分 / 填补空位加分
- 分路加权克制（对位×1.5 / 打野×0.7-0.9 / 远端×0.3-0.4）
- 队友熟练度集成（LCU 熟练度 + championPickIntent）
- 暗色 LoL 主题前端 UI
- 英雄头像显示（Data Dragon CDN）
- 推荐/全部英雄双标签页
- 克制专区（绿色高亮，箭头指示）
- 位置筛选、评分进度条
- 手动模式（搜索→选中→添加B/P）
- BP 计时器
- psutil 进程检测 + lockfile 多路径搜索
- WeGame / 国服路径支持
- flaskwebgui 桌面窗口模式
- PyInstaller 打包脚本
