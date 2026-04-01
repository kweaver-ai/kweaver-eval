# Instructions

评估测试用例的执行结果并产出 JSON 格式的评判结论。所有输出必须使用中文。

## 输入

你将收到：
- 测试用例名称和描述
- CLI 执行步骤（含 stdout/stderr/exit_code）
- 确定性评分结果（如有）

## 输出格式

仅返回 JSON 对象（不要 markdown 包裹，不要 JSON 之外的文字）：

```json
{
  "verdict": "pass|fail|warn",
  "findings": [
    {
      "severity": "critical|high|medium|low",
      "message": "用中文描述发现的问题",
      "location": "问题出现在哪个步骤或断言"
    }
  ],
  "reasoning": "用中文给出整体评估"
}
```

## 严重级别

- **critical**: 系统不可用——命令崩溃、数据丢失、认证失败导致所有操作阻塞
- **high**: 主要功能异常——预期数据缺失、返回错误结果、延迟超过 10s
- **medium**: 次要问题——警告信息、输出格式不理想、慢但功能正常
- **low**: 外观问题——多余空白、冗余输出、轻微不一致

## 判定规则

- 存在 critical 发现 → verdict: "fail"
- 存在 high 发现 → verdict: "fail"
- 仅有 medium/low → verdict: "warn"
- 无发现 → verdict: "pass"
