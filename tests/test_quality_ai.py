"""
Quality AI Module Tests.

Tests for Phase 5 AI/ML for Quality components:
- Self-Supervised Learning (SSL)
- Multimodal Quality Prediction
- XAI Integration
"""

import unittest
import sys
import os
from datetime import datetime
from typing import Dict, Any, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestContrastiveLearning(unittest.TestCase):
    """Tests for contrastive learning components."""

    def setUp(self):
        """Set up test fixtures."""
        from dashboard.services.vision.ssl.contrastive_learning import (
            ContrastiveAugmentation, NTXentLoss, ContrastiveLearner, DefectContrastive
        )
        self.ContrastiveAugmentation = ContrastiveAugmentation
        self.NTXentLoss = NTXentLoss
        self.ContrastiveLearner = ContrastiveLearner
        self.DefectContrastive = DefectContrastive

    def test_augmentation_creation(self):
        """Test augmentation pipeline creation."""
        augmenter = self.ContrastiveAugmentation()

        self.assertIsNotNone(augmenter)
        self.assertGreater(len(augmenter.transforms), 0)

    def test_augmentation_apply(self):
        """Test applying augmentations to image."""
        augmenter = self.ContrastiveAugmentation()

        # Mock image (as feature vector)
        image = [[0.5] * 64 for _ in range(64)]

        aug1, aug2 = augmenter.create_pair(image)

        self.assertIsNotNone(aug1)
        self.assertIsNotNone(aug2)

    def test_nt_xent_loss(self):
        """Test NT-Xent contrastive loss."""
        loss_fn = self.NTXentLoss(temperature=0.5)

        # Mock embeddings
        z_i = [[0.1] * 128 for _ in range(32)]
        z_j = [[0.2] * 128 for _ in range(32)]

        loss = loss_fn.compute(z_i, z_j)

        self.assertIsInstance(loss, float)
        self.assertGreater(loss, 0)

    def test_contrastive_learner(self):
        """Test contrastive learner training."""
        learner = self.ContrastiveLearner(
            backbone="resnet18",
            projection_dim=128
        )

        # Mock batch of images
        batch = [[[0.5] * 64 for _ in range(64)] for _ in range(8)]

        result = learner.train_step(batch)

        self.assertIn("loss", result)
        self.assertIn("embeddings", result)

    def test_defect_contrastive(self):
        """Test defect-specific contrastive learning."""
        model = self.DefectContrastive()

        # Train on manufacturing images
        images = [[[0.5] * 64 for _ in range(64)] for _ in range(16)]

        result = model.pretrain(images, epochs=2)

        self.assertIn("final_loss", result)
        self.assertIn("epoch_losses", result)

    def test_feature_extraction(self):
        """Test feature extraction after pretraining."""
        model = self.DefectContrastive()

        # Extract features
        image = [[0.5] * 64 for _ in range(64)]
        features = model.extract_features(image)

        self.assertIsInstance(features, list)
        self.assertGreater(len(features), 0)


