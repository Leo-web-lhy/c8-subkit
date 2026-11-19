# subkit — 提交前自查与验收工具包

一个**真实项目**：把我在 2026 年 9–11 月连续 10 次课程挑战提交中踩到的失败，固化成可执行的检查工具。

起因不是"想做个工具"，而是**有 2 个挑战（C5、C4C）被平台退回，且退回原因不给评语**。退回不是靠感觉修的，只能靠把踩过的坑变成机器可查的判据。subkit 就是这份判据清单的代码化。

> 判断标准只有一条：**它能在我下一次提交前，挡住我已经犯过的错。**

---

## 它能挡住什么

六个失败类，每一类都对应一次真实事故，每一类都有回归测试：

| # | 失败类 | 真实事故 | 工具如何判 |
|---|---|---|---|
| 1 | 通配符匹配的是**文件名**，不是文件内容 | C6：README 正文写满了链接，平台仍报 `missing` 四个必交物 | `preflight` 逐条报告命中规则（basename / path），并给出该建的文件名 |
| 2 | 文件存在但**是空壳** | 补一个 0 字节的 `demo.md` 骗过通配符，实质无交付 | `is_stub()` 把零字节和近空文件标为 STUB，不算通过 |
| 3 | `git status` 说"改了"，其实**只是 CRLF** | C5：5 个文件显示 M，实际字节无差异，误判为"远端过期" | 用 git blob id 比对（`sha1("blob N\0"+bytes)`），字节不同才算不同 |
| 4 | 把**树对象 id** 当文件 id 比 | 远端 tree 里混着 tree/blob，比错会产生"每个文件都不一致" | 只取 `type=blob`，且截断的列表直接报错，不当"全都没上传" |
| 5 | 平台调用的**引号与轮询语义** | `@payload` 少写 `@` 就被当 JSON 解析；`list` 滞后导致重复提交 | argv 永远是列表、`@` 前缀由构造保证；轮询只认 `get-task` 终态 |
| 6 | 文档写的**调用方式从来没跑通过** | 本工具 0.1.0 自身：`python -m subkit` 缺 `__main__.py` 每条命令立即崩；`ascii_ok` 被调用 7 次却从未定义 | 交付前把文档里的每条命令**照着跑一遍**，并给 CLI 补契约测试（`tests/test_cli.py`） |

第五条尤其重要：**"列表里没有"不等于"没提交"**。这个工具里 `decide()` 永远不返回 `resubmit`——重复提交是我已经犯过的错。

---

## 安装与运行

无第三方依赖，Python 3.9+ 即可。

```bash
git clone https://github.com/Leo-web-lhy/c8-subkit.git
cd c8-subkit
python -m unittest discover -s tests -v     # 58 项，全部应 OK
```

作为库使用，或直接跑 CLI：

```bash
python -m subkit doctor                          # 环境前置检查
python -m subkit preflight ./my-delivery --required "*proposal*,*AAR_W*,*AI日志*,*拿来说明*"
python -m subkit manifest ./my-delivery --out manifest.json
python -m subkit verify --manifest manifest.json --owner Leo-web-lhy --repo c8-subkit
```

**只用标准库**，是因为它要能在评分环境、我的本机、以及任何一台没有 pip 权限的机器上直接跑。一个依赖装不上的检查工具，等于没有检查工具。

---

## 四个子命令

### `doctor` — 先确认前置条件

检查 Python 版本、Node 运行器、`COGSEED_NODE` / `COGSEED_PC_DIR`、GitHub token，以及 `api.github.com` 是否真的可达。

之所以要有这一步：这台机器上 `git push` 到 `github.com:443` **会超时**，但 `api.github.com` 通。不先测就动手，会浪费半小时在"为什么推送不上去"。

### `preflight` — 挡第 1、2 类

```bash
python -m subkit preflight . --required "*proposal*,*AAR_W*,*AI日志*,*拿来说明*" --detail preflight.txt
```

控制台只打 ASCII 计数与判定（`verdict=READY / NOT_READY`），中文明细写进 `--detail` 指定文件。

为什么分成两路：这台机器上**把中文直接打到 Windows 控制台会让进程 0xC0000005 崩溃**，崩溃发生在落盘之前，连日志都不会有。所以 CLI 里每条输出都过 `emit()`，强制转义成 ASCII。

### `manifest` — 给"字节"留证据

生成 `path / bytes / sha1 / git_blob` 四元组。同时存 `sha1` 和 `git_blob` 是刻意的：**两者是不同的算法**，拿 `sha1` 去比远端 tree 会得到"每个文件都不一样"的假结果。

### `verify` — 挡第 3、4 类，并证明仓库真的公开

用递归 tree 列表拿到 `path -> git blob id`，与本地 manifest 逐条比。输出 `matched / mismatched / missing_on_remote / extra_on_remote`，同时用**匿名请求**验证仓库可公开访问（`public=True` 才算通过）。

匿名检查不能省：自己带 token 能看到，不代表别人能看到。挑战要的是"公开仓库"。

---

## 它怎么被验收的（不是自称，是自证）

这个工具的第一个用户是它自己的交付：

1. 用它 `preflight` 检查本目录 → 四项必交物全部命中
2. 用它 `manifest` 生成字节清单
3. 发布后用它 `verify` 核对远端 → `mismatched=0 / missing=0 / extra=0 / public=True`

也就是说，**交付物本身如果缺件或不是逐字节一致，这个工具会自己报错**。这就是 C8 要的"交付-反馈-迭代闭环"。

---

## 已知边界（不掩饰）

- **只在 Windows + Python 3.12 上实跑过**。代码只用了 `os`/`hashlib`/`urllib`，理论上跨平台，但**没有在 Linux/macOS 上验证**，所以不宣称"跨平台通过"。
- **没有 CI**。本机 GitHub 凭据缺 `workflow` scope，推 `.github/workflows/` 被明确拒绝。仓库里没有 CI 文件，不写"CI 已启用"。
- `verify` 依赖 GitHub REST API 的**匿名速率**（未认证 60 次/小时）。文件数上百时需要 token。
- `is_stub()` 用"非空白字符 < 40"判定空壳，**是启发式**：一份真正只有一行结论的交付会被误判为 STUB。这种情况要人工确认。
- 通配符匹配沿用 `fnmatch`，不做完整 glob 语义（`**` 递归不支持）。

---

## 目录

```
subkit/            # 5 个模块：deliverables / manifest / remote / platform / cli
tests/             # 58 项回归测试，六类故障各自有判据
examples/          # 一个故意做坏的交付样例，用来演示 preflight 如何拦
README.md          # 本文件
proposal.md        # 需求来源、验收标准、范围与非目标
AAR_W.md           # 事后复盘：真实差异与改进项
AI日志.md          # AI 协作记录：多轮迭代与真实失败
拿来说明.md        # 怎么用、为什么这么设计
```

许可：MIT。
