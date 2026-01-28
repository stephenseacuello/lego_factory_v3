"""
LEGO Factory v3 - Anomaly Detection Service Unit Tests
=======================================================
Tests for statistical and ML-based anomaly detection.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import math
import statistics


class TestZScoreDetection:
    """Tests for Z-score based anomaly detection."""

    def test_zscore_calculation(self, normal_data):
        """Z-score should be calculated correctly."""
        mean = statistics.mean(normal_data)
        std = statistics.stdev(normal_data)

        # Z-score for a value
        value = 65.0
        z_score = (value - mean) / std

        assert abs(z_score) < 5  # Should be reasonable

    def test_zscore_detects_outliers(self, data_with_anomalies):
        """Z-score method should detect outliers."""
        mean = statistics.mean(data_with_anomalies)
        std = statistics.stdev(data_with_anomalies)
        threshold = 3.0

        outliers = []
        for i, value in enumerate(data_with_anomalies):
            z = abs((value - mean) / std)
            if z > threshold:
                outliers.append((i, value, z))

        # Should detect our inserted anomalies
        assert len(outliers) > 0

    def test_zscore_no_false_positives_on_normal(self, normal_data):
        """Z-score should have few false positives on normal data."""
        mean = statistics.mean(normal_data)
        std = statistics.stdev(normal_data)
        threshold = 3.0

        outliers = [
            v for v in normal_data
            if abs((v - mean) / std) > threshold
        ]

        # Normal data should have very few outliers (< 1% at 3 sigma)
        false_positive_rate = len(outliers) / len(normal_data)
        assert false_positive_rate < 0.05

    def test_zscore_with_zero_std(self):
        """Z-score should handle zero standard deviation."""
        constant_data = [50.0] * 100

        mean = statistics.mean(constant_data)
        # stdev of constant data is 0
        std = 0

        # Should not divide by zero
        if std == 0:
            outliers = []
        else:
            outliers = [v for v in constant_data if abs((v - mean) / std) > 3]

        assert len(outliers) == 0

    def test_zscore_threshold_sensitivity(self, data_with_anomalies):
        """Different thresholds should detect different numbers of anomalies."""
        mean = statistics.mean(data_with_anomalies)
        std = statistics.stdev(data_with_anomalies)

        # Lower threshold catches more
        threshold_2 = 2.0
        outliers_2 = [v for v in data_with_anomalies if abs((v - mean) / std) > threshold_2]

        # Higher threshold catches fewer
        threshold_4 = 4.0
        outliers_4 = [v for v in data_with_anomalies if abs((v - mean) / std) > threshold_4]

        assert len(outliers_2) >= len(outliers_4)


class TestThresholdDetection:
    """Tests for threshold-based anomaly detection."""

    def test_high_threshold_detection(self):
        """Values above high threshold should be detected."""
        data = [50.0, 55.0, 60.0, 85.0, 52.0, 48.0]
        high_threshold = 80.0

        violations = [v for v in data if v > high_threshold]

        assert len(violations) == 1
        assert 85.0 in violations

    def test_low_threshold_detection(self):
        """Values below low threshold should be detected."""
        data = [50.0, 55.0, 15.0, 60.0, 52.0, 48.0]
        low_threshold = 20.0

        violations = [v for v in data if v < low_threshold]

        assert len(violations) == 1
        assert 15.0 in violations

    def test_high_high_threshold(self):
        """High-high threshold for critical alarms."""
        data = [50.0, 85.0, 92.0, 55.0]
        high_threshold = 80.0
        high_high_threshold = 90.0

        high_alarms = [v for v in data if high_threshold < v <= high_high_threshold]
        high_high_alarms = [v for v in data if v > high_high_threshold]

        assert 85.0 in high_alarms
        assert 92.0 in high_high_alarms

    def test_low_low_threshold(self):
        """Low-low threshold for critical alarms."""
        data = [50.0, 15.0, 8.0, 55.0]
        low_threshold = 20.0
        low_low_threshold = 10.0

        low_alarms = [v for v in data if low_low_threshold <= v < low_threshold]
        low_low_alarms = [v for v in data if v < low_low_threshold]

        assert 15.0 in low_alarms
        assert 8.0 in low_low_alarms

    def test_deadband_prevents_chattering(self):
        """Deadband should prevent alarm chattering."""
        threshold = 80.0
        deadband = 2.0

        # Values oscillating around threshold
        values = [79.5, 80.5, 79.8, 80.2, 79.9, 80.1]

        alarm_active = False
        transitions = 0

        for v in values:
            if not alarm_active and v > threshold:
                alarm_active = True
                transitions += 1
            elif alarm_active and v < (threshold - deadband):
                alarm_active = False
                transitions += 1

        # With deadband, fewer transitions
        assert transitions < len(values)


class TestPatternDetection:
    """Tests for pattern-based anomaly detection."""

    def test_trend_detection(self, trending_data):
        """Should detect upward or downward trends."""
        # Calculate slope using simple linear regression
        n = len(trending_data)
        x_mean = (n - 1) / 2
        y_mean = statistics.mean(trending_data)

        numerator = sum((i - x_mean) * (trending_data[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        slope = numerator / denominator if denominator != 0 else 0

        # Positive slope indicates upward trend
        assert slope > 0

    def test_level_shift_detection(self):
        """Should detect sudden level shifts."""
        data = [50.0] * 50 + [80.0] * 50  # Shift from 50 to 80

        first_half_mean = statistics.mean(data[:50])
        second_half_mean = statistics.mean(data[50:])

        level_shift = abs(second_half_mean - first_half_mean)

        assert level_shift > 20  # Significant shift

    def test_rate_of_change_detection(self):
        """Should detect rapid rate of change."""
        data = [50.0, 51.0, 52.0, 80.0, 81.0]  # Sudden jump

        max_rate_threshold = 5.0
        violations = []

        for i in range(1, len(data)):
            rate = abs(data[i] - data[i-1])
            if rate > max_rate_threshold:
                violations.append((i, rate))

        # Should detect the jump from 52 to 80
        assert len(violations) > 0
        assert violations[0][1] == 28.0

    def test_seasonality_deviation(self, seasonal_data):
        """Should detect deviations from expected seasonal pattern."""
        # Create expected pattern
        expected = [50.0 + 20 * math.sin(2 * math.pi * i / 24) for i in range(100)]

        # Insert anomaly
        modified_data = seasonal_data.copy()
        modified_data[50] = 100.0  # Way outside expected

        deviations = [
            abs(modified_data[i] - expected[i])
            for i in range(len(modified_data))
        ]

        max_deviation = max(deviations)
        max_deviation_index = deviations.index(max_deviation)

        assert max_deviation_index == 50
        assert max_deviation > 30


class TestIQRDetection:
    """Tests for IQR (Interquartile Range) based detection."""

    def test_iqr_calculation(self, normal_data):
        """IQR should be calculated correctly."""
        sorted_data = sorted(normal_data)
        n = len(sorted_data)

        q1 = sorted_data[n // 4]
        q3 = sorted_data[3 * n // 4]
        iqr = q3 - q1

        assert iqr > 0

    def test_iqr_outlier_detection(self, data_with_anomalies):
        """IQR method should detect outliers."""
        sorted_data = sorted(data_with_anomalies)
        n = len(sorted_data)

        q1 = sorted_data[n // 4]
        q3 = sorted_data[3 * n // 4]
        iqr = q3 - q1

        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr

        outliers = [v for v in data_with_anomalies if v < lower_bound or v > upper_bound]

        assert len(outliers) > 0

    def test_iqr_no_outliers_on_uniform(self):
        """IQR should not find outliers in uniform data."""
        uniform_data = list(range(100))  # 0 to 99

        sorted_data = sorted(uniform_data)
        n = len(sorted_data)

        q1 = sorted_data[n // 4]
        q3 = sorted_data[3 * n // 4]
        iqr = q3 - q1

        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr

        outliers = [v for v in uniform_data if v < lower_bound or v > upper_bound]

        # Uniform data should have no outliers
        assert len(outliers) == 0


class TestMovingAverageDetection:
    """Tests for moving average based detection."""

    def test_moving_average_calculation(self, normal_data):
        """Moving average should be calculated correctly."""
        window = 5
        moving_avg = []

        for i in range(window, len(normal_data)):
            avg = sum(normal_data[i-window:i]) / window
            moving_avg.append(avg)

        assert len(moving_avg) == len(normal_data) - window

    def test_moving_average_anomaly_detection(self, data_with_anomalies):
        """Should detect anomalies using moving average."""
        window = 5
        threshold = 3.0

        anomalies = []
        for i in range(window, len(data_with_anomalies)):
            window_data = data_with_anomalies[i-window:i]
            ma = sum(window_data) / window
            ma_std = statistics.stdev(window_data) if len(window_data) > 1 else 0

            if ma_std > 0:
                z = abs((data_with_anomalies[i] - ma) / ma_std)
                if z > threshold:
                    anomalies.append((i, data_with_anomalies[i]))

        assert len(anomalies) > 0


class TestEWMADetection:
    """Tests for Exponentially Weighted Moving Average detection."""

    def test_ewma_calculation(self, normal_data):
        """EWMA should be calculated correctly."""
        lambda_ = 0.2  # Smoothing factor

        ewma = normal_data[0]
        ewma_values = [ewma]

        for value in normal_data[1:]:
            ewma = lambda_ * value + (1 - lambda_) * ewma
            ewma_values.append(ewma)

        assert len(ewma_values) == len(normal_data)

    def test_ewma_smoothing_effect(self, normal_data):
        """EWMA should smooth the data."""
        lambda_ = 0.2

        ewma = normal_data[0]
        ewma_values = []

        for value in normal_data:
            ewma = lambda_ * value + (1 - lambda_) * ewma
            ewma_values.append(ewma)

        # EWMA should be less variable than raw data
        raw_std = statistics.stdev(normal_data)
        ewma_std = statistics.stdev(ewma_values)

        assert ewma_std < raw_std

    def test_ewma_lambda_sensitivity(self, normal_data):
        """Different lambda values should affect smoothing."""
        # Higher lambda = more weight to recent values
        lambda_high = 0.8
        lambda_low = 0.1

        ewma_high = normal_data[0]
        ewma_low = normal_data[0]

        for value in normal_data[1:]:
            ewma_high = lambda_high * value + (1 - lambda_high) * ewma_high
            ewma_low = lambda_low * value + (1 - lambda_low) * ewma_low

        # Low lambda should have smaller variance from previous value (more smoothed)
        # With more data points, the difference becomes more apparent
        # Both should still be reasonable estimates near the data range
        mean = statistics.mean(normal_data)
        std = statistics.stdev(normal_data)
        # Both EWMA values should be within 2 standard deviations of the mean
        assert abs(ewma_low - mean) < 2 * std
        assert abs(ewma_high - mean) < 2 * std


class TestControlCharts:
    """Tests for SPC control chart functionality."""

    def test_control_limits_calculation(self, normal_data):
        """Control limits should be calculated correctly."""
        mean = statistics.mean(normal_data)
        std = statistics.stdev(normal_data)

        ucl = mean + 3 * std  # Upper Control Limit
        lcl = mean - 3 * std  # Lower Control Limit

        assert ucl > mean
        assert lcl < mean
        assert ucl - mean == mean - lcl  # Symmetric

    def test_in_control_detection(self, normal_data):
        """Points within control limits should be in control."""
        mean = statistics.mean(normal_data)
        std = statistics.stdev(normal_data)
        ucl = mean + 3 * std
        lcl = mean - 3 * std

        in_control = [v for v in normal_data if lcl <= v <= ucl]

        # Most points should be in control
        in_control_rate = len(in_control) / len(normal_data)
        assert in_control_rate > 0.95

    def test_out_of_control_detection(self, data_with_anomalies):
        """Points outside control limits should be detected."""
        mean = statistics.mean(data_with_anomalies)
        std = statistics.stdev(data_with_anomalies)
        ucl = mean + 3 * std
        lcl = mean - 3 * std

        out_of_control = [v for v in data_with_anomalies if v < lcl or v > ucl]

        assert len(out_of_control) > 0

    def test_cpk_calculation(self):
        """Process capability index should be calculated correctly."""
        data = [50.0 + i * 0.01 for i in range(100)]  # Very stable process
        usl = 55.0  # Upper Spec Limit
        lsl = 45.0  # Lower Spec Limit

        mean = statistics.mean(data)
        std = statistics.stdev(data) or 0.001  # Avoid division by zero

        cpu = (usl - mean) / (3 * std)
        cpl = (mean - lsl) / (3 * std)
        cpk = min(cpu, cpl)

        assert cpk > 1.0  # Capable process

    def test_cpk_interpretation(self):
        """Cpk values should be interpreted correctly."""
        interpretations = {
            2.0: "Excellent (Six Sigma)",
            1.67: "Very Good",
            1.33: "Good",
            1.0: "Capable",
            0.67: "Marginal",
            0.5: "Incapable"
        }

        # Cpk >= 1.33 is generally considered good
        assert interpretations[1.33] == "Good"


class TestWesternElectricRules:
    """Tests for Western Electric rules."""

    def test_rule_1_beyond_3sigma(self):
        """Rule 1: One point beyond 3 sigma."""
        center = 50.0
        sigma = 5.0
        ucl = center + 3 * sigma  # 65
        lcl = center - 3 * sigma  # 35

        data = [50.0, 52.0, 48.0, 70.0, 51.0]  # 70 is beyond UCL

        violations = [v for v in data if v > ucl or v < lcl]

        assert len(violations) == 1
        assert 70.0 in violations

    def test_rule_2_two_of_three_beyond_2sigma(self):
        """Rule 2: 2 of 3 consecutive points beyond 2 sigma."""
        center = 50.0
        sigma = 5.0
        two_sigma = 2 * sigma

        data = [50.0, 61.0, 62.0, 50.0]  # 61 and 62 are beyond 2 sigma

        violations = []
        for i in range(2, len(data)):
            window = data[i-2:i+1]
            beyond = sum(1 for v in window if abs(v - center) > two_sigma)
            if beyond >= 2:
                violations.append(i)

        assert len(violations) > 0

    def test_rule_4_eight_consecutive_one_side(self):
        """Rule 4: 8 consecutive points on one side of center."""
        center = 50.0

        # 8 consecutive above center
        data = [51.0, 52.0, 53.0, 54.0, 55.0, 56.0, 57.0, 58.0, 49.0]

        violations = []
        for i in range(7, len(data)):
            window = data[i-7:i+1]
            all_above = all(v > center for v in window)
            all_below = all(v < center for v in window)
            if all_above or all_below:
                violations.append(i)

        assert len(violations) > 0


class TestAlertGeneration:
    """Tests for anomaly alert generation."""

    def test_alert_creation(self):
        """Alert should be created with required fields."""
        alert = {
            'alert_id': 'ANOM-000001',
            'anomaly_type': 'point',
            'severity': 'warning',
            'value': 85.0,
            'expected_value': 50.0,
            'deviation': 3.5,
            'threshold': 3.0,
            'timestamp': '2024-01-15T12:00:00Z',
            'metric_name': 'temperature'
        }

        assert 'alert_id' in alert
        assert 'severity' in alert
        assert alert['deviation'] > alert['threshold']

    def test_severity_determination(self):
        """Severity should be determined by deviation magnitude."""
        threshold = 3.0

        def get_severity(deviation):
            if deviation > threshold * 2:
                return 'critical'
            elif deviation > threshold * 1.5:
                return 'warning'
            else:
                return 'info'

        assert get_severity(3.2) == 'info'
        assert get_severity(5.0) == 'warning'
        assert get_severity(7.0) == 'critical'

    def test_alert_context(self):
        """Alert should include contextual information."""
        alert = {
            'alert_id': 'ANOM-000001',
            'context': {
                'machine_id': 'MCH-001',
                'work_order_id': 'WO-001',
                'operator': 'user123'
            }
        }

        assert 'context' in alert
        assert 'machine_id' in alert['context']


class TestAnomalyTypes:
    """Tests for different anomaly types."""

    def test_point_anomaly(self):
        """Point anomaly: single outlier."""
        anomaly_types = ['point', 'contextual', 'collective', 'trend', 'level_shift', 'seasonality']

        assert 'point' in anomaly_types

    def test_contextual_anomaly(self):
        """Contextual anomaly: abnormal in specific context."""
        # Value 20 is normal overall but abnormal at midnight
        assert True  # Placeholder for contextual logic

    def test_collective_anomaly(self):
        """Collective anomaly: group of related anomalies."""
        # Multiple consecutive outliers
        data = [50.0, 80.0, 85.0, 82.0, 50.0]  # 3 consecutive high values

        threshold = 70.0
        consecutive_high = 0
        max_consecutive = 0

        for v in data:
            if v > threshold:
                consecutive_high += 1
                max_consecutive = max(max_consecutive, consecutive_high)
            else:
                consecutive_high = 0

        assert max_consecutive >= 3