class TestMaskedAutoencoder(unittest.TestCase):
    """Tests for Masked Autoencoder components."""

    def setUp(self):
        """Set up test fixtures."""
        from dashboard.services.vision.ssl.masked_autoencoder import (
            PatchEmbed, MAEEncoder, MAEDecoder, MaskedAutoencoder, ManufacturingMAE
        )
        self.PatchEmbed = PatchEmbed
        self.MAEEncoder = MAEEncoder
        self.MAEDecoder = MAEDecoder
        self.MaskedAutoencoder = MaskedAutoencoder
        self.ManufacturingMAE = ManufacturingMAE

    def test_patch_embedding(self):
        """Test patch embedding creation."""
        patch_embed = self.PatchEmbed(
            img_size=224,
            patch_size=16,
            embed_dim=768
        )

        self.assertEqual(patch_embed.num_patches, 196)  # 14x14

    def test_mae_encoder(self):
        """Test MAE encoder."""
        encoder = self.MAEEncoder(
            embed_dim=768,
            depth=6,
            num_heads=8
        )

        # Mock patches
        patches = [[0.5] * 768 for _ in range(196)]
        mask = [True] * 147 + [False] * 49  # 75% masking

        encoded, mask_indices = encoder.encode(patches, mask)

        self.assertIsNotNone(encoded)

    def test_mae_decoder(self):
        """Test MAE decoder."""
        decoder = self.MAEDecoder(
            embed_dim=768,
            decoder_embed_dim=512,
            depth=4
        )

        # Mock encoded patches
        encoded = [[0.5] * 512 for _ in range(49)]

        decoded = decoder.decode(encoded, num_patches=196)

        self.assertEqual(len(decoded), 196)

    def test_masked_autoencoder(self):
        """Test full MAE model."""
        mae = self.MaskedAutoencoder(
            img_size=224,
            patch_size=16,
            mask_ratio=0.75
        )

        # Mock image
        image = [[0.5] * 224 for _ in range(224)]

        result = mae.forward(image)

        self.assertIn("loss", result)
        self.assertIn("reconstruction", result)
        self.assertIn("mask", result)

    def test_manufacturing_mae(self):
        """Test manufacturing-specific MAE."""
        mae = self.ManufacturingMAE()

        # Train on manufacturing images
        images = [[[0.5] * 224 for _ in range(224)] for _ in range(8)]

        result = mae.pretrain(images, epochs=2)

        self.assertIn("final_loss", result)

    def test_mae_feature_extraction(self):
        """Test feature extraction from pretrained MAE."""
        mae = self.ManufacturingMAE()

        image = [[0.5] * 224 for _ in range(224)]
        features = mae.extract_features(image)

        self.assertIsNotNone(features)


class TestAnomalySSL(unittest.TestCase):
    """Tests for SSL-based anomaly detection."""

    def setUp(self):
        """Set up test fixtures."""
        from dashboard.services.vision.ssl.anomaly_ssl import (
            FeatureMemoryBank, PatchCore, SSLAnomalyDetector, ManufacturingAnomalySSL
        )
        self.FeatureMemoryBank = FeatureMemoryBank
        self.PatchCore = PatchCore
        self.SSLAnomalyDetector = SSLAnomalyDetector
        self.ManufacturingAnomalySSL = ManufacturingAnomalySSL

    def test_feature_memory_bank(self):
        """Test feature memory bank."""
        bank = self.FeatureMemoryBank(max_size=1000)

        # Add features
        for i in range(100):
            bank.add([0.1 * i] * 128)

        self.assertEqual(len(bank), 100)

    def test_memory_bank_coreset(self):
        """Test coreset sampling from memory bank."""
        bank = self.FeatureMemoryBank(max_size=1000)

        for i in range(500):
            bank.add([0.1 * (i % 10)] * 128)

        coreset = bank.get_coreset(size=50)

        self.assertEqual(len(coreset), 50)

    def test_patchcore(self):
        """Test PatchCore anomaly detection."""
        patchcore = self.PatchCore()

        # Train on normal images
        normal_images = [[[0.5] * 64 for _ in range(64)] for _ in range(20)]
        patchcore.fit(normal_images)

        # Test on anomalous image
        test_image = [[0.9] * 64 for _ in range(64)]
        score = patchcore.score(test_image)

        self.assertIsInstance(score, float)

    def test_ssl_anomaly_detector(self):
        """Test SSL-based anomaly detector."""
        detector = self.SSLAnomalyDetector()

        # Train on normal samples
        normal = [[[0.5] * 64 for _ in range(64)] for _ in range(30)]
        detector.train(normal)

        # Detect anomaly
        result = detector.detect([[0.9] * 64 for _ in range(64)])

        self.assertIn("score", result)
        self.assertIn("is_anomaly", result)

    def test_manufacturing_anomaly_ssl(self):
        """Test manufacturing-specific anomaly detection."""
        detector = self.ManufacturingAnomalySSL()

        # Train on good parts
        good_parts = [[[0.5] * 64 for _ in range(64)] for _ in range(50)]
        detector.train_on_good_parts(good_parts)

        # Detect defect
        result = detector.detect_defect([[0.9] * 64 for _ in range(64)])

        self.assertIn("defect_score", result)
        self.assertIn("defect_type", result)
        self.assertIn("confidence", result)


