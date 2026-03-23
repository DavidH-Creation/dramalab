# ScriptSmith 改动需求：聚焦剧本改编 + 修复优化分布不均

> 交付日期：2026-03-23
> 优先级：高——当前版本跑出来的结果剧本组不可用

---

## 一、背景

我们用 ScriptSmith 跑了一轮剧本优化。剧本组拿到 improved.docx 后的反馈是：

> "感觉新版更偏向给导演的分镜剧本，剧情好像没有变化。"

具体来说：
- 前 14 集被大量添加了 `【竖屏特写·核心视觉符号建立】` `【色彩语法】` 之类的导演执行标注
- 实际剧情（情节、冲突、人物弧光、对白）几乎没动
- 后半段（15 集以后）连导演标注都没加上，基本还是旧稿

这说明当前版本有两个 bug 级的问题需要修。

---

## 二、问题 1：LLM 在加导演包装，不是在改剧本

### 现象

每次 modify 循环，LLM 选择最容易拿分的路径——给文本加镜头语言标签（如 `【仰拍】【慢动作】【冷蓝色调】`），而不是真正修改剧情内容。因为加标签成本低、评分容易涨。

### 根因

1. **modify prompt 没有划界**：`modify_micro.md` 和 `modify_macro.md` 只说"你是短剧改稿主编"，没有明确禁止添加导演层内容。LLM 自然会走阻力最小的路径。
2. **scoring prompt 没有校准**：`score_micro.md` 和 `score_macro.md` 没有告诉评分模型"加了镜头标注不等于场景视听分该涨"，导致评分模型也在奖励这种行为。

### 要改什么

#### 2.1 `packages/scriptsmith/src/scriptsmith/prompts/modify_micro.md`

在"修改规则"部分（现有 4 条规则之后）追加第 5 条：

```
- ⚠️ 你是编剧，不是导演。禁止添加任何镜头语言（景别、特写、仰拍、慢动作）、
  视觉标注（【竖屏特写】【色彩语法】【视觉符号建立】等）、或导演执行指示。
  你的任务是改善故事本身——情节、冲突、人物动机、对白质量、节奏钩子。
  如果原文已有导演标注，保留不动，但绝不新增。
```

#### 2.2 `packages/scriptsmith/src/scriptsmith/prompts/modify_macro.md`

在"修改规则"部分（现有 3 条规则之后）追加同一条：

```
- ⚠️ 你是编剧，不是导演。禁止添加任何镜头语言（景别、特写、仰拍、慢动作）、
  视觉标注（【竖屏特写】【色彩语法】【视觉符号建立】等）、或导演执行指示。
  你的任务是改善故事本身——情节、冲突、人物动机、对白质量、节奏钩子。
  如果原文已有导演标注，保留不动，但绝不新增。
```

#### 2.3 `packages/scriptsmith/src/scriptsmith/prompts/score_micro.md`

在文件末尾"注意"部分（现有 3 条之后）追加：

```
- 「场景与视听可视化」评的是故事层面的视觉潜力：场景是否集中可控、动作是否有画面感、
  空间和道具是否有记忆点。不是评"是否写了镜头语言或景别指示"——那是导演分镜阶段的事。
  添加镜头标注（如【特写】【仰拍】【色彩语法】）不应提升任何维度的分数。
  评分只看故事内容本身的质量。
```

#### 2.4 `packages/scriptsmith/src/scriptsmith/prompts/score_macro.md`

在文件末尾"注意"部分追加同一段文字。

---

## 三、问题 2：优化力度前重后轻

### 现象

前面的序列（phase1、phase2a）被反复优化了很多轮，后面的序列几乎没轮到就结束了。

### 根因

`loop.py` 里有三处序列选择逻辑，全部是"按顺序从头选"，没有考虑哪个序列分数最低：

| 位置 | 当前逻辑 | 问题 |
|------|----------|------|
| `_run_macro_round` ~line 290 | `target_seq = sequences[0]`，然后找第一个未完成的 | macro 模式永远先改前面的序列 |
| `_run_micro_round` ~line 244 | stall 后遍历找第一个未完成的 `next_seq` | micro stall 后跳到下一个而非最弱的 |
| `run_loop` ~line 123 | auto 进入 micro_sweep 时 `state.current_sequence = sequences[0].id` | micro sweep 永远从第一个序列开始 |

### 要改什么

三处逻辑统一改成**"选 baseline 分数最低的未完成序列"**。

