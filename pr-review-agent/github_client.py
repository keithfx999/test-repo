"""
github_client.py — GitHub REST API 封装

负责：
- 拉取仓库中的 open PR 列表
- 获取某个 PR 的 diff / 文件变更
- 发布 Review Comment 到 PR
"""

import os
import httpx
from dataclasses import dataclass
from typing import Optional


@dataclass
class PullRequest:
    number: int
    title: str
    body: str
    head_sha: str
    author: str
    url: str
    diff_url: str
    html_url: str


class GitHubClient:
    BASE = "https://api.github.com"

    def __init__(self, token: str, repo: str):
        """
        :param token: GitHub Personal Access Token（需要 repo 权限）
        :param repo:  owner/repo 格式，例如 "octocat/hello-world"
        """
        self.repo = repo
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    # ------------------------------------------------------------------
    # PR 列表
    # ------------------------------------------------------------------

    def list_open_prs(self) -> list[PullRequest]:
        """返回仓库中所有 open 状态的 PR。"""
        url = f"{self.BASE}/repos/{self.repo}/pulls"
        params = {"state": "open", "per_page": 100}
        with httpx.Client(headers=self.headers, timeout=30) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            return [self._parse_pr(p) for p in resp.json()]

    # ------------------------------------------------------------------
    # PR 内容
    # ------------------------------------------------------------------

    def get_pr_diff(self, pr_number: int) -> str:
        """获取 PR 的 unified diff 文本（原始 patch 格式）。"""
        url = f"{self.BASE}/repos/{self.repo}/pulls/{pr_number}"
        with httpx.Client(
            headers={**self.headers, "Accept": "application/vnd.github.diff"},
            timeout=60,
        ) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.text

    def get_pr_files(self, pr_number: int) -> list[dict]:
        """获取 PR 变更文件列表（含 filename / status / patch 等字段）。"""
        url = f"{self.BASE}/repos/{self.repo}/pulls/{pr_number}/files"
        with httpx.Client(headers=self.headers, timeout=30) as client:
            resp = client.get(url, params={"per_page": 100})
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    # 发布评论
    # ------------------------------------------------------------------

    def post_review_comment(self, pr_number: int, body: str) -> dict:
        """
        向指定 PR 发布一条 Review（COMMENT 类型，不批准也不拒绝）。
        body: Markdown 格式的评论正文。
        """
        url = f"{self.BASE}/repos/{self.repo}/pulls/{pr_number}/reviews"
        payload = {"body": body, "event": "COMMENT"}
        with httpx.Client(headers=self.headers, timeout=30) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()

    def post_issue_comment(self, pr_number: int, body: str) -> dict:
        """
        向 PR 的 issue 线程发布一条普通评论（更简单，不触发 Review 流程）。
        """
        url = f"{self.BASE}/repos/{self.repo}/issues/{pr_number}/comments"
        with httpx.Client(headers=self.headers, timeout=30) as client:
            resp = client.post(url, json={"body": body})
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_pr(data: dict) -> PullRequest:
        return PullRequest(
            number=data["number"],
            title=data["title"],
            body=data.get("body") or "",
            head_sha=data["head"]["sha"],
            author=data["user"]["login"],
            url=data["url"],
            diff_url=data["diff_url"],
            html_url=data["html_url"],
        )