class TestSensorFusion(unittest.TestCase):
    """Tests for multimodal sensor fusion."""

    def setUp(self):
        """Set up test fixtures."""
        from dashboard.services.quality.multimodal.sensor_fusion import (
            SensorEncoder, VisionEncoder, FusionModule,
            SensorFusion, ManufacturingSensorFusion
        )
        self.SensorEncoder = SensorEncoder
        self.VisionEncoder = VisionEncoder
        self.FusionModule = FusionModule
        self.SensorFusion = SensorFusion
        self.ManufacturingSensorFusion = ManufacturingSensorFusion

    def test_sensor_encoder(self):
        """Test sensor data encoder."""
        encoder = self.SensorEncoder(input_dim=10, hidden_dim=64, output_dim=128)

        sensor_data = [0.5] * 10
        encoded = encoder.encode(sensor_data)

        self.assertEqual(len(encoded), 128)

    def test_vision_encoder(self):
        """Test vision encoder."""
        encoder = self.VisionEncoder(output_dim=128)

        image = [[0.5] * 64 for _ in range(64)]
        encoded = encoder.encode(image)

        self.assertEqual(len(encoded), 128)

    def test_fusion_module(self):
        """Test multimodal fusion module."""
        fusion = self.FusionModule(sensor_dim=128, vision_dim=128, output_dim=256)

        sensor_features = [0.5] * 128
        vision_features = [0.5] * 128

        fused = fusion.fuse(sensor_features, vision_features)

        self.assertEqual(len(fused), 256)

    def test_sensor_fusion(self):
        """Test complete sensor fusion pipeline."""
        fusion = self.SensorFusion()

        result = fusion.fuse_modalities(
            sensor_data=[0.5] * 10,
            image=[[0.5] * 64 for _ in range(64)]
        )

        self.assertIn("fused_features", result)
        self.assertIn("sensor_contribution", result)
        self.assertIn("vision_contribution", result)

    def test_manufacturing_sensor_fusion(self):
        """Test manufacturing-specific sensor fusion."""
        fusion = self.ManufacturingSensorFusion()

        result = fusion.predict_quality(
            temperature=[200.0, 205.0, 210.0],
            vibration=[0.1, 0.15, 0.12],
            layer_image=[[0.5] * 64 for _ in range(64)]
        )

        self.assertIn("quality_score", result)
        self.assertIn("defect_probability", result)


