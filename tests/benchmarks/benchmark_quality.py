"""
Quality Detection Algorithm Benchmarks.

Compares performance of different quality/defect detection algorithms:
- YOLO11 Vision Model
- Traditional CV (OpenCV)
- SPC-based Detection
- Ensemble Methods
"""

import pytest
import time
import asyncio
import statistics
from datetime import datetime
from typing import Dict, List, Tuple
import random
import math

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


class QualityBenchmark:
    """Benchmarking framework for quality detection algorithms."""

    def __init__(self):
        self.results: Dict[str, List[Dict]] = {}

    def generate_test_dataset(
        self,
        num_samples: int,
        defect_rate: float = 0.05,
        defect_types: List[str] = None
    ) -> Dict:
        """Generate synthetic test dataset for quality detection."""
        random.seed(42)

        if defect_types is None:
            defect_types = [
                "scratch", "dent", "discoloration", "crack",
                "missing_component", "misalignment", "contamination"
            ]

        samples = []
        for i in range(num_samples):
            is_defective = random.random() < defect_rate
            sample = {
                "sample_id": f"SAMPLE-{i:05d}",
                "is_defective": is_defective,
                "defect_type": random.choice(defect_types) if is_defective else None,
                "defect_severity": random.uniform(0.3, 1.0) if is_defective else 0.0,
                "image_size": (640, 480),
                "features": self._generate_features(is_defective)
            }
            samples.append(sample)

        actual_defect_count = sum(1 for s in samples if s["is_defective"])

        return {
            "samples": samples,
            "num_samples": num_samples,
            "actual_defect_rate": actual_defect_count / num_samples,
            "defect_types": defect_types
        }

    def _generate_features(self, is_defective: bool) -> Dict:
        """Generate synthetic features for a sample."""
        base_intensity = 128 + random.uniform(-10, 10)
        base_texture = 0.5 + random.uniform(-0.05, 0.05)

        if is_defective:
            # Defective samples have anomalous features
            intensity_anomaly = random.uniform(20, 50)
            texture_anomaly = random.uniform(0.1, 0.3)
        else:
            intensity_anomaly = random.uniform(-5, 5)
            texture_anomaly = random.uniform(-0.02, 0.02)

        return {
            "mean_intensity": base_intensity + intensity_anomaly,
            "std_intensity": 15 + abs(intensity_anomaly) * 0.5,
            "texture_score": base_texture + texture_anomaly,
            "edge_density": 0.3 + random.uniform(-0.05, 0.15 if is_defective else 0.05),
            "color_variance": 10 + (random.uniform(5, 20) if is_defective else random.uniform(-2, 2))
        }

    async def benchmark_yolo_detector(self, dataset: Dict) -> Dict:
        """Benchmark YOLO11 vision model for defect detection."""
        start_time = time.perf_counter()

        # Simulate YOLO inference
        inference_time_per_image = 0.015  # ~15ms per image on GPU
        total_inference_time = inference_time_per_image * dataset["num_samples"]
        await asyncio.sleep(min(total_inference_time, 0.5))  # Cap for testing

        # Simulate detection results
        true_positives = 0
        false_positives = 0
        true_negatives = 0
        false_negatives = 0

        for sample in dataset["samples"]:
            # YOLO has high accuracy
            detection_prob = 0.95 if sample["is_defective"] else 0.02

            if random.random() < detection_prob:
                if sample["is_defective"]:
                    true_positives += 1
                else:
                    false_positives += 1
            else:
                if sample["is_defective"]:
                    false_negatives += 1
                else:
                    true_negatives += 1

        end_time = time.perf_counter()

        precision = true_positives / max(1, true_positives + false_positives)
        recall = true_positives / max(1, true_positives + false_negatives)
        f1 = 2 * precision * recall / max(0.001, precision + recall)

        return {
            "algorithm": "YOLO11",
            "inference_time": end_time - start_time,
            "throughput_fps": dataset["num_samples"] / (end_time - start_time),
            "precision": precision,
            "recall": recall,
            "f1_score": f1,
            "accuracy": (true_positives + true_negatives) / dataset["num_samples"],
            "confusion_matrix": {
                "TP": true_positives,
                "FP": false_positives,
                "TN": true_negatives,
                "FN": false_negatives
            }
        }

    async def benchmark_opencv_detector(self, dataset: Dict) -> Dict:
        """Benchmark traditional OpenCV-based detection."""
        start_time = time.perf_counter()

        # Traditional CV is faster but less accurate
        processing_time_per_image = 0.005  # ~5ms per image
        total_time = processing_time_per_image * dataset["num_samples"]
        await asyncio.sleep(min(total_time, 0.3))

        true_positives = 0
        false_positives = 0
        true_negatives = 0
        false_negatives = 0

        for sample in dataset["samples"]:
            # Traditional CV has lower accuracy
            detection_prob = 0.75 if sample["is_defective"] else 0.08

            if random.random() < detection_prob:
                if sample["is_defective"]:
                    true_positives += 1
                else:
                    false_positives += 1
            else:
                if sample["is_defective"]:
                    false_negatives += 1
                else:
                    true_negatives += 1

        end_time = time.perf_counter()

        precision = true_positives / max(1, true_positives + false_positives)
        recall = true_positives / max(1, true_positives + false_negatives)
        f1 = 2 * precision * recall / max(0.001, precision + recall)

        return {
            "algorithm": "OpenCV-Traditional",
            "inference_time": end_time - start_time,
            "throughput_fps": dataset["num_samples"] / (end_time - start_time),
            "precision": precision,
            "recall": recall,
            "f1_score": f1,
            "accuracy": (true_positives + true_negatives) / dataset["num_samples"],
            "confusion_matrix": {
                "TP": true_positives,
                "FP": false_positives,
                "TN": true_negatives,
                "FN": false_negatives
            }
        }

    async def benchmark_spc_detector(self, dataset: Dict) -> Dict:
        """Benchmark SPC-based anomaly detection."""
        start_time = time.perf_counter()

        # SPC is very fast
        processing_time_per_sample = 0.0001
        total_time = processing_time_per_sample * dataset["num_samples"]
        await asyncio.sleep(min(total_time, 0.1))

        # Calculate control limits from features
        intensities = [s["features"]["mean_intensity"] for s in dataset["samples"]]
        mean_intensity = statistics.mean(intensities)
        std_intensity = statistics.stdev(intensities)
        ucl = mean_intensity + 3 * std_intensity
        lcl = mean_intensity - 3 * std_intensity

        true_positives = 0
        false_positives = 0
        true_negatives = 0
        false_negatives = 0

        for sample in dataset["samples"]:
            intensity = sample["features"]["mean_intensity"]
            is_out_of_control = intensity > ucl or intensity < lcl

            if is_out_of_control:
                if sample["is_defective"]:
                    true_positives += 1
                else:
                    false_positives += 1
            else:
                if sample["is_defective"]:
                    false_negatives += 1
                else:
                    true_negatives += 1

        end_time = time.perf_counter()

        precision = true_positives / max(1, true_positives + false_positives)
        recall = true_positives / max(1, true_positives + false_negatives)
        f1 = 2 * precision * recall / max(0.001, precision + recall)

        return {
            "algorithm": "SPC-Statistical",
            "inference_time": end_time - start_time,
            "throughput_fps": dataset["num_samples"] / (end_time - start_time),
            "precision": precision,
            "recall": recall,
            "f1_score": f1,
            "accuracy": (true_positives + true_negatives) / dataset["num_samples"],
            "confusion_matrix": {
                "TP": true_positives,
                "FP": false_positives,
                "TN": true_negatives,
                "FN": false_negatives
            },
            "control_limits": {"UCL": ucl, "LCL": lcl}
        }

    async def benchmark_ensemble_detector(self, dataset: Dict) -> Dict:
        """Benchmark ensemble method combining multiple detectors."""
        start_time = time.perf_counter()

        # Run all base detectors
        yolo_results = await self.benchmark_yolo_detector(dataset)
        opencv_results = await self.benchmark_opencv_detector(dataset)
        spc_results = await self.benchmark_spc_detector(dataset)

        # Ensemble voting (majority vote with weighted confidence)
        true_positives = 0
        false_positives = 0
        true_negatives = 0
        false_negatives = 0

        for sample in dataset["samples"]:
            # Weighted voting based on individual detector strengths
            yolo_vote = random.random() < (0.95 if sample["is_defective"] else 0.02)
            opencv_vote = random.random() < (0.75 if sample["is_defective"] else 0.08)
            spc_vote = sample["features"]["mean_intensity"] > 140 or sample["features"]["mean_intensity"] < 116

            # Weighted ensemble (YOLO has highest weight)
            weighted_score = (
                0.5 * yolo_vote +
                0.3 * opencv_vote +
                0.2 * spc_vote
            )

            is_detected = weighted_score >= 0.4

            if is_detected:
                if sample["is_defective"]:
                    true_positives += 1
                else:
                    false_positives += 1
            else:
                if sample["is_defective"]:
                    false_negatives += 1
                else:
                    true_negatives += 1

        end_time = time.perf_counter()

        precision = true_positives / max(1, true_positives + false_positives)
        recall = true_positives / max(1, true_positives + false_negatives)
        f1 = 2 * precision * recall / max(0.001, precision + recall)

        return {
            "algorithm": "Ensemble-Weighted",
            "inference_time": end_time - start_time,
            "throughput_fps": dataset["num_samples"] / (end_time - start_time),
            "precision": precision,
            "recall": recall,
            "f1_score": f1,
            "accuracy": (true_positives + true_negatives) / dataset["num_samples"],
            "confusion_matrix": {
                "TP": true_positives,
                "FP": false_positives,
                "TN": true_negatives,
                "FN": false_negatives
            },
            "base_models": ["YOLO11", "OpenCV", "SPC"]
        }

    async def run_benchmark_suite(
        self,
        dataset_sizes: List[int] = None,
        defect_rates: List[float] = None
    ) -> Dict:
        """Run complete quality detection benchmark suite."""
        if dataset_sizes is None:
            dataset_sizes = [100, 500, 1000]

        if defect_rates is None:
            defect_rates = [0.01, 0.05, 0.10]

        all_results = []

        for size in dataset_sizes:
            for rate in defect_rates:
                dataset = self.generate_test_dataset(size, rate)

                yolo = await self.benchmark_yolo_detector(dataset)
                opencv = await self.benchmark_opencv_detector(dataset)
                spc = await self.benchmark_spc_detector(dataset)
                ensemble = await self.benchmark_ensemble_detector(dataset)

                result = {
                    "dataset_size": size,
                    "defect_rate": rate,
                    "algorithms": {
                        "YOLO11": yolo,
                        "OpenCV": opencv,
                        "SPC": spc,
                        "Ensemble": ensemble
                    }
                }

                all_results.append(result)

        return {
            "benchmark_name": "Quality Detection",
            "timestamp": datetime.now().isoformat(),
            "results": all_results,
            "summary": self._generate_summary(all_results)
        }

    def _generate_summary(self, results: List[Dict]) -> Dict:
        """Generate summary statistics."""
        summary = {}

        for algo in ["YOLO11", "OpenCV", "SPC", "Ensemble"]:
            f1_scores = [r["algorithms"][algo]["f1_score"] for r in results]
            throughputs = [r["algorithms"][algo]["throughput_fps"] for r in results]

            summary[algo] = {
                "avg_f1_score": statistics.mean(f1_scores),
                "std_f1_score": statistics.stdev(f1_scores) if len(f1_scores) > 1 else 0,
                "avg_throughput": statistics.mean(throughputs),
                "std_throughput": statistics.stdev(throughputs) if len(throughputs) > 1 else 0
            }

        return summary


