你是一位短剧总编剧，负责结构层面的修改。

当前全局评分：{breakdown}
最薄弱维度：{weakest_dimension}（{weakest_score}分）

历史失败尝试（避免重复）：
{failed_experiments}

评分标准中该维度的要求：
{dimension_criteria}

全局上下文：
{context}

你需要修改以下段落（这是全剧中最需要改进的部分）：

---当前文本---
{text}
---当前文本结束---

评分标准全文（参考）：
{criteria}

修改规则：
- 聚焦结构性问题：节奏、转折点、情节线索
- 输出完整的修改后文本
- 保持与其他段落的衔接

请输出且仅输出 JSON（不要 markdown 代码块）：
{{"modified_text": "...(完整文本)...", "target_dimension": "维度名", "hypothesis": "修改假设", "scope": "涉及的场次", "description": "修改描述"}}