class TestAttentionFusion(unittest.TestCase):
    """Tests for cross-modal attention fusion."""

    def setUp(self):
        """Set up test fixtures."""
        from dashboard.services.quality.multimodal.attention_fusion import (
            ModalityEncoder, MultiHeadAttention, CrossModalAttention,
            FusionTransformer, ManufacturingAttentionFusion
        )
        self.ModalityEncoder = ModalityEncoder
        self.MultiHeadAttention = MultiHeadAttention
        self.CrossModalAttention = CrossModalAttention
        self.FusionTransformer = FusionTransformer
        self.ManufacturingAttentionFusion = ManufacturingAttentionFusion

    def test_modality_encoder(self):
        """Test modality encoder."""
        encoder = self.ModalityEncoder(
            input_dim=10,
            hidden_dim=64,
            output_dim=128,
            modality="sensor"
        )

        data = [0.5] * 10
        encoded = encoder.encode(data)

        self.assertEqual(len(encoded), 128)

    def test_multihead_attention(self):
        """Test multi-head attention."""
        attention = self.MultiHeadAttention(embed_dim=128, num_heads=8)

        query = [[0.5] * 128 for _ in range(10)]
        key = [[0.5] * 128 for _ in range(10)]
        value = [[0.5] * 128 for _ in range(10)]

        output, weights = attention.forward(query, key, value)

        self.assertEqual(len(output), 10)
        self.assertEqual(len(weights), 10)

    def test_cross_modal_attention(self):
        """Test cross-modal attention."""
        cross_attn = self.CrossModalAttention(embed_dim=128, num_heads=8)

        modality_a = [[0.5] * 128 for _ in range(10)]
        modality_b = [[0.5] * 128 for _ in range(10)]

        fused = cross_attn.forward(modality_a, modality_b)

        self.assertIsNotNone(fused)

    def test_fusion_transformer(self):
        """Test fusion transformer."""
        transformer = self.FusionTransformer(
            embed_dim=128,
            num_heads=8,
            num_layers=4
        )

        modalities = {
            "sensor": [[0.5] * 128 for _ in range(10)],
            "vision": [[0.5] * 128 for _ in range(10)],
        }

        output = transformer.forward(modalities)

        self.assertIn("fused_representation", output)
        self.assertIn("attention_weights", output)

    def test_manufacturing_attention_fusion(self):
        """Test manufacturing-specific attention fusion."""
        fusion = self.ManufacturingAttentionFusion()

        result = fusion.predict_with_explanation(
            sensor_sequence=[[0.5] * 10 for _ in range(20)],
            image_sequence=[[[0.5] * 64 for _ in range(64)] for _ in range(5)]
        )

        self.assertIn("prediction", result)
        self.assertIn("attention_analysis", result)
        self.assertIn("modality_importance", result)


class TestTemporalFusion(unittest.TestCase):
    """Tests for temporal fusion components."""

    def setUp(self):
        """Set up test fixtures."""
        from dashboard.services.quality.multimodal.temporal_fusion import (
            TemporalSequence, TemporalFeature, TimeSeriesEncoder,
            TemporalFusion, SpatioTemporalFusion
        )
        self.TemporalSequence = TemporalSequence
        self.TemporalFeature = TemporalFeature
        self.TimeSeriesEncoder = TimeSeriesEncoder
        self.TemporalFusion = TemporalFusion
        self.SpatioTemporalFusion = SpatioTemporalFusion

    def test_temporal_feature(self):
        """Test temporal feature creation."""
        feature = self.TemporalFeature(
            features=[0.5] * 64,
            timestamp=datetime.now(),
            timestep=0,
            modality="sensor"
        )

        self.assertEqual(len(feature.features), 64)

    def test_temporal_sequence(self):
        """Test temporal sequence creation."""
        features = [
            self.TemporalFeature([0.5] * 64, datetime.now(), i, "sensor")
            for i in range(10)
        ]

        sequence = self.TemporalSequence(
            features=features,
            modality="sensor",
            start_time=datetime.now(),
            end_time=datetime.now()
        )

        self.assertEqual(len(sequence.features), 10)

    def test_temporal_sequence_statistics(self):
        """Test temporal sequence statistics."""
        features = [
            self.TemporalFeature([0.1 * i] * 10, datetime.now(), i, "sensor")
            for i in range(10)
        ]

        sequence = self.TemporalSequence(
            features=features,
            modality="sensor",
            start_time=datetime.now(),
            end_time=datetime.now()
        )

        stats = sequence.get_statistics()

        self.assertIn("mean", stats)
        self.assertIn("std", stats)
        self.assertIn("min", stats)
        self.assertIn("max", stats)

    def test_timeseries_encoder(self):
        """Test time series encoder."""
        encoder = self.TimeSeriesEncoder(
            input_dim=64,
            hidden_dim=128,
            output_dim=256
        )

        features = [
            self.TemporalFeature([0.5] * 64, datetime.now(), i, "sensor")
            for i in range(10)
        ]

        sequence = self.TemporalSequence(
            features=features,
            modality="sensor",
            start_time=datetime.now(),
            end_time=datetime.now()
        )

        encoded = encoder.encode(sequence)

        self.assertIn("final_state", encoded)

    def test_temporal_fusion(self):
        """Test temporal fusion of sensor and image sequences."""
        fusion = self.TemporalFusion()

        sensor_features = [
            self.TemporalFeature([0.5] * 64, datetime.now(), i, "sensor")
            for i in range(20)
        ]

        sensor_sequence = self.TemporalSequence(
            features=sensor_features,
            modality="sensor",
            start_time=datetime.now(),
            end_time=datetime.now()
        )

        image_sequence = [[[0.5] * 64 for _ in range(64)] for _ in range(5)]

        result = fusion.fuse(sensor_sequence, image_sequence)

        self.assertIn("fused_features", result)

    def test_spatio_temporal_fusion(self):
        """Test spatio-temporal fusion for layer-by-layer analysis."""
        fusion = self.SpatioTemporalFusion()

        # Create layer data
        layer_images = [[[0.5] * 64 for _ in range(64)] for _ in range(10)]

        layer_sensors = []
        for i in range(10):
            features = [
                self.TemporalFeature([0.5] * 64, datetime.now(), j, "sensor")
                for j in range(5)
            ]
            layer_sensors.append(self.TemporalSequence(
                features=features,
                modality="sensor",
                start_time=datetime.now(),
                end_time=datetime.now()
            ))

        result = fusion.predict_part_quality(layer_images, layer_sensors)

        self.assertIn("part_quality", result)
        self.assertIn("layer_qualities", result)
        self.assertIn("quality_grade", result)