#### 3.1 建议先抽一个辅助函数（可放在 `loop.py` 顶部）

```python
def _pick_weakest_sequence(
    sequences: list,
    completed: list[str],
    baseline_scores: dict[str, dict],
) -> object | None:
    """从未完成序列中选 baseline 总分最低的。无 baseline 记录的序列优先选中。"""
    candidates = [s for s in sequences if s.id not in completed]
    if not candidates:
        return None

    def sort_key(seq):
        if seq.id in baseline_scores:
            return ScoreResult.from_dict(baseline_scores[seq.id]).total
        return -1  # 没有 baseline 的优先（分数视为最低）

    candidates.sort(key=sort_key)
    return candidates[0]
```

#### 3.2 `_run_macro_round` 改用该函数

将 ~line 288-294 的：

```python
target_seq = sequences[0]  # Simple heuristic for v1
for seq in sequences:
    if seq.id not in state.sequences_completed:
        target_seq = seq
        break
```

替换为：

```python
target_seq = _pick_weakest_sequence(sequences, state.sequences_completed, state.baseline_scores)
if target_seq is None:
    target_seq = sequences[0]  # fallback: all completed
```

#### 3.3 `_run_micro_round` stall 跳转改用该函数

将 ~line 244-249 的：

```python
next_seq = None
for seq in sequences:
    if seq.id not in state.sequences_completed:
        next_seq = seq
        break
```

替换为：

```python
next_seq = _pick_weakest_sequence(sequences, state.sequences_completed, state.baseline_scores)
```

#### 3.4 auto 模式 micro_sweep 入口改用该函数

将 ~line 123-124 的：

```python
if sequences:
    state.current_sequence = sequences[0].id
```

替换为：

```python
weakest = _pick_weakest_sequence(sequences, state.sequences_completed, state.baseline_scores)
if weakest is not None:
    state.current_sequence = weakest.id
elif sequences:
    state.current_sequence = sequences[0].id
```

---

## 四、改动总览

| 文件 | 改什么 | 改动量 |
|------|--------|--------|
| `prompts/modify_micro.md` | 追加编剧边界约束 | +4 行 |
| `prompts/modify_macro.md` | 追加编剧边界约束 | +4 行 |
| `prompts/score_micro.md` | 追加评分校准说明 | +4 行 |
| `prompts/score_macro.md` | 追加评分校准说明 | +4 行 |
| `loop.py` | 新增 `_pick_weakest_sequence` 函数 + 替换 3 处调用 | +15 行，-12 行 |

**不涉及**：新文件、新依赖、新 CLI 命令、数据模型变更、criteria.md 修改。

---

## 五、验证方法

### 5.1 自动化验证

```bash
# 确认现有测试不 break
cd packages/scriptsmith && python -m pytest

# 确认 prompt 文件语法正常（占位符能正确替换）
python -c "from scriptsmith.prompts import load_prompt; print('OK')"
```

### 5.2 评分校准验证

用 `scriptsmith score` 对同一段文本做 A/B：
- A 版：纯剧情文本
- B 版：同样的剧情 + 大量 `【竖屏特写】【色彩语法】` 标签

预期：A 和 B 的"场景与视听可视化"分数不应有显著差异。如果 B 明显高于 A，说明评分校准没生效。

### 5.3 序列选择验证

写一个简单的单元测试：mock 三个序列的 baseline scores（seq_001=45, seq_002=30, seq_003=40），调用 `_pick_weakest_sequence`，断言返回 seq_002。

### 5.4 端到端验证

```bash
scriptsmith run --mode micro --rounds 3
```

检查点：
1. 修改内容是否聚焦剧情（情节变化、对白改写、冲突升级），而不是加镜头标签
2. 如果有多个序列，是否优先修改分数最低的那个

---

## 六、风险与注意事项

1. **不要改 `criteria.md`**——那是只读评分标准，来自公司评估办法。我们只在 prompt 层面引导 LLM 正确理解它。
2. **`_pick_weakest_sequence` 依赖 `baseline_scores`**——如果某个序列还没有 baseline（比如刚 init 还没跑过 score），函数会优先选它（视为最低分）。这是正确行为：没评过分的序列应该先评。
3. **改完后需要 `--fresh` 重跑**——旧的 state.json 里的 baseline_scores 是用旧 prompt 评出来的，新 prompt 的评分标准不同。建议改完后用 `scriptsmith run --fresh` 重新建立 baseline。
