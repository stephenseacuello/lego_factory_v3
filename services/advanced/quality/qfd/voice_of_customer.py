"""
Voice of Customer Analyzer - NLP-based VOC extraction.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 2: Causal AI & Explainability Engine
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from enum import Enum
import re
import logging
from collections import Counter

from .hoq_engine import CustomerRequirement, KanoType

logger = logging.getLogger(__name__)


@dataclass
class CustomerFeedback:
    """Raw customer feedback entry."""
    feedback_id: str
    text: str
    source: str  # survey, review, interview, support
    sentiment: float = 0.0  # -1 to 1
    timestamp: Optional[str] = None
    customer_segment: str = "general"


@dataclass
class RequirementCluster:
    """Cluster of related requirements."""
    cluster_id: str
    theme: str
    requirements: List[str]
    frequency: int
    average_sentiment: float


class VoiceOfCustomerAnalyzer:
    """
    NLP-based Voice of Customer extraction for LEGO brick requirements.

    Features:
    - Keyword extraction
    - Sentiment analysis
    - Requirement clustering
    - Kano model classification
    - Importance scoring
    """

    def __init__(self):
        self._keyword_patterns = self._load_keyword_patterns()
        self._kano_keywords = self._load_kano_keywords()

    def _load_keyword_patterns(self) -> Dict[str, List[str]]:
        """Load keyword patterns for requirement extraction."""
        return {
            'connection': ['connect', 'attach', 'stick', 'hold', 'clutch', 'grip'],
            'separation': ['separate', 'pull apart', 'remove', 'detach', 'release'],
            'compatibility': ['compatible', 'fit', 'work with', 'lego', 'official'],
            'durability': ['strong', 'durable', 'break', 'last', 'sturdy', 'robust'],
            'appearance': ['look', 'color', 'smooth', 'finish', 'surface', 'shiny'],
            'accuracy': ['accurate', 'precise', 'dimension', 'size', 'measure'],
            'ease_of_use': ['easy', 'simple', 'quick', 'convenient'],
            'value': ['price', 'cost', 'value', 'worth', 'affordable']
        }

    def _load_kano_keywords(self) -> Dict[KanoType, List[str]]:
        """Load keywords indicating Kano classification."""
        return {
            KanoType.MUST_BE: ['must', 'need', 'require', 'essential', 'basic', 'expect'],
            KanoType.ONE_DIMENSIONAL: ['want', 'like', 'prefer', 'better', 'more', 'improve'],
            KanoType.ATTRACTIVE: ['love', 'amazing', 'surprise', 'delight', 'wow', 'cool'],
            KanoType.REVERSE: ['hate', 'annoying', 'frustrating', 'terrible', 'worst']
        }

    def extract_requirements(self,
                            feedback_list: List[CustomerFeedback],
                            min_frequency: int = 2) -> List[CustomerRequirement]:
        """
        Extract customer requirements from feedback.

        Args:
            feedback_list: List of customer feedback entries
            min_frequency: Minimum mentions to include requirement

        Returns:
            List of CustomerRequirement objects
        """
        # Extract and count themes
        theme_mentions: Dict[str, List[str]] = {theme: [] for theme in self._keyword_patterns}
        theme_sentiments: Dict[str, List[float]] = {theme: [] for theme in self._keyword_patterns}

        for feedback in feedback_list:
            text_lower = feedback.text.lower()
            for theme, keywords in self._keyword_patterns.items():
                if any(kw in text_lower for kw in keywords):
                    theme_mentions[theme].append(feedback.text)
                    theme_sentiments[theme].append(feedback.sentiment)

        # Create requirements from frequent themes
        requirements = []
        req_counter = 0

        for theme, mentions in theme_mentions.items():
            if len(mentions) >= min_frequency:
                # Calculate importance from frequency and sentiment
                frequency_score = min(len(mentions) / len(feedback_list) * 20, 10)
                avg_sentiment = sum(theme_sentiments[theme]) / len(mentions) if mentions else 0
                sentiment_modifier = 1 + avg_sentiment * 0.3

                importance = min(frequency_score * sentiment_modifier, 10)

                # Determine Kano type
                kano_type = self._classify_kano(mentions)

                # Generate requirement description
                description = self._generate_requirement_description(theme, mentions)

                req = CustomerRequirement(
                    req_id=f"CR_{req_counter:03d}",
                    description=description,
                    importance=round(importance, 1),
                    kano_type=kano_type,
                    category=theme,
                    source="voc_analysis"
                )
                requirements.append(req)
                req_counter += 1

        # Sort by importance
        requirements.sort(key=lambda r: -r.importance)

        logger.info(f"Extracted {len(requirements)} requirements from {len(feedback_list)} feedback items")
        return requirements

    def _classify_kano(self, mentions: List[str]) -> KanoType:
        """Classify requirement using Kano model."""
        kano_scores = {kt: 0 for kt in KanoType}

        for mention in mentions:
            mention_lower = mention.lower()
            for kano_type, keywords in self._kano_keywords.items():
                if any(kw in mention_lower for kw in keywords):
                    kano_scores[kano_type] += 1

        # Return type with highest score, default to one_dimensional
        max_type = max(kano_scores, key=kano_scores.get)
        if kano_scores[max_type] > 0:
            return max_type
        return KanoType.ONE_DIMENSIONAL

    def _generate_requirement_description(self, theme: str, mentions: List[str]) -> str:
        """Generate requirement description from theme and mentions."""
        descriptions = {
            'connection': "Bricks should connect firmly and securely",
            'separation': "Bricks should be easy to separate when needed",
            'compatibility': "Bricks must be compatible with official LEGO bricks",
            'durability': "Bricks should be strong and durable for repeated use",
            'appearance': "Bricks should have good surface finish and accurate colors",
            'accuracy': "Bricks should have accurate dimensions",
            'ease_of_use': "Bricks should be easy and intuitive to use",
            'value': "Bricks should provide good value for the price"
        }
        return descriptions.get(theme, f"Customer requirement: {theme}")

    def analyze_sentiment(self, text: str) -> float:
        """
        Simple sentiment analysis.

        Returns value from -1 (negative) to 1 (positive).
        """
        positive_words = {'good', 'great', 'excellent', 'love', 'perfect', 'amazing',
                         'best', 'awesome', 'fantastic', 'wonderful', 'satisfied'}
        negative_words = {'bad', 'poor', 'terrible', 'hate', 'worst', 'awful',
                         'disappointed', 'frustrating', 'broken', 'defective'}

        text_lower = text.lower()
        words = set(re.findall(r'\w+', text_lower))

        pos_count = len(words & positive_words)
        neg_count = len(words & negative_words)
        total = pos_count + neg_count

        if total == 0:
            return 0.0
        return (pos_count - neg_count) / total

    def cluster_feedback(self,
                        feedback_list: List[CustomerFeedback],
                        n_clusters: int = 5) -> List[RequirementCluster]:
        """Cluster feedback into related groups."""
        # Simple clustering based on theme overlap
        clusters: Dict[str, List[CustomerFeedback]] = {}

        for feedback in feedback_list:
            text_lower = feedback.text.lower()
            matched_theme = None

            for theme, keywords in self._keyword_patterns.items():
                if any(kw in text_lower for kw in keywords):
                    matched_theme = theme
                    break

            if matched_theme:
                if matched_theme not in clusters:
                    clusters[matched_theme] = []
                clusters[matched_theme].append(feedback)

        # Convert to RequirementCluster objects
        result = []
        for i, (theme, feedbacks) in enumerate(clusters.items()):
            avg_sentiment = sum(f.sentiment for f in feedbacks) / len(feedbacks)
            cluster = RequirementCluster(
                cluster_id=f"CL_{i:03d}",
                theme=theme,
                requirements=[f.text for f in feedbacks],
                frequency=len(feedbacks),
                average_sentiment=avg_sentiment
            )
            result.append(cluster)

        result.sort(key=lambda c: -c.frequency)
        return result[:n_clusters]

    def prioritize_requirements(self,
                               requirements: List[CustomerRequirement],
                               weights: Optional[Dict[str, float]] = None) -> List[CustomerRequirement]:
        """
        Prioritize requirements using weighted scoring.

        Default weights:
        - importance: 0.4
        - kano_must_be: 0.3
        - kano_attractive: 0.2
        - frequency: 0.1
        """
        weights = weights or {
            'importance': 0.4,
            'kano_must_be': 0.3,
            'kano_attractive': 0.2
        }

        for req in requirements:
            score = req.importance * weights.get('importance', 0.4)

            # Kano bonus
            if req.kano_type == KanoType.MUST_BE:
                score += 10 * weights.get('kano_must_be', 0.3)
            elif req.kano_type == KanoType.ATTRACTIVE:
                score += 5 * weights.get('kano_attractive', 0.2)

            req.importance = min(score, 10)

        requirements.sort(key=lambda r: -r.importance)
        return requirements


# Pre-defined LEGO customer requirements
LEGO_STANDARD_REQUIREMENTS = [
    CustomerRequirement(
        req_id="CR_STD_001",
        description="Bricks connect firmly with good clutch power",
        importance=9.0,
        kano_type=KanoType.MUST_BE,
        category="connection"
    ),
    CustomerRequirement(
        req_id="CR_STD_002",
        description="Bricks are easy to separate",
        importance=8.0,
        kano_type=KanoType.ONE_DIMENSIONAL,
        category="separation"
    ),
    CustomerRequirement(
        req_id="CR_STD_003",
        description="Compatible with official LEGO bricks",
        importance=10.0,
        kano_type=KanoType.MUST_BE,
        category="compatibility"
    ),
    CustomerRequirement(
        req_id="CR_STD_004",
        description="Smooth surface finish",
        importance=6.0,
        kano_type=KanoType.ATTRACTIVE,
        category="appearance"
    ),
    CustomerRequirement(
        req_id="CR_STD_005",
        description="Accurate and consistent colors",
        importance=7.0,
        kano_type=KanoType.ONE_DIMENSIONAL,
        category="appearance"
    ),
    CustomerRequirement(
        req_id="CR_STD_006",
        description="Durable and long-lasting",
        importance=8.0,
        kano_type=KanoType.MUST_BE,
        category="durability"
    ),
]
