"""
run_review.py — GitHub Actions 调用的 CLI 入口

GitHub Actions 通过环境变量传入 PR 信息，本脚本：
1. 从环境变量读取 PR number、head_sha、title、author 等
2. 调用 Claude Agent 进行 Code Review
3. 将结果 POST 为 PR Comment

用法（由 Actions workflow 自动调用）：
  python run_review.py
"""

import asyncio
import logging
import os
import sys
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("run-review")


async def main() -> None:
    # -----------------------------------------------------------------------
    # 从环境变量读取 PR 信息（由 Actions workflow 注入）
    # -----------------------------------------------------------------------
    github_token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")           # owner/repo
    pr_number = os.environ.get("PR_NUMBER")
    head_sha = os.environ.get("PR_HEAD_SHA")
    pr_title = os.environ.get("PR_TITLE", "")
    pr_body = os.environ.get("PR_BODY", "")
    pr_author = os.environ.get("PR_AUTHOR", "")
    pr_html_url = os.environ.get("PR_HTML_URL", "")

    missing = [k for k, v in {
        "GITHUB_TOKEN": github_token,
        "GITHUB_REPOSITORY": repo,
        "PR_NUMBER": pr_number,
        "PR_HEAD_SHA": head_sha,
    }.items() if not v]

    if missing:
        log.error("缺少必要环境变量: %s", ", ".join(missing))
        sys.exit(1)

    pr_number = int(pr_number)  # type: ignore[arg-type]

    # 延迟导入，避免在环境变量未就绪时加载
    from github_client import GitHubClient, PullRequest
    from reviewer import run_code_review

    gh = GitHubClient(token=github_token, repo=repo)  # type: ignore[arg-type]

    pr = PullRequest(
        number=pr_number,
        title=pr_title,
        body=pr_body,
        head_sha=head_sha,  # type: ignore[arg-type]
        author=pr_author,
        url=f"https://api.github.com/repos/{repo}/pulls/{pr_number}",
        diff_url=f"https://github.com/{repo}/pull/{pr_number}.diff",
        html_url=pr_html_url,
    )

    log.info("📌 审查 PR #%d: %s (sha=%s)", pr.number, pr.title, pr.head_sha[:7])

    # -----------------------------------------------------------------------
    # 获取 diff 和文件变更
    # -----------------------------------------------------------------------
    diff, files = await asyncio.gather(
        asyncio.to_thread(gh.get_pr_diff, pr.number),
        asyncio.to_thread(gh.get_pr_files, pr.number),
    )
    log.info("  %d 个文件，diff %.1f KB", len(files), len(diff) / 1024)

    # -----------------------------------------------------------------------
    # 调用 Claude Agent 进行 Code Review
    # -----------------------------------------------------------------------
    log.info("🤖 启动 Claude Agent ...")
    review_body = await run_code_review(pr, diff, files)

    # -----------------------------------------------------------------------
    # 发布 Comment
    # -----------------------------------------------------------------------
    comment = (
        f"## 🤖 自动 Code Review 报告\n\n"
        f"> 由 Claude 自动生成 · {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
        f" · commit `{pr.head_sha[:7]}`\n\n"
        f"---\n\n"
        f"{review_body}\n\n"
        f"---\n"
        f"*如有疑问请 @ 相关同学人工复核。*"
    )

    result = await asyncio.to_thread(gh.post_issue_comment, pr.number, comment)
    log.info("✅ Comment 已发布: %s", result["html_url"])


if __name__ == "__main__":
    asyncio.run(main())
