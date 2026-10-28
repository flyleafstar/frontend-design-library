# 灵感库前端设计 Skill

让 Codex 根据页面用途，从设计灵感库挑选参考、应用分类提示词，然后直接设计、实现与验证。

支持 **后台、研究报告、产品官网、个人主页**。随包提供 **37 个来源、10 种风格、9 类页面用途**的结构化索引，以及四类中文提示词；筛选只依赖 Python 3 标准库，不需要 API Key。

## 安装

这是公开仓库，安装无需登录 GitHub。安装 Git 后，在 macOS / Linux 或 Windows Git Bash 执行：

```bash
git clone https://github.com/flyleafstar/frontend-design-library.git "${CODEX_HOME:-$HOME/.codex}/skills/frontend-design-library"
```

Windows PowerShell（默认 Codex 目录）：

```powershell
git clone https://github.com/flyleafstar/frontend-design-library.git "$env:USERPROFILE\.codex\skills\frontend-design-library"
```

若已设置 `CODEX_HOME`，使用其下的 `skills/frontend-design-library`。目标目录已存在时先查看现有版本，不要直接覆盖；可下载到另一个目录进行比较。已有本仓库 Git checkout 时可在该目录用 `git pull --ff-only` 更新。

新开聊天刷新技能列表，直接说：

> 我要做前端设计，为当前项目做一个企业后台，重点是搜索、审核与状态。

> 把这份材料做成研究报告网页，风格偏编辑刊物。

也可显式调用 `$frontend-design-library` 并附上需求。技能允许隐式匹配，但已打开的聊天可能需要刷新。

## 工作方式

1. 读取当前项目与要求，识别页面类型、技术栈和保留项。
2. 筛选候选，再实际查看具体页面或用户提供的截图，确定视觉主参考与结构参考。
3. 读取所选类别的完整模板，填入真实内容，沿用项目架构直接实施。
4. 用浏览器检查桌面、手机和关键交互，交付预览与实际验证结果。

`frontend-design` 是可选的下游技能，未安装时仍可工作。候选脚本不会联网，网页查看与实现由 Codex 使用可用工具完成。

## 指定自己的素材库

选择顺序为 **`--library` → `FRONTEND_DESIGN_LIBRARY` 环境变量 → 随包 `references/library/`**。目录必须包含 `catalog.json` 与 `PROMPTS.md`。

```bash
# 在本仓库根目录运行
python3 scripts/select_references.py --type dashboard --style enterprise
python3 scripts/select_references.py --type report --style editorial
python3 scripts/select_references.py --type product --style bento --stack Astro
python3 scripts/select_references.py --type personal --reference site-html5up
python3 scripts/select_references.py --type report --library "/path/to/my-library"

# 可选：当前终端会话使用外部库；图形界面的 Codex 未必继承终端环境变量
export FRONTEND_DESIGN_LIBRARY="/path/to/my-library"
```

Windows 安装 Python 后可将 `python3` 替换为 `py`。也可以直接在聊天里提供外部素材库路径，让 Codex 通过 `--library` 读取。

脚本输出完整模板、候选来源、匹配原因、历史核验记录、技术栈和许可说明。它不会把标签匹配当作已访问源站或已验证代码兼容。

## 文件与维护

- [SKILL.md](SKILL.md)：触发描述与完整流程。
- [候选脚本](scripts/select_references.py)：只读筛选与模板读取。
- [素材索引](references/library/catalog.json)：37 条公共来源及分类、许可线索。
- [分类模板](references/library/PROMPTS.md)：四类模板与迭代反馈方式。
- [测试](tests/test_portability.py)：跨目录运行、路径覆盖、四类读取与异常输入。

随包目录是 **2026-10-24** 核验的首版快照；上传不代表重新核验了全部外部网站。维护时编辑这两个参考文件，核查原始来源后再更新日期。外部素材库每次直接读取，不会被本包覆盖。

本包包含技能、来源索引和提示词；不包含完整灵感库网页、浏览器收藏 / 草稿、其他技能或第三方页面截图。离线设计可使用用户提供的带来源截图。引用的模板、字体、图像与第三方代码仍遵循各自许可。

## 自测

```bash
python3 -m unittest discover -s tests -v
```

本次发布验证的是可迁移打包与脚本；设计流程此前已通过个人主页的浏览器试跑。本次上传没有重新测试全部第三方模板。