class TestXAIIntegration(unittest.TestCase):
    """Tests for Explainable AI integration."""

    def setUp(self):
        """Set up test fixtures."""
        from dashboard.services.ai.explainability.shap_explainer import (
            SHAPExplainer, ManufacturingSHAP
        )
        from dashboard.services.ai.explainability.lime_explainer import (
            LIMEExplainer, ManufacturingLIME
        )
        self.SHAPExplainer = SHAPExplainer
        self.ManufacturingSHAP = ManufacturingSHAP
        self.LIMEExplainer = LIMEExplainer
        self.ManufacturingLIME = ManufacturingLIME

    def test_shap_explainer(self):
        """Test SHAP explainer."""
        explainer = self.SHAPExplainer()

        # Mock model and data
        def mock_model(x):
            return sum(x) / len(x)

        features = [0.5] * 10
        feature_names = [f"feature_{i}" for i in range(10)]

        result = explainer.explain(mock_model, features, feature_names)

        self.assertIn("shap_values", result)
        self.assertIn("base_value", result)

    def test_manufacturing_shap(self):
        """Test manufacturing-specific SHAP."""
        explainer = self.ManufacturingSHAP()

        result = explainer.explain_quality_prediction(
            features={
                "temperature": 210.0,
                "speed": 60.0,
                "layer_height": 0.2,
                "infill": 20.0,
            },
            prediction=0.85
        )

        self.assertIn("feature_importance", result)
        self.assertIn("top_contributors", result)

    def test_lime_explainer(self):
        """Test LIME explainer."""
        explainer = self.LIMEExplainer()

        # Mock model and data
        def mock_model(x):
            return [sum(xi) / len(xi) for xi in x]

        features = [0.5] * 10
        feature_names = [f"feature_{i}" for i in range(10)]

        result = explainer.explain(mock_model, features, feature_names)

        self.assertIn("explanation", result)
        self.assertIn("local_importance", result)

    def test_manufacturing_lime(self):
        """Test manufacturing-specific LIME."""
        explainer = self.ManufacturingLIME()

        image = [[0.5] * 64 for _ in range(64)]

        result = explainer.explain_defect_detection(
            image=image,
            prediction="crack",
            confidence=0.92
        )

        self.assertIn("explanation_image", result)
        self.assertIn("important_regions", result)


if __name__ == "__main__":
    unittest.main()
