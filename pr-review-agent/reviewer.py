"""
reviewer.py — 独立 Claude Agent 进程进行 Code Review

每个 PR 调用一次 run_code_review()，该函数：
1. 将 PR diff 及元信息组装成 prompt
2. 通过 claude-agent-sdk 的 query() 启动一个独立 Claude Agent 进程
3. 收集 Agent 最终输出并返回 Markdown 格式的 CR 报告
"""

import anyio
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage

from github_client import PullRequest


# -----------------------------------------------------------------------
# 系统提示：定义 Code Reviewer 角色
# -----------------------------------------------------------------------
SYSTEM_PROMPT = """\
你是一位资深工程师，正在对 GitHub Pull Request 进行严谨、专业的代码审查（Code Review）。

**审查维度（按优先级）：**
1. **正确性**：逻辑是否有 bug、边界条件是否处理、错误处理是否完备
2. **安全性**：是否存在注入、越权、敏感信息泄漏等安全风险
3. **性能**：是否存在不必要的 N+1 查询、内存泄漏、低效算法
4. **可维护性**：命名是否清晰、代码是否重复、是否遵循单一职责原则
5. **测试覆盖**：关键路径是否有测试

**输出格式要求：**
- 使用 Markdown，结构清晰
- 每个问题注明文件名和行号（如有）
- 严重性标签：🔴 阻塞（必须修复）/ 🟡 建议（强烈推荐）/ 🟢 优化（可选改进）
- 末尾给出总体评价（LGTM / 需要修改 / 建议重构）

只输出审查报告，不要包含其他解释。
"""


def _build_prompt(pr: PullRequest, diff: str, files: list[dict]) -> str:
    """将 PR 信息拼装成 Claude 能理解的 prompt。"""

    # 文件摘要
    file_summary = "\n".join(
        f"- `{f['filename']}` ({f['status']}, +{f.get('additions', 0)}/-{f.get('deletions', 0)})"
        for f in files[:50]  # 最多列 50 个文件
    )

    # diff 截断（避免超出 context window，保留约 80K 字符）
    MAX_DIFF_CHARS = 80_000
    diff_truncated = diff
    if len(diff) > MAX_DIFF_CHARS:
        diff_truncated = diff[:MAX_DIFF_CHARS] + "\n\n... [diff 过长，已截断] ..."

    return f"""\
## PR 信息

- **标题**：{pr.title}
- **作者**：{pr.author}
- **PR 链接**：{pr.html_url}
- **描述**：
{pr.body or '（无描述）'}

## 变更文件（{len(files)} 个）

{file_summary}

## Diff

```diff
{diff_truncated}
```

请对上述 PR 进行全面的 Code Review，并按照要求的格式输出审查报告。
"""


async def run_code_review(pr: PullRequest, diff: str, files: list[dict]) -> str:
    """
    启动独立 Claude Agent 进程进行 Code Review。

    返回：Markdown 格式的 CR 报告字符串。
    """
    prompt = _build_prompt(pr, diff, files)

    result_text = ""

    try:
        async for message in query(
            prompt=prompt,
            options=ClaudeAgentOptions(
                system_prompt=SYSTEM_PROMPT,
                # Code Review 只需要"思考"，不需要文件操作工具
                allowed_tools=[],
                # 关闭交互式权限提示，纯批处理模式
                permission_mode="bypassPermissions",
                # 限制最大轮次，防止 Agent 死循环
                max_turns=5,
            ),
        ):
            if isinstance(message, ResultMessage):
                result_text = message.result
                break
    except Exception:
        # claude-agent-sdk 在 break 后清理 anyio cancel scope 时会抛出无害异常，忽略即可
        pass

    if not result_text:
        result_text = "⚠️ Code Review Agent 未返回结果，请手动检查。"

    return result_text


def run_code_review_sync(pr: PullRequest, diff: str, files: list[dict]) -> str:
    """
    同步包装器，供测试脚本或不在 async 上下文中调用。
    注意：在已有 event loop 的环境（如 Jupyter）中请直接 await run_code_review()。
    """
    return anyio.run(run_code_review, pr, diff, files)
