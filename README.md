> **⚠️ 项目公告**
> 
> 本项目由于早期仓促创建，存在功能缺陷、Bug、使用期间卡顿等问题。目前正在全面重制中，重制版本将迁移至新仓库 **[lol-bp-rebuilt](https://github.com/alijacintleishah-spec/lol-bp-rebuilt)**。
> 
> 重制版当前仍在开发中，尚未发布可用版本。如需继续使用 v1.x，仍可下载下方 Release，但请留意已知问题。
> 
> —— 2026-05-08

# LoL BP Assistant v1.1 [已停止维护]

LoL 排位赛实时 BP 辅助工具 — 自动读取 LCU 数据，综合协同 + 克制给出最优英雄推荐。

## 快速开始（用户）

### 下载使用
从 [GitHub Releases](https://github.com/your-username/lol-bp-assistant/releases) 下载最新 `LoL_BP_Assistant_vX.X.X.exe`，双击运行即可。

### 从源码运行
```bash
pip install -r requirements.txt
python desktop_app.py     # 桌面窗口（推荐）
python app.py             # 浏览器模式 http://localhost:5000
```

## 功能

- **自动模式**：进入英雄选择界面后自动读取 BP 数据，实时推荐
- **手动模式**：无需客户端，手动输入双方 B/P，推荐同样有效
- **推荐维度**：版本强度、位置匹配、阵容协同、对位克制、被克制惩罚、ban率、队友熟练度
- **克制专区**：绿色高亮强力克制敌方阵容的英雄
- **BP 计时器**：显示当前阶段剩余时间
- **位置筛选**：按上单/打野/中单/下路/辅助过滤
- **数据实时更新**：从 OP.GG MCP 自动获取最新胜率/tier

## 配置

首次运行自动生成 `config.ini`，可自定义：
- 服务器端口、LCU 轮询间隔
- API 端点、缓存时长
- 日志级别、更新检查频率
- GitHub 仓库（填入后启用自动更新）

## 日志

日志文件在 `logs/lol-bp.log`，自动轮转（5MB×3）。遇到问题时请附带日志反馈。

## 开发

```bash
pip install -e .
# or
pip install -r requirements.txt
python app.py
```

项目结构：
```
app.py               Flask 路由 + 启动入口
champion_data.py     英雄数据（Data Dragon + 内置meta）
meta_fetcher.py      OP.GG 实时数据获取
engine.py            推荐评分引擎
lcu.py               LCU 客户端连接
updater.py           GitHub 自动更新检查
config.py            配置管理
logging_config.py    日志系统
version.py           版本号
data/                缓存数据文件
templates/           前端 UI
```

## 注意事项

- 工具仅读取数据，不操作游戏，不违反 Riot 服务条款
- Python 3.9+，支持 Windows / macOS / Linux
- 手动模式无需 LoL 客户端
