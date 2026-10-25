# claude-rules-lint

检查分层 `CLAUDE.md` 规则集的**结构**。

[English](README.md) | **简体中文**

一旦你把指令拆到 `CLAUDE.md` 和 `.claude/rules/*.md` 里，三类失败就变得可能，而**它们全都是静默的**——没有任何东西报错，Claude 只是不再读那条你以为它已经掌握的规则：

- 某个规则文件没有任何 `CLAUDE.md` 索引，agent 根本不知道它存在
- 引用了已被改名或删除的规则文件
- `paths:` frontmatter 写了但为空，条件加载永远不触发

这个插件抓这三类问题，盯着 200 行的遵守预算，并报告 `paths:` 覆盖率——但不对它下判断。

## 安装

```bash
/plugin marketplace add mi4646/claude-rules-lint
/plugin install claude-rules-lint@claude-rules-lint
```

## 使用

让 Claude「lint 一下 CLAUDE.md 规则」，或直接运行：

```bash
python3 ~/.claude/plugins/*/claude-rules-lint/*/scripts/check-rules.py . --all
```

```bash
check-rules.py                 # 检查当前目录
check-rules.py <dir> [<dir>..] # 检查指定项目
check-rules.py --all           # 同时检查 ~/.claude（全局层）
check-rules.py --quiet         # 只报 FAIL
```

退出码 `0` = 干净，`1` = 至少一个 FAIL，`2` = 用法错误。

## 检查什么

| 级别 | 发现 |
|---|---|
| FAIL | 规则文件没被主 `CLAUDE.md` 引用 |
| FAIL | 主文件引用了不存在的 `rules/<x>.md` |
| FAIL | `paths:` 存在但没列任何模式 |
| FAIL | 有 `.claude/rules/` 却没有 `CLAUDE.md` 来索引它 |
| WARN | 主 `CLAUDE.md` 超过 200 行 |
| INFO | 每条规则的 `paths:` 覆盖率及它触及的顶层目录 |

## 自动 hook

`hooks/hooks.json` 注册了一个 `PostToolUse` hook，匹配 `Write|Edit|MultiEdit`。当编辑落到某个 `CLAUDE.md` 或 `.claude/rules/*.md` 上时，它检查那个项目，并**只在有问题时**通过退出码 2 把结果呈现给 Claude——这是 `PostToolUse` hook 在工具已经执行完之后唯一能发声的方式。

编辑任何其他文件零成本：hook 解析路径后退出 0，保持静默。一个每次编辑都说话的 hook 会把你训练成无视它。

想关掉它，删掉 `hooks/hooks.json`（或不装插件，只拷 `scripts/`）。

## 覆盖率只报告，不评判

一条规则覆盖仓库 50% 并不自动等于错了。一条前端规则掌管 `web/` 和 `app/`、同时正确排除了 `src/`，覆盖率可以过半而完全正确。

关键在于这个模式**区分不区分项目**。拿同一条规则去两个不同项目测量：这边 29%、那边 0%，说明它精准。如果**每个**项目都过半，那它就是伪装成条件加载的常驻规则，应该去掉 `paths:`——但这个判断需要人来做，所以工具只打印数字和覆盖的目录，然后就停。

## 抓不到什么

文字质量。含糊的规则、互相矛盾的规则、重复的指引、过时的规则——工具对这一切都是瞎的。这些靠 review 把关；`skills/rules-lint/references/layering.md` 记录了能预防其中大部分问题的归位规则。

## 设计说明

- **零依赖。** `check-rules.py` 只用标准库，Python 3.9+。
- **先证明会失败。** 每个 FAIL 分支在发布前都对着一个故意写坏的规则集跑过；第一次运行就是绿的闸门什么都没证明。
- **默认静默。** 没有输出就是没有问题。

## 开发

```bash
python3 -m unittest discover -s tests -v
```

33 项标准库测试，无需安装步骤。覆盖 glob 转换、`paths:` 解析、全部四类 FAIL、WARN/INFO 的划分、命令行参数、hook 的每个分支，以及插件 manifest。

这套测试立刻证明了自己的价值：它抓到一个悬空的 `rules/<x>.md` 引用在项目没有 `.claude/rules/` 目录时被跳过——那个引用检查当时位于一处提前返回之后，于是它存在的唯一意义（目录被删或改名）恰好成了它漏掉的情况。对着修复前的代码跑，会有三项测试失败。

CI 在 Python 3.9 和 3.13（Linux）以及 3.13（Windows）上跑这套测试，外加一项自检——确认检查器仍然会拒绝一个已知坏掉的规则集——以及一道闸门，保证 `plugin.json`、`marketplace.json`、hook matcher 和 `CHANGELOG.md` 保持同步。

## 许可证

MIT —— 版本历史见 [CHANGELOG.md](CHANGELOG.md)。
