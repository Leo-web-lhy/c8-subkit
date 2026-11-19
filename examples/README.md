# examples — 两个故意做坏的交付

这两个目录是**反面样例**，用来演示 `preflight` 到底拦住什么。它们不应该通过检查。

## broken-demo/

```bash
python -m subkit preflight examples/broken-demo --required "*demo*,*AI日志*"
```

实测输出（Windows / Python 3.12.13，`exit=3`）：

```
patterns=2 found=1 missing=1 stubs=1
  MISSING *AI日志* -> AI日志.md
  STUB *demo* x1
verdict=NOT_READY
```

`*demo*` 显示 `found=1` 是因为空壳被判成 STUB，仍然算不合格——这正是要演示的第 2 类坑。

里面有什么：

| 文件 | 故意犯的错 | 对应失败类 |
|---|---|---|
| `链接写在正文里.md` | 正文里写满了 `demo` 与 `AI日志` 的链接，但文件名不含关键词 | 1：通配符匹配文件名，不匹配内容 |
| `空壳demo.md` | 只有一行空白，能被 `*demo*` 命中但没有内容 | 2：空壳文件不算通过 |

> 这个文件原本叫 `空壳.md`，`*demo*` 根本命中不到它，`stubs` 也就不会触发——反面样例自己先违反了「关键词必须出现在文件名里」这条规则。改名后 `stubs=1` 才真正验到第 2 类判据。

把这个目录改名对照一下：把 `链接写在正文里.md` 改成 `demo.md`，`*demo*` 立刻变成 `found=True`，而正文内容一个字节都没变。

**这就是 C6 第一次提交失败的完整机理。** 当时我把所有链接写进了 README 正文，平台仍报四项 `missing`；补出 `app链接.md`、`repo链接.md` 之后立刻 4/4。

## 为什么不做"正确样例"

正确样例就是这个仓库本身——它同时是工具和它的第一个用户。用 `preflight` 检查仓库根目录，四项必交物全中；发布后 `verify` 报 `mismatched=0`。**如果我自己缺件，工具会当场报 `NOT_READY`。**
