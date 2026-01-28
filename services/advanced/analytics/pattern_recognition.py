"""
Pattern Recognition

Manufacturing pattern detection for quality improvement,
process optimization, and predictive maintenance.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from enum import Enum
import math

logger = logging.getLogger(__name__)


class PatternType(Enum):
    """Pattern types in manufacturing data."""
    CYCLE = "cycle"              # Recurring pattern
    TREND = "trend"              # Upward/downward trend
    SHIFT = "shift"              # Level shift
    MIXTURE = "mixture"          # Multi-modal distribution
    STRATIFICATION = "stratification"  # Non-random clustering
    OSCILLATION = "oscillation"  # Regular alternation


@dataclass
class MatchResult:
    """Pattern match result."""
    pattern_type: PatternType
    confidence: float
    start_index: int
    end_index: int
    parameters: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.pattern_type.value,
            "confidence": round(self.confidence, 4),
            "range": [self.start_index, self.end_index],
            "parameters": self.parameters,
            "description": self.description
        }


class PatternMatcher:
    """
    Manufacturing Pattern Recognition.
    
    Detects patterns in time series data:
    - Cycles and periodicities
    - Trends and drifts
    - Level shifts
    - Mixtures and bimodality
    """
    
    def __init__(
        self,
        min_confidence: float = 0.7,
        min_pattern_length: int = 5
    ):
        self.min_confidence = min_confidence
        self.min_pattern_length = min_pattern_length
        logger.info("PatternMatcher initialized")
    
    def find_patterns(
        self,
        data: List[float],
        pattern_types: Optional[List[PatternType]] = None
    ) -> List[MatchResult]:
        """Find all patterns in data."""
        if len(data) < self.min_pattern_length:
            return []
        
        patterns = []
        types_to_check = pattern_types or list(PatternType)
        
        for ptype in types_to_check:
            if ptype == PatternType.CYCLE:
                patterns.extend(self._find_cycles(data))
            elif ptype == PatternType.TREND:
                patterns.extend(self._find_trends(data))
            elif ptype == PatternType.SHIFT:
                patterns.extend(self._find_shifts(data))
            elif ptype == PatternType.OSCILLATION:
                patterns.extend(self._find_oscillations(data))
            elif ptype == PatternType.MIXTURE:
                patterns.extend(self._find_mixtures(data))
        
        # Filter by confidence
        patterns = [p for p in patterns if p.confidence >= self.min_confidence]
        
        # Sort by confidence
        patterns.sort(key=lambda x: x.confidence, reverse=True)
        
        return patterns
    
    def _find_cycles(self, data: List[float]) -> List[MatchResult]:
        """Detect cyclic patterns using autocorrelation."""
        patterns = []
        n = len(data)
        
        if n < 10:
            return patterns
        
        mean = sum(data) / n
        variance = sum((x - mean) ** 2 for x in data)
        
        if variance == 0:
            return patterns
        
        best_lag = None
        best_correlation = 0.5  # Threshold
        
        for lag in range(2, min(n // 3, 50)):
            correlation = sum(
                (data[i] - mean) * (data[i + lag] - mean)
                for i in range(n - lag)
            ) / variance
            
            if correlation > best_correlation:
                best_correlation = correlation
                best_lag = lag
        
        if best_lag:
            patterns.append(MatchResult(
                pattern_type=PatternType.CYCLE,
                confidence=best_correlation,
                start_index=0,
                end_index=n - 1,
                parameters={"period": best_lag},
                description=f"Cyclic pattern with period {best_lag}"
            ))
        
        return patterns
    
    def _find_trends(self, data: List[float]) -> List[MatchResult]:
        """Detect linear trends."""
        patterns = []
        n = len(data)
        
        if n < 5:
            return patterns
        
        # Linear regression
        x = list(range(n))
        x_mean = sum(x) / n
        y_mean = sum(data) / n
        
        numerator = sum((x[i] - x_mean) * (data[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return patterns
        
        slope = numerator / denominator
        intercept = y_mean - slope * x_mean
        
        # R-squared
        predictions = [slope * x[i] + intercept for i in range(n)]
        ss_res = sum((data[i] - predictions[i]) ** 2 for i in range(n))
        ss_tot = sum((data[i] - y_mean) ** 2 for i in range(n))
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        if r_squared > 0.5 and abs(slope) > 0.001:
            direction = "upward" if slope > 0 else "downward"
            patterns.append(MatchResult(
                pattern_type=PatternType.TREND,
                confidence=r_squared,
                start_index=0,
                end_index=n - 1,
                parameters={
                    "slope": round(slope, 6),
                    "direction": direction,
                    "r_squared": round(r_squared, 4)
                },
                description=f"Linear {direction} trend (R²={r_squared:.3f})"
            ))
        
        return patterns
    
    def _find_shifts(self, data: List[float]) -> List[MatchResult]:
        """Detect level shifts using change point detection."""
        patterns = []
        n = len(data)
        
        if n < 10:
            return patterns
        
        best_split = None
        best_reduction = 0
        
        # Total variance
        total_mean = sum(data) / n
        total_var = sum((x - total_mean) ** 2 for x in data)
        
        for i in range(5, n - 5):
            left = data[:i]
            right = data[i:]
            
            left_mean = sum(left) / len(left)
            right_mean = sum(right) / len(right)
            
            left_var = sum((x - left_mean) ** 2 for x in left)
            right_var = sum((x - right_mean) ** 2 for x in right)
            
            reduction = 1 - (left_var + right_var) / total_var if total_var > 0 else 0
            
            if reduction > best_reduction and abs(left_mean - right_mean) > 0.1 * abs(total_mean):
                best_reduction = reduction
                best_split = i
        
        if best_split and best_reduction > 0.3:
            left_mean = sum(data[:best_split]) / best_split
            right_mean = sum(data[best_split:]) / (n - best_split)
            
            patterns.append(MatchResult(
                pattern_type=PatternType.SHIFT,
                confidence=best_reduction,
                start_index=best_split - 1,
                end_index=best_split,
                parameters={
                    "change_point": best_split,
                    "before_mean": round(left_mean, 4),
                    "after_mean": round(right_mean, 4),
                    "shift_magnitude": round(right_mean - left_mean, 4)
                },
                description=f"Level shift at index {best_split}"
            ))
        
        return patterns
    
    def _find_oscillations(self, data: List[float]) -> List[MatchResult]:
        """Detect oscillating patterns (alternating high/low)."""
        patterns = []
        n = len(data)
        
        if n < 6:
            return patterns
        
        # Count sign changes in differences
        diffs = [data[i+1] - data[i] for i in range(n-1)]
        sign_changes = sum(
            1 for i in range(len(diffs)-1)
            if diffs[i] * diffs[i+1] < 0
        )
        
        oscillation_ratio = sign_changes / (n - 2) if n > 2 else 0
        
        if oscillation_ratio > 0.7:
            patterns.append(MatchResult(
                pattern_type=PatternType.OSCILLATION,
                confidence=oscillation_ratio,
                start_index=0,
                end_index=n - 1,
                parameters={
                    "sign_changes": sign_changes,
                    "oscillation_ratio": round(oscillation_ratio, 4)
                },
                description=f"Oscillating pattern ({oscillation_ratio:.1%} alternation)"
            ))
        
        return patterns
    
    def _find_mixtures(self, data: List[float]) -> List[MatchResult]:
        """Detect bimodal/mixture distributions."""
        patterns = []
        n = len(data)
        
        if n < 20:
            return patterns
        
        # Simple bimodality check using histogram gaps
        sorted_data = sorted(data)
        data_range = sorted_data[-1] - sorted_data[0]
        
        if data_range == 0:
            return patterns
        
        # Create histogram
        bins = 10
        bin_width = data_range / bins
        histogram = [0] * bins
        
        for val in data:
            bin_idx = min(int((val - sorted_data[0]) / bin_width), bins - 1)
            histogram[bin_idx] += 1
        
        # Find valleys (potential mixture)
        valleys = []
        for i in range(1, bins - 1):
            if histogram[i] < histogram[i-1] and histogram[i] < histogram[i+1]:
                if histogram[i-1] > n * 0.1 and histogram[i+1] > n * 0.1:
                    valleys.append(i)
        
        if valleys:
            # Calculate bimodality coefficient
            from statistics import mean, stdev
            m = mean(data)
            s = stdev(data) if n > 1 else 1
            
            skewness = sum((x - m) ** 3 for x in data) / (n * s ** 3) if s > 0 else 0
            kurtosis = sum((x - m) ** 4 for x in data) / (n * s ** 4) if s > 0 else 0
            
            bc = (skewness ** 2 + 1) / kurtosis if kurtosis > 0 else 0
            
            if bc > 0.5:
                patterns.append(MatchResult(
                    pattern_type=PatternType.MIXTURE,
                    confidence=min(bc, 1.0),
                    start_index=0,
                    end_index=n - 1,
                    parameters={
                        "valleys": valleys,
                        "bimodality_coefficient": round(bc, 4)
                    },
                    description=f"Bimodal distribution detected"
                ))
        
        return patterns
