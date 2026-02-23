"""
Weighted Voting - Consensus through weighted agent votes.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 1: Multi-Agent Orchestration Framework
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class VoteChoice(Enum):
    """Vote choices."""
    APPROVE = "approve"
    REJECT = "reject"
    ABSTAIN = "abstain"


@dataclass
class Vote:
    """Individual agent vote."""
    agent_id: str
    choice: VoteChoice
    weight: float
    confidence: float
    reasoning: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class VoteResult:
    """Result of a voting round."""
    proposal_id: str
    approved: bool
    approval_score: float
    rejection_score: float
    abstain_score: float
    total_weight: float
    votes: List[Vote]
    quorum_reached: bool
    timestamp: datetime = field(default_factory=datetime.utcnow)


class WeightedVoting:
    """
    Weighted voting protocol for multi-agent consensus.

    Features:
    - Weighted votes based on agent expertise
    - Confidence-weighted scoring
    - Quorum requirements
    - Approval thresholds
    """

    def __init__(self,
                 approval_threshold: float = 0.6,
                 quorum_threshold: float = 0.5,
                 default_weight: float = 1.0):
        self.approval_threshold = approval_threshold
        self.quorum_threshold = quorum_threshold
        self.default_weight = default_weight
        self._agent_weights: Dict[str, float] = {}
        self._active_votes: Dict[str, Dict[str, Vote]] = {}
        self._results: Dict[str, VoteResult] = {}

    def set_agent_weight(self, agent_id: str, weight: float) -> None:
        """Set voting weight for an agent."""
        self._agent_weights[agent_id] = max(0.0, weight)

    def get_agent_weight(self, agent_id: str) -> float:
        """Get voting weight for an agent."""
        return self._agent_weights.get(agent_id, self.default_weight)

    def start_vote(self, proposal_id: str, eligible_agents: List[str]) -> None:
        """Start a new voting round."""
        self._active_votes[proposal_id] = {}
        logger.info(f"Started vote {proposal_id} with {len(eligible_agents)} eligible agents")

    def cast_vote(self,
                  proposal_id: str,
                  agent_id: str,
                  choice: VoteChoice,
                  confidence: float = 1.0,
                  reasoning: Optional[str] = None) -> bool:
        """
        Cast a vote on a proposal.

        Args:
            proposal_id: Proposal identifier
            agent_id: Voting agent ID
            choice: Vote choice
            confidence: Confidence in vote (0-1)
            reasoning: Optional reasoning

        Returns:
            True if vote recorded
        """
        if proposal_id not in self._active_votes:
            logger.warning(f"No active vote for proposal {proposal_id}")
            return False

        weight = self.get_agent_weight(agent_id)
        vote = Vote(
            agent_id=agent_id,
            choice=choice,
            weight=weight,
            confidence=max(0.0, min(1.0, confidence)),
            reasoning=reasoning
        )

        self._active_votes[proposal_id][agent_id] = vote
        logger.debug(f"Agent {agent_id} voted {choice.value} on {proposal_id}")
        return True

    def tally_votes(self, proposal_id: str, total_eligible_weight: float) -> Optional[VoteResult]:
        """
        Tally votes and determine outcome.

        Args:
            proposal_id: Proposal identifier
            total_eligible_weight: Total weight of all eligible voters

        Returns:
            VoteResult or None if voting not found
        """
        if proposal_id not in self._active_votes:
            return None

        votes = list(self._active_votes[proposal_id].values())
        if not votes:
            return VoteResult(
                proposal_id=proposal_id,
                approved=False,
                approval_score=0,
                rejection_score=0,
                abstain_score=0,
                total_weight=0,
                votes=[],
                quorum_reached=False
            )

        # Calculate weighted scores
        approve_score = 0.0
        reject_score = 0.0
        abstain_score = 0.0
        total_voted_weight = 0.0

        for vote in votes:
            effective_weight = vote.weight * vote.confidence
            total_voted_weight += vote.weight

            if vote.choice == VoteChoice.APPROVE:
                approve_score += effective_weight
            elif vote.choice == VoteChoice.REJECT:
                reject_score += effective_weight
            else:
                abstain_score += effective_weight

        # Check quorum
        quorum_reached = (total_voted_weight / total_eligible_weight) >= self.quorum_threshold

        # Determine approval (excluding abstentions)
        voting_score = approve_score + reject_score
        approved = False
        if voting_score > 0:
            approval_ratio = approve_score / voting_score
            approved = quorum_reached and approval_ratio >= self.approval_threshold

        result = VoteResult(
            proposal_id=proposal_id,
            approved=approved,
            approval_score=approve_score,
            rejection_score=reject_score,
            abstain_score=abstain_score,
            total_weight=total_voted_weight,
            votes=votes,
            quorum_reached=quorum_reached
        )

        self._results[proposal_id] = result
        del self._active_votes[proposal_id]

        logger.info(f"Vote {proposal_id} tallied: approved={approved}, score={approve_score:.2f}/{reject_score:.2f}")
        return result

    def get_result(self, proposal_id: str) -> Optional[VoteResult]:
        """Get result of a completed vote."""
        return self._results.get(proposal_id)

    def get_pending_votes(self) -> List[str]:
        """Get list of pending vote proposal IDs."""
        return list(self._active_votes.keys())
