"""GitHub integration — creates repos and pushes generated code via PR."""
import logging
from datetime import datetime, timezone
import requests as http_requests

logger = logging.getLogger(__name__)


class GitHubService:
    """Push generated code to a GitHub repository."""

    def __init__(self, token: str):
        self.token = token
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }
        self.base_url = "https://api.github.com"

    def create_repo(self, org: str, name: str, private: bool = True, description: str = "") -> dict:
        """Create a new GitHub repository."""
        url = f"{self.base_url}/orgs/{org}/repos" if org else f"{self.base_url}/user/repos"
        payload = {"name": name, "private": private, "description": description, "auto_init": False}
        resp = http_requests.post(url, json=payload, headers=self.headers, timeout=30)
        if resp.status_code == 201:
            data = resp.json()
            return {"success": True, "url": data["html_url"], "clone_url": data["clone_url"], "full_name": data["full_name"]}
        return {"success": False, "error": f"GitHub API error {resp.status_code}: {resp.text[:200]}"}

    def deploy_via_pr(self, owner: str, repo: str, files: dict, commit_message: str,
                      pr_title: str, pr_body: str, default_branch: str = "main",
                      branch_slug: str = "codegen") -> dict:
        """Push files to a new branch and create a pull request (GAP-05).

        Returns {"success": True, "commit_sha": ..., "pr_url": ..., "branch": ...}
        """
        try:
            # 1. Get default branch SHA
            ref_url = f"{self.base_url}/repos/{owner}/{repo}/git/ref/heads/{default_branch}"
            ref_resp = http_requests.get(ref_url, headers=self.headers, timeout=15)
            if ref_resp.status_code != 200:
                # Repo is empty — fall back to direct push (no PR possible on empty repo)
                result = self.push_files(owner, repo, files, commit_message)
                result["pr_url"] = None
                result["branch"] = default_branch
                return result

            base_sha = ref_resp.json()["object"]["sha"]

            # 2. Create feature branch from default branch
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
            branch_name = f"archie/{branch_slug}-{timestamp}"

            branch_resp = http_requests.post(
                f"{self.base_url}/repos/{owner}/{repo}/git/refs",
                json={"ref": f"refs/heads/{branch_name}", "sha": base_sha},
                headers=self.headers, timeout=15,
            )
            if branch_resp.status_code != 201:
                logger.warning("Branch creation failed (%s), falling back to direct push", branch_resp.status_code)
                return self.push_files(owner, repo, files, commit_message)

            # 3. Create blobs, tree, and commit (same as push_files internals)
            commit_resp = http_requests.get(
                f"{self.base_url}/repos/{owner}/{repo}/git/commits/{base_sha}",
                headers=self.headers, timeout=15,
            )
            base_tree = commit_resp.json()["tree"]["sha"] if commit_resp.status_code == 200 else None

            tree_items = []
            for path, content in files.items():
                blob_resp = http_requests.post(
                    f"{self.base_url}/repos/{owner}/{repo}/git/blobs",
                    json={"content": content, "encoding": "utf-8"},
                    headers=self.headers, timeout=15,
                )
                if blob_resp.status_code != 201:
                    return {"success": False, "error": f"Failed to create blob for {path}"}
                tree_items.append({
                    "path": path, "mode": "100644", "type": "blob", "sha": blob_resp.json()["sha"],
                })

            tree_payload = {"tree": tree_items}
            if base_tree:
                tree_payload["base_tree"] = base_tree
            tree_resp = http_requests.post(
                f"{self.base_url}/repos/{owner}/{repo}/git/trees",
                json=tree_payload, headers=self.headers, timeout=30,
            )
            if tree_resp.status_code != 201:
                return {"success": False, "error": "Failed to create tree"}

            new_commit_resp = http_requests.post(
                f"{self.base_url}/repos/{owner}/{repo}/git/commits",
                json={"message": commit_message, "tree": tree_resp.json()["sha"], "parents": [base_sha]},
                headers=self.headers, timeout=15,
            )
            if new_commit_resp.status_code != 201:
                return {"success": False, "error": "Failed to create commit"}

            commit_sha = new_commit_resp.json()["sha"]

            # 4. Update branch ref to the new commit
            http_requests.patch(
                f"{self.base_url}/repos/{owner}/{repo}/git/refs/heads/{branch_name}",
                json={"sha": commit_sha},
                headers=self.headers, timeout=15,
            )

            # 5. Create pull request
            pr_resp = http_requests.post(
                f"{self.base_url}/repos/{owner}/{repo}/pulls",
                json={"title": pr_title, "body": pr_body, "head": branch_name, "base": default_branch},
                headers=self.headers, timeout=30,
            )
            if pr_resp.status_code == 201:
                pr_data = pr_resp.json()
                return {
                    "success": True,
                    "commit_sha": commit_sha,
                    "pr_url": pr_data["html_url"],
                    "pr_number": pr_data["number"],
                    "branch": branch_name,
                }

            # PR creation failed but code is on branch
            logger.warning("PR creation failed (%s): %s", pr_resp.status_code, pr_resp.text[:200])
            return {
                "success": True,
                "commit_sha": commit_sha,
                "pr_url": None,
                "branch": branch_name,
                "warning": f"Code pushed to {branch_name} but PR creation failed: {pr_resp.text[:100]}",
            }

        except Exception as e:
            logger.error("GitHub deploy via PR failed: %s", e)
            return {"success": False, "error": str(e)}

    def compare_commits(self, owner: str, repo: str, base_sha: str, head: str = "HEAD") -> dict:
        """Compare base_sha against head ref. Returns list of changed files since our last push.

        Uses GitHub's compare API — single request, returns full patch per file.
        Returns {"success": True, "base_sha": ..., "head_sha": ..., "files": [...], "total_commits": N}
        Each file: {"path", "change_type" (added/modified/removed/renamed), "additions", "deletions", "patch"}
        """
        try:
            url = f"{self.base_url}/repos/{owner}/{repo}/compare/{base_sha}...{head}"
            resp = http_requests.get(url, headers=self.headers, timeout=30)
            if resp.status_code == 404:
                return {"success": False, "error": "Repository or commit not found — has the repo been deleted or rebased?"}
            if resp.status_code != 200:
                return {"success": False, "error": f"GitHub compare API returned {resp.status_code}: {resp.text[:200]}"}

            data = resp.json()
            files = [
                {
                    "path": f["filename"],
                    "change_type": f["status"],  # added | removed | modified | renamed
                    "additions": f.get("additions", 0),
                    "deletions": f.get("deletions", 0),
                    "patch": f.get("patch", ""),  # unified diff — may be absent for binary files
                }
                for f in data.get("files", [])
            ]
            commits = data.get("commits", [])
            head_sha = commits[-1]["sha"] if commits else base_sha
            return {
                "success": True,
                "base_sha": base_sha,
                "head_sha": head_sha,
                "files": files,
                "total_commits": data.get("total_commits", 0),
            }
        except Exception as e:
            logger.error("GitHub compare_commits failed (%s/%s): %s", owner, repo, e)
            return {"success": False, "error": str(e)}

    def get_file_content(self, owner: str, repo: str, path: str, ref: str = "HEAD") -> str | None:
        """Fetch raw content of a single file from GitHub. Returns decoded string or None on error."""
        try:
            import base64
            url = f"{self.base_url}/repos/{owner}/{repo}/contents/{path}?ref={ref}"
            resp = http_requests.get(url, headers=self.headers, timeout=15)
            if resp.status_code != 200:
                return None
            data = resp.json()
            encoded = data.get("content", "")
            return base64.b64decode(encoded).decode("utf-8", errors="replace")
        except Exception as e:
            logger.debug("get_file_content failed for %s/%s/%s: %s", owner, repo, path, e)
            return None
