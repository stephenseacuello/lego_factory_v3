"""
Data Version Control - DVC-style Data Versioning.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 6: Research Platform Infrastructure

Provides Git-like versioning for large datasets with content-addressable storage.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum
from pathlib import Path
import hashlib
import json
import logging
import uuid

logger = logging.getLogger(__name__)


class CommitType(Enum):
    """Type of data commit."""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    MERGE = "merge"
    REVERT = "revert"


@dataclass
class DataCommit:
    """A data version commit."""
    commit_id: str
    commit_hash: str
    message: str
    commit_type: CommitType
    author: str
    timestamp: datetime
    parent_commits: List[str]
    changes: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "commit_id": self.commit_id,
            "commit_hash": self.commit_hash,
            "message": self.message,
            "commit_type": self.commit_type.value,
            "author": self.author,
            "timestamp": self.timestamp.isoformat(),
            "parent_commits": self.parent_commits,
            "changes": self.changes,
            "metadata": self.metadata,
            "tags": self.tags,
        }


@dataclass
class DataBranch:
    """A data versioning branch."""
    name: str
    head_commit: str
    created_at: datetime
    created_from: Optional[str]
    protected: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "head_commit": self.head_commit,
            "created_at": self.created_at.isoformat(),
            "created_from": self.created_from,
            "protected": self.protected,
        }


class DataVersionControl:
    """
    Git-like version control for manufacturing datasets.

    Features:
    - Content-addressable storage
    - Branch and merge support
    - Commit history and DAG
    - Tag management
    - Diff and comparison
    """

    def __init__(self, repo_path: str = "/data/dvc"):
        self.repo_path = Path(repo_path)
        self.commits: Dict[str, DataCommit] = {}
        self.branches: Dict[str, DataBranch] = {}
        self.tags: Dict[str, str] = {}  # tag_name -> commit_hash
        self.current_branch = "main"
        self._initialize_repo()

    def _initialize_repo(self):
        """Initialize with main branch and sample commits."""
        # Create initial commit
        initial_commit = DataCommit(
            commit_id=str(uuid.uuid4()),
            commit_hash=self._generate_hash("initial"),
            message="Initial commit - Repository created",
            commit_type=CommitType.CREATE,
            author="system",
            timestamp=datetime.now(),
            parent_commits=[],
            changes={"action": "initialize_repository"},
            metadata={"version": "1.0.0"},
        )
        self.commits[initial_commit.commit_hash] = initial_commit

        # Create main branch
        self.branches["main"] = DataBranch(
            name="main",
            head_commit=initial_commit.commit_hash,
            created_at=datetime.now(),
            created_from=None,
            protected=True,
        )

        # Add sample commits
        self._add_sample_commits(initial_commit.commit_hash)

    def _add_sample_commits(self, parent_hash: str):
        """Add sample commit history."""
        commits_data = [
            {
                "message": "Add quality inspection dataset v1.0",
                "changes": {
                    "added": ["datasets/quality_images/"],
                    "file_count": 5000,
                    "total_size": "1.2GB",
                },
                "author": "quality_team",
            },
            {
                "message": "Update quality dataset with new annotations",
                "changes": {
                    "modified": ["datasets/quality_images/annotations.json"],
                    "added_records": 2500,
                },
                "author": "annotation_team",
            },
            {
                "message": "Add sensor telemetry data pipeline",
                "changes": {
                    "added": ["datasets/sensor_data/", "pipelines/sensor_etl.py"],
                    "file_count": 12,
                },
                "author": "data_engineering",
            },
        ]

        current_parent = parent_hash
        for data in commits_data:
            commit = DataCommit(
                commit_id=str(uuid.uuid4()),
                commit_hash=self._generate_hash(data["message"]),
                message=data["message"],
                commit_type=CommitType.UPDATE,
                author=data["author"],
                timestamp=datetime.now(),
                parent_commits=[current_parent],
                changes=data["changes"],
            )
            self.commits[commit.commit_hash] = commit
            current_parent = commit.commit_hash

        # Update main branch head
        self.branches["main"].head_commit = current_parent

        # Add a tag
        self.tags["v1.0.0"] = parent_hash

    def _generate_hash(self, content: str) -> str:
        """Generate a commit hash."""
        data = f"{content}{datetime.now().isoformat()}{uuid.uuid4()}"
        return hashlib.sha256(data.encode()).hexdigest()[:12]

    def commit(
        self,
        message: str,
        changes: Dict[str, Any],
        author: str,
        commit_type: CommitType = CommitType.UPDATE,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DataCommit:
        """Create a new commit."""
        current_head = self.branches[self.current_branch].head_commit

        commit = DataCommit(
            commit_id=str(uuid.uuid4()),
            commit_hash=self._generate_hash(message),
            message=message,
            commit_type=commit_type,
            author=author,
            timestamp=datetime.now(),
            parent_commits=[current_head],
            changes=changes,
            metadata=metadata or {},
        )

        self.commits[commit.commit_hash] = commit
        self.branches[self.current_branch].head_commit = commit.commit_hash

        logger.info(f"Created commit {commit.commit_hash[:8]}: {message}")

        return commit

    def create_branch(
        self,
        name: str,
        from_commit: Optional[str] = None,
    ) -> DataBranch:
        """Create a new branch."""
        if name in self.branches:
            raise ValueError(f"Branch already exists: {name}")

        source_commit = from_commit or self.branches[self.current_branch].head_commit

        branch = DataBranch(
            name=name,
            head_commit=source_commit,
            created_at=datetime.now(),
            created_from=self.current_branch,
        )

        self.branches[name] = branch
        logger.info(f"Created branch: {name} from {source_commit[:8]}")

        return branch

    def checkout(self, branch_name: str) -> DataBranch:
        """Switch to a different branch."""
        if branch_name not in self.branches:
            raise ValueError(f"Branch not found: {branch_name}")

        self.current_branch = branch_name
        logger.info(f"Switched to branch: {branch_name}")

        return self.branches[branch_name]

    def merge(
        self,
        source_branch: str,
        author: str,
        message: Optional[str] = None,
    ) -> DataCommit:
        """Merge source branch into current branch."""
        if source_branch not in self.branches:
            raise ValueError(f"Branch not found: {source_branch}")

        source_head = self.branches[source_branch].head_commit
        target_head = self.branches[self.current_branch].head_commit

        merge_message = message or f"Merge branch '{source_branch}' into {self.current_branch}"

        commit = DataCommit(
            commit_id=str(uuid.uuid4()),
            commit_hash=self._generate_hash(merge_message),
            message=merge_message,
            commit_type=CommitType.MERGE,
            author=author,
            timestamp=datetime.now(),
            parent_commits=[target_head, source_head],
            changes={"merged_from": source_branch},
        )

        self.commits[commit.commit_hash] = commit
        self.branches[self.current_branch].head_commit = commit.commit_hash

        logger.info(f"Merged {source_branch} into {self.current_branch}")

        return commit

    def tag(self, tag_name: str, commit_hash: Optional[str] = None) -> str:
        """Create a tag at a commit."""
        target_commit = commit_hash or self.branches[self.current_branch].head_commit

        if target_commit not in self.commits:
            raise ValueError(f"Commit not found: {target_commit}")

        self.tags[tag_name] = target_commit
        logger.info(f"Created tag {tag_name} at {target_commit[:8]}")

        return target_commit

    def get_commit(self, commit_hash: str) -> Optional[DataCommit]:
        """Get commit by hash."""
        return self.commits.get(commit_hash)

    def get_history(
        self,
        branch: Optional[str] = None,
        limit: int = 50,
    ) -> List[DataCommit]:
        """Get commit history for a branch."""
        branch_name = branch or self.current_branch
        if branch_name not in self.branches:
            raise ValueError(f"Branch not found: {branch_name}")

        history = []
        visited = set()
        queue = [self.branches[branch_name].head_commit]

        while queue and len(history) < limit:
            commit_hash = queue.pop(0)
            if commit_hash in visited:
                continue

            visited.add(commit_hash)
            commit = self.commits.get(commit_hash)

            if commit:
                history.append(commit)
                queue.extend(commit.parent_commits)

        return history

    def diff(
        self,
        commit_a: str,
        commit_b: str,
    ) -> Dict[str, Any]:
        """Compare two commits."""
        c_a = self.get_commit(commit_a)
        c_b = self.get_commit(commit_b)

        if not c_a or not c_b:
            raise ValueError("Commit not found")

        return {
            "from_commit": commit_a,
            "to_commit": commit_b,
            "from_changes": c_a.changes,
            "to_changes": c_b.changes,
            "time_diff": (c_b.timestamp - c_a.timestamp).total_seconds(),
            "commits_between": self._count_commits_between(commit_a, commit_b),
        }

    def _count_commits_between(self, start: str, end: str) -> int:
        """Count commits between two points."""
        history = self.get_history(limit=1000)
        start_idx = next((i for i, c in enumerate(history) if c.commit_hash == start), -1)
        end_idx = next((i for i, c in enumerate(history) if c.commit_hash == end), -1)

        if start_idx == -1 or end_idx == -1:
            return -1

        return abs(end_idx - start_idx)

    def get_status(self) -> Dict[str, Any]:
        """Get repository status."""
        return {
            "current_branch": self.current_branch,
            "head_commit": self.branches[self.current_branch].head_commit,
            "branches": list(self.branches.keys()),
            "tags": list(self.tags.keys()),
            "total_commits": len(self.commits),
        }

    def revert(self, commit_hash: str, author: str) -> DataCommit:
        """Revert to a previous commit."""
        target = self.get_commit(commit_hash)
        if not target:
            raise ValueError(f"Commit not found: {commit_hash}")

        revert_commit = DataCommit(
            commit_id=str(uuid.uuid4()),
            commit_hash=self._generate_hash(f"revert-{commit_hash}"),
            message=f"Revert to {commit_hash[:8]}: {target.message}",
            commit_type=CommitType.REVERT,
            author=author,
            timestamp=datetime.now(),
            parent_commits=[self.branches[self.current_branch].head_commit],
            changes={"reverted_to": commit_hash, "original_changes": target.changes},
        )

        self.commits[revert_commit.commit_hash] = revert_commit
        self.branches[self.current_branch].head_commit = revert_commit.commit_hash

        return revert_commit
