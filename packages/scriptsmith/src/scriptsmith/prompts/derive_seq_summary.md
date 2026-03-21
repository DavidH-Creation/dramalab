请为以下剧本段落生成结构化摘要。

段落 ID：{seq_id}

---文本---
{text}
---文本结束---

输出且仅输出 JSON（不要 markdown 代码块）：
{{"scenes": ["场景1简述", "场景2简述", ...], "characters": ["角色1", "角色2", ...], "arc_position": "起/承/转/合", "key_events": ["事件1", "事件2", ...], "transitions": {{"from_previous": "衔接方式", "to_next": "悬念/过渡"}}}}
