"""
Model Versioning Service

GitOps for architecture artifacts with branching and merge support.
Provides version control for architecture models, policies, and configurations.

Features:
- Git-based versioning for architecture artifacts
- Branching and merging workflows
- Conflict resolution for model changes
- Audit trail of model evolution
- Integration with ARB approval processes
- Automated validation and testing
"""

import hashlib
import json
import logging
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ArtifactType(Enum):
    """Types of architecture artifacts."""

    ARCHIMATE_MODEL = "archimate_model"
    CAPABILITY_MODEL = "capability_model"
    APPLICATION_MODEL = "application_model"
    DATA_MODEL = "data_model"
    POLICY_DOCUMENT = "policy_document"
    CONFIGURATION = "configuration"
    DIAGRAM = "diagram"


class VersionStatus(Enum):
    """Version status in lifecycle."""

    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    REJECTED = "rejected"


@dataclass
class ArtifactVersion:
    """Version information for an architecture artifact."""

    artifact_id: str
    version: str
    artifact_type: ArtifactType
    name: str
    description: str
    author: str
    status: VersionStatus
    branch: str = "main"
    parent_version: Optional[str] = None
    content_hash: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    published_at: Optional[datetime] = None


@dataclass
class MergeRequest:
    """Merge request for artifact versions."""

    merge_id: str
    source_branch: str
    target_branch: str
    artifact_id: str
    title: str
    description: str
    author: str
    reviewers: List[str] = field(default_factory=list)
    status: str = "open"  # open, merged, closed
    conflicts: List[Dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    merged_at: Optional[datetime] = None
    merged_by: Optional[str] = None


class ModelVersioningService:
    """
    GitOps service for architecture artifact versioning.

    Provides version control capabilities:
    - Artifact versioning with Git-like operations
    - Branching and merging workflows
    - Conflict detection and resolution
    - ARB integration for approvals
    - Audit trail and compliance reporting
    """

    def __init__(self, repo_path: str = None):
        self.repo_path = repo_path or os.path.join(os.getcwd(), "architecture_repo")
        self.versions: Dict[str, List[ArtifactVersion]] = {}
        self.merge_requests: Dict[str, MergeRequest] = {}
        self._ensure_repo()

    def _ensure_repo(self):
        """Ensure Git repository exists."""
        if not os.path.exists(self.repo_path):
            os.makedirs(self.repo_path)
            # Initialize Git repo
            try:
                subprocess.run(["git", "init"], cwd=self.repo_path, check=True, capture_output=True)
                subprocess.run(
                    ["git", "config", "user.name", "Architecture System"],
                    cwd=self.repo_path,
                    check=True,
                )
                subprocess.run(
                    ["git", "config", "user.email", "architecture@system.local"],
                    cwd=self.repo_path,
                    check=True,
                )
                logger.info(f"Initialized architecture repository at {self.repo_path}")
            except subprocess.CalledProcessError as e:
                logger.warning(f"Failed to initialize Git repo: {e}")

    def create_artifact_version(
        self, artifact_data: Dict[str, Any], content: bytes, author: str
    ) -> ArtifactVersion:
        """
        Create a new version of an architecture artifact.

        Args:
            artifact_data: Artifact metadata
            content: Artifact content
            author: Author of the version

        Returns:
            Created artifact version
        """
        artifact_id = artifact_data["artifact_id"]
        version = self._generate_version_number(artifact_id)

        # Calculate content hash
        content_hash = hashlib.sha256(content).hexdigest()

        # Create version object
        version_obj = ArtifactVersion(
            artifact_id=artifact_id,
            version=version,
            artifact_type=ArtifactType(artifact_data["artifact_type"]),
            name=artifact_data["name"],
            description=artifact_data.get("description", ""),
            author=author,
            status=VersionStatus.DRAFT,
            branch=artifact_data.get("branch", "main"),
            content_hash=content_hash,
            metadata=artifact_data.get("metadata", {}),
            tags=artifact_data.get("tags", []),
        )

        # Store content in Git
        self._store_content(version_obj, content)

        # Track version
        if artifact_id not in self.versions:
            self.versions[artifact_id] = []
        self.versions[artifact_id].append(version_obj)

        logger.info(f"Created artifact version: {artifact_id} v{version}")
        return version_obj

    def update_artifact_version(
        self,
        artifact_id: str,
        version: str,
        updates: Dict[str, Any],
        content: Optional[bytes] = None,
        author: str = None,
    ) -> Optional[ArtifactVersion]:
        """
        Update an existing artifact version.

        Args:
            artifact_id: Artifact ID
            version: Version to update
            updates: Updates to apply
            content: New content (if changed)
            author: Author of the update

        Returns:
            Updated version or None if not found
        """
        version_obj = self.get_artifact_version(artifact_id, version)
        if not version_obj:
            return None

        # Apply updates
        for key, value in updates.items():
            if hasattr(version_obj, key):
                setattr(version_obj, key, value)

        version_obj.updated_at = datetime.utcnow()

        # Update content if provided
        if content:
            content_hash = hashlib.sha256(content).hexdigest()
            version_obj.content_hash = content_hash
            self._store_content(version_obj, content)

        # Commit changes to Git
        self._commit_version(version_obj, f"Update {artifact_id} v{version}")

        logger.info(f"Updated artifact version: {artifact_id} v{version}")
        return version_obj

    def submit_for_review(
        self, artifact_id: str, version: str, reviewers: List[str]
    ) -> Optional[MergeRequest]:
        """
        Submit artifact version for review.

        Args:
            artifact_id: Artifact ID
            version: Version to submit
            reviewers: List of reviewers

        Returns:
            Created merge request or None if failed
        """
        version_obj = self.get_artifact_version(artifact_id, version)
        if not version_obj:
            return None

        # Update status
        version_obj.status = VersionStatus.REVIEW

        # Create merge request if not on main branch
        if version_obj.branch != "main":
            merge_request = MergeRequest(
                merge_id=f"MR-{artifact_id}-{version}",
                source_branch=version_obj.branch,
                target_branch="main",
                artifact_id=artifact_id,
                title=f"Review {version_obj.name} v{version}",
                description=f"Review request for {version_obj.name}",
                author=version_obj.author,
                reviewers=reviewers,
            )

            self.merge_requests[merge_request.merge_id] = merge_request
            logger.info(f"Created merge request: {merge_request.merge_id}")
            return merge_request

        return None

    def approve_version(self, artifact_id: str, version: str, approver: str) -> bool:
        """
        Approve an artifact version.

        Args:
            artifact_id: Artifact ID
            version: Version to approve
            approver: Approver user ID

        Returns:
            True if approved successfully
        """
        version_obj = self.get_artifact_version(artifact_id, version)
        if not version_obj:
            return False

        version_obj.status = VersionStatus.APPROVED
        version_obj.approved_at = datetime.utcnow()
        version_obj.approved_by = approver

        logger.info(f"Approved artifact version: {artifact_id} v{version} by {approver}")
        return True

    def publish_version(self, artifact_id: str, version: str) -> bool:
        """
        Publish an approved artifact version.

        Args:
            artifact_id: Artifact ID
            version: Version to publish

        Returns:
            True if published successfully
        """
        version_obj = self.get_artifact_version(artifact_id, version)
        if not version_obj or version_obj.status != VersionStatus.APPROVED:
            return False

        # Merge to main branch if needed
        if version_obj.branch != "main":
            success = self._merge_to_main(version_obj)
            if not success:
                return False

        version_obj.status = VersionStatus.PUBLISHED
        version_obj.published_at = datetime.utcnow()

        logger.info(f"Published artifact version: {artifact_id} v{version}")
        return True

    def create_branch(
        self, artifact_id: str, branch_name: str, from_version: Optional[str] = None
    ) -> bool:
        """
        Create a new branch for an artifact.

        Args:
            artifact_id: Artifact ID
            branch_name: Name of new branch
            from_version: Version to branch from (latest if None)

        Returns:
            True if branch created successfully
        """
        try:
            # Git branch creation
            from_version = from_version or "HEAD"
            subprocess.run(
                ["git", "checkout", "-b", branch_name, from_version],
                cwd=self.repo_path,
                check=True,
                capture_output=True,
            )
            subprocess.run(["git", "checkout", "main"], cwd=self.repo_path, check=True)

            logger.info(f"Created branch {branch_name} for artifact {artifact_id}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create branch {branch_name}: {e}")
            return False

    def merge_branches(
        self, merge_request: MergeRequest, merger: str
    ) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Merge branches with conflict detection.

        Args:
            merge_request: Merge request details
            merger: User performing merge

        Returns:
            (success, conflicts) tuple
        """
        try:
            # Attempt merge
            result = subprocess.run(
                [
                    "git",
                    "merge",
                    merge_request.source_branch,
                    "--no-ff",
                    "-m",
                    f"Merge {merge_request.title}",
                ],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                # Successful merge
                merge_request.status = "merged"
                merge_request.merged_at = datetime.utcnow()
                merge_request.merged_by = merger

                # Update version status
                version_obj = self.get_artifact_version(
                    merge_request.artifact_id, None, merge_request.source_branch
                )
                if version_obj:
                    version_obj.status = VersionStatus.APPROVED

                logger.info(
                    f"Merged branch {merge_request.source_branch} to {merge_request.target_branch}"
                )
                return True, []

            else:
                # Check for conflicts
                conflicts = self._detect_conflicts()
                merge_request.conflicts = conflicts
                logger.warning(f"Merge conflicts detected for {merge_request.merge_id}")
                return False, conflicts

        except subprocess.CalledProcessError as e:
            logger.error(f"Merge failed: {e}")
            return False, [{"error": str(e)}]

    def get_artifact_version(
        self, artifact_id: str, version: Optional[str] = None, branch: str = "main"
    ) -> Optional[ArtifactVersion]:
        """Get specific artifact version."""
        if artifact_id not in self.versions:
            return None

        versions = self.versions[artifact_id]

        if version:
            # Find specific version
            for v in versions:
                if v.version == version and v.branch == branch:
                    return v
        else:
            # Return latest version on branch
            branch_versions = [v for v in versions if v.branch == branch]
            if branch_versions:
                return max(branch_versions, key=lambda v: v.created_at)

        return None

    def get_artifact_history(self, artifact_id: str, branch: str = "main") -> List[ArtifactVersion]:
        """Get version history for an artifact."""
        if artifact_id not in self.versions:
            return []

        return sorted(
            [v for v in self.versions[artifact_id] if v.branch == branch],
            key=lambda v: v.created_at,
            reverse=True,
        )

    def get_content(self, version: ArtifactVersion) -> Optional[bytes]:
        """Retrieve artifact content."""
        try:
            file_path = self._get_content_path(version)
            if os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    return f.read()
        except Exception as e:
            logger.error(
                f"Failed to read content for {version.artifact_id} v{version.version}: {e}"
            )

        return None

    def _generate_version_number(self, artifact_id: str) -> str:
        """Generate next version number."""
        existing_versions = self.versions.get(artifact_id, [])
        if not existing_versions:
            return "1.0.0"

        # Simple increment - in production, use semantic versioning
        latest = max(existing_versions, key=lambda v: [int(x) for x in v.version.split(".")])
        major, minor, patch = [int(x) for x in latest.version.split(".")]
        return f"{major}.{minor}.{patch + 1}"

    def _store_content(self, version: ArtifactVersion, content: bytes):
        """Store artifact content."""
        file_path = self._get_content_path(version)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        with open(file_path, "wb") as f:
            f.write(content)

        # Git add and commit
        self._commit_version(version, f"Add {version.artifact_id} v{version.version}")

    def _get_content_path(self, version: ArtifactVersion) -> str:
        """Get file path for version content."""
        return os.path.join(
            self.repo_path,
            version.artifact_type.value,
            version.artifact_id,
            version.branch,
            f"v{version.version}",
            f"{version.name}.{self._get_file_extension(version.artifact_type)}",
        )

    def _get_file_extension(self, artifact_type: ArtifactType) -> str:
        """Get file extension for artifact type."""
        extensions = {
            ArtifactType.ARCHIMATE_MODEL: "xml",
            ArtifactType.CAPABILITY_MODEL: "json",
            ArtifactType.APPLICATION_MODEL: "yaml",
            ArtifactType.DATA_MODEL: "sql",
            ArtifactType.POLICY_DOCUMENT: "md",
            ArtifactType.CONFIGURATION: "yaml",
            ArtifactType.DIAGRAM: "svg",
        }
        return extensions.get(artifact_type, "bin")

    def _commit_version(self, version: ArtifactVersion, message: str):
        """Commit version to Git."""
        try:
            subprocess.run(["git", "add", "."], cwd=self.repo_path, check=True, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", message],
                cwd=self.repo_path,
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            logger.warning(f"Git commit failed: {e}")

    def _merge_to_main(self, version: ArtifactVersion) -> bool:
        """Merge version branch to main."""
        try:
            subprocess.run(["git", "checkout", "main"], cwd=self.repo_path, check=True)
            subprocess.run(
                [
                    "git",
                    "merge",
                    version.branch,
                    "--no-ff",
                    "-m",
                    f"Merge {version.artifact_id} v{version.version} to main",
                ],
                cwd=self.repo_path,
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to merge {version.branch} to main: {e}")
            return False

    def _detect_conflicts(self) -> List[Dict[str, Any]]:
        """Detect merge conflicts."""
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            conflicts = []
            for line in result.stdout.split("\n"):
                if line.startswith("UU "):
                    conflicts.append({"file": line[3:], "type": "content_conflict"})
            return conflicts
        except subprocess.CalledProcessError:
            return []