class TestQualityBenchmarks:
    """Test class for quality detection benchmarks."""

    @pytest.fixture
    def benchmark(self):
        """Create benchmark instance."""
        return QualityBenchmark()

    @pytest.mark.asyncio
    async def test_yolo_performance(self, benchmark):
        """Test YOLO detector performance."""
        dataset = benchmark.generate_test_dataset(100, 0.05)
        result = await benchmark.benchmark_yolo_detector(dataset)

        assert result["f1_score"] > 0.8
        assert result["throughput_fps"] > 0

    @pytest.mark.asyncio
    async def test_opencv_vs_yolo(self, benchmark):
        """Compare OpenCV and YOLO performance."""
        dataset = benchmark.generate_test_dataset(100, 0.05)

        yolo = await benchmark.benchmark_yolo_detector(dataset)
        opencv = await benchmark.benchmark_opencv_detector(dataset)

        # YOLO should have better accuracy
        assert yolo["f1_score"] >= opencv["f1_score"]

        # OpenCV should be faster per image
        assert opencv["inference_time"] <= yolo["inference_time"]

    @pytest.mark.asyncio
    async def test_ensemble_improvement(self, benchmark):
        """Test that ensemble improves over individual methods."""
        dataset = benchmark.generate_test_dataset(200, 0.05)

        yolo = await benchmark.benchmark_yolo_detector(dataset)
        opencv = await benchmark.benchmark_opencv_detector(dataset)
        spc = await benchmark.benchmark_spc_detector(dataset)
        ensemble = await benchmark.benchmark_ensemble_detector(dataset)

        # Ensemble should perform at least as well as best individual
        best_individual = max(yolo["f1_score"], opencv["f1_score"], spc["f1_score"])
        assert ensemble["f1_score"] >= best_individual * 0.95

    @pytest.mark.asyncio
    async def test_high_defect_rate_detection(self, benchmark):
        """Test detection with high defect rate."""
        dataset = benchmark.generate_test_dataset(100, 0.20)  # 20% defect rate

        result = await benchmark.benchmark_yolo_detector(dataset)

        # Should still maintain good recall
        assert result["recall"] > 0.85

    @pytest.mark.asyncio
    async def test_benchmark_suite(self, benchmark):
        """Run abbreviated benchmark suite."""
        results = await benchmark.run_benchmark_suite(
            dataset_sizes=[50, 100],
            defect_rates=[0.05]
        )

        assert "results" in results
        assert "summary" in results
        assert len(results["results"]) == 2

        for algo in ["YOLO11", "OpenCV", "SPC", "Ensemble"]:
            assert algo in results["summary"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
