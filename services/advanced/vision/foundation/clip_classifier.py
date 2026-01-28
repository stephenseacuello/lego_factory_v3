"""
CLIP Vision-Language Classifier
LegoMCP PhD-Level Manufacturing Platform

Implements OpenAI CLIP for vision-language understanding with:
- Zero-shot classification
- Image-text similarity
- Manufacturing-specific embeddings
- Multi-label classification
- Hierarchical classification
"""

import logging
import numpy as np
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import time

logger = logging.getLogger(__name__)


class CLIPModelType(Enum):
    VIT_B_32 = "ViT-B/32"  # Base, 32px patches (fastest)
    VIT_B_16 = "ViT-B/16"  # Base, 16px patches
    VIT_L_14 = "ViT-L/14"  # Large, 14px patches
    VIT_L_14_336 = "ViT-L/14@336px"  # Large, higher resolution


@dataclass
class ClassificationResult:
    """Zero-shot classification result."""
    labels: List[str]
    probabilities: List[float]
    top_label: str
    top_probability: float
    inference_time_ms: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "labels": self.labels,
            "probabilities": [float(p) for p in self.probabilities],
            "top_label": self.top_label,
            "top_probability": float(self.top_probability),
            "inference_time_ms": self.inference_time_ms,
            "metadata": self.metadata,
        }

    def get_top_k(self, k: int = 5) -> List[Tuple[str, float]]:
        """Get top-k predictions."""
        sorted_pairs = sorted(
            zip(self.labels, self.probabilities),
            key=lambda x: x[1],
            reverse=True
        )
        return sorted_pairs[:k]


@dataclass
class EmbeddingResult:
    """CLIP embedding result."""
    image_embedding: np.ndarray
    text_embeddings: Optional[np.ndarray] = None
    similarity_scores: Optional[List[float]] = None
    inference_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "embedding_dim": len(self.image_embedding),
            "similarity_scores": (
                [float(s) for s in self.similarity_scores]
                if self.similarity_scores else None
            ),
            "inference_time_ms": self.inference_time_ms,
        }


class CLIPClassifier:
    """
    CLIP vision-language classifier for manufacturing.

    Features:
    - Zero-shot image classification
    - Custom label vocabularies
    - Manufacturing-specific templates
    - Multi-label support
    - Embedding extraction for similarity search
    """

    def __init__(
        self,
        model_type: CLIPModelType = CLIPModelType.VIT_B_32,
        device: str = "cuda",
    ):
        self.model_type = model_type
        self.device = device
        self._model = None
        self._preprocess = None
        self._tokenize = None

        # Manufacturing label sets
        self.label_sets = {
            "defect_types": [
                "scratch defect",
                "crack defect",
                "dent defect",
                "chip defect",
                "surface contamination",
                "discoloration",
                "no defect",
            ],
            "lego_colors": [
                "red LEGO brick",
                "blue LEGO brick",
                "yellow LEGO brick",
                "green LEGO brick",
                "black LEGO brick",
                "white LEGO brick",
                "gray LEGO brick",
                "orange LEGO brick",
            ],
            "lego_types": [
                "standard LEGO brick",
                "LEGO plate",
                "LEGO tile",
                "LEGO slope",
                "LEGO technic beam",
                "LEGO minifigure",
                "LEGO wheel",
            ],
            "quality_grades": [
                "excellent quality product",
                "good quality product",
                "acceptable quality product",
                "poor quality product",
                "defective product",
            ],
            "assembly_states": [
                "fully assembled product",
                "partially assembled product",
                "disassembled components",
                "incorrectly assembled product",
            ],
        }

        # Prompt templates for better classification
        self.templates = [
            "a photo of {}",
            "a photo of a {}",
            "an image of {}",
            "a picture of {}",
            "{} in a manufacturing setting",
            "a close-up of {}",
        ]

    def load_model(self):
        """Load CLIP model."""
        try:
            import clip
            import torch

            self._model, self._preprocess = clip.load(
                self.model_type.value,
                device=self.device,
            )
            self._tokenize = clip.tokenize

            logger.info(f"CLIP model loaded: {self.model_type.value}")

        except ImportError:
            logger.warning("clip not installed, using mock model")
            self._model = MockCLIPModel()
            self._preprocess = lambda x: x
            self._tokenize = lambda x: x

        except Exception as e:
            logger.warning(f"Failed to load CLIP: {e}, using mock")
            self._model = MockCLIPModel()
            self._preprocess = lambda x: x
            self._tokenize = lambda x: x

    def classify(
        self,
        image: np.ndarray,
        labels: List[str],
        use_templates: bool = True,
    ) -> ClassificationResult:
        """
        Zero-shot classify image with given labels.

        Args:
            image: RGB image (H, W, 3)
            labels: List of possible class labels
            use_templates: Use prompt templates for better accuracy

        Returns:
            ClassificationResult with probabilities
        """
        if self._model is None:
            self.load_model()

        start_time = time.time()

        try:
            import clip
            import torch
            from PIL import Image

            # Prepare image
            pil_image = Image.fromarray(image)
            image_tensor = self._preprocess(pil_image).unsqueeze(0).to(self.device)

            # Prepare text prompts
            if use_templates:
                text_prompts = self._expand_with_templates(labels)
            else:
                text_prompts = labels

            text_tokens = clip.tokenize(text_prompts).to(self.device)

            # Compute features
            with torch.no_grad():
                image_features = self._model.encode_image(image_tensor)
                text_features = self._model.encode_text(text_tokens)

                # Normalize
                image_features = image_features / image_features.norm(dim=-1, keepdim=True)
                text_features = text_features / text_features.norm(dim=-1, keepdim=True)

                # Compute similarity
                similarity = (100.0 * image_features @ text_features.T).softmax(dim=-1)
                probs = similarity[0].cpu().numpy()

            # If using templates, average across templates
            if use_templates and len(self.templates) > 1:
                n_templates = len(self.templates)
                probs = probs.reshape(len(labels), n_templates).mean(axis=1)

            probs = probs.tolist()

        except (ImportError, AttributeError):
            # Mock classification
            probs = self._mock_classify(labels)

        inference_time = (time.time() - start_time) * 1000

        # Find top prediction
        top_idx = np.argmax(probs)

        return ClassificationResult(
            labels=labels,
            probabilities=probs,
            top_label=labels[top_idx],
            top_probability=probs[top_idx],
            inference_time_ms=inference_time,
            metadata={
                "model": self.model_type.value,
                "use_templates": use_templates,
            },
        )

    def classify_defects(self, image: np.ndarray) -> ClassificationResult:
        """Classify defect type in image."""
        return self.classify(image, self.label_sets["defect_types"])

    def classify_lego_color(self, image: np.ndarray) -> ClassificationResult:
        """Classify LEGO brick color."""
        return self.classify(image, self.label_sets["lego_colors"])

    def classify_lego_type(self, image: np.ndarray) -> ClassificationResult:
        """Classify LEGO part type."""
        return self.classify(image, self.label_sets["lego_types"])

    def classify_quality(self, image: np.ndarray) -> ClassificationResult:
        """Classify product quality grade."""
        return self.classify(image, self.label_sets["quality_grades"])

    def classify_assembly(self, image: np.ndarray) -> ClassificationResult:
        """Classify assembly state."""
        return self.classify(image, self.label_sets["assembly_states"])

    def multi_label_classify(
        self,
        image: np.ndarray,
        labels: List[str],
        threshold: float = 0.5,
    ) -> Dict[str, float]:
        """
        Multi-label classification (multiple labels can be true).

        Args:
            image: RGB image
            labels: List of possible labels
            threshold: Probability threshold for positive labels

        Returns:
            Dict of label -> probability for labels above threshold
        """
        result = self.classify(image, labels, use_templates=False)

        # Use sigmoid instead of softmax for multi-label
        if self._model is None:
            self.load_model()

        try:
            import torch
            from PIL import Image
            import clip

            pil_image = Image.fromarray(image)
            image_tensor = self._preprocess(pil_image).unsqueeze(0).to(self.device)
            text_tokens = clip.tokenize(labels).to(self.device)

            with torch.no_grad():
                image_features = self._model.encode_image(image_tensor)
                text_features = self._model.encode_text(text_tokens)

                image_features = image_features / image_features.norm(dim=-1, keepdim=True)
                text_features = text_features / text_features.norm(dim=-1, keepdim=True)

                # Use sigmoid for multi-label
                similarity = (image_features @ text_features.T)[0]
                probs = torch.sigmoid(similarity * 10).cpu().numpy()

            positive_labels = {
                label: float(prob)
                for label, prob in zip(labels, probs)
                if prob >= threshold
            }

        except (ImportError, AttributeError):
            positive_labels = {
                label: float(prob)
                for label, prob in zip(labels, result.probabilities)
                if prob >= threshold
            }

        return positive_labels

    def get_embedding(self, image: np.ndarray) -> EmbeddingResult:
        """
        Extract CLIP embedding for image.

        Args:
            image: RGB image

        Returns:
            EmbeddingResult with image embedding
        """
        if self._model is None:
            self.load_model()

        start_time = time.time()

        try:
            import torch
            from PIL import Image

            pil_image = Image.fromarray(image)
            image_tensor = self._preprocess(pil_image).unsqueeze(0).to(self.device)

            with torch.no_grad():
                image_features = self._model.encode_image(image_tensor)
                image_features = image_features / image_features.norm(dim=-1, keepdim=True)
                embedding = image_features[0].cpu().numpy()

        except (ImportError, AttributeError):
            embedding = np.random.randn(512).astype(np.float32)
            embedding = embedding / np.linalg.norm(embedding)

        inference_time = (time.time() - start_time) * 1000

        return EmbeddingResult(
            image_embedding=embedding,
            inference_time_ms=inference_time,
        )

    def compute_similarity(
        self,
        image: np.ndarray,
        texts: List[str],
    ) -> EmbeddingResult:
        """
        Compute similarity between image and texts.

        Args:
            image: RGB image
            texts: List of text descriptions

        Returns:
            EmbeddingResult with similarity scores
        """
        if self._model is None:
            self.load_model()

        start_time = time.time()

        try:
            import torch
            import clip
            from PIL import Image

            pil_image = Image.fromarray(image)
            image_tensor = self._preprocess(pil_image).unsqueeze(0).to(self.device)
            text_tokens = clip.tokenize(texts).to(self.device)

            with torch.no_grad():
                image_features = self._model.encode_image(image_tensor)
                text_features = self._model.encode_text(text_tokens)

                image_features = image_features / image_features.norm(dim=-1, keepdim=True)
                text_features = text_features / text_features.norm(dim=-1, keepdim=True)

                similarity = (image_features @ text_features.T)[0].cpu().numpy()

            image_embedding = image_features[0].cpu().numpy()
            text_embeddings = text_features.cpu().numpy()

        except (ImportError, AttributeError):
            image_embedding = np.random.randn(512).astype(np.float32)
            text_embeddings = np.random.randn(len(texts), 512).astype(np.float32)
            similarity = np.random.rand(len(texts)).astype(np.float32)

        inference_time = (time.time() - start_time) * 1000

        return EmbeddingResult(
            image_embedding=image_embedding,
            text_embeddings=text_embeddings,
            similarity_scores=similarity.tolist(),
            inference_time_ms=inference_time,
        )

    def find_best_match(
        self,
        query_image: np.ndarray,
        reference_images: List[np.ndarray],
    ) -> Tuple[int, float]:
        """
        Find most similar reference image.

        Args:
            query_image: Query RGB image
            reference_images: List of reference images

        Returns:
            Tuple of (best_index, similarity_score)
        """
        query_emb = self.get_embedding(query_image).image_embedding

        best_idx = -1
        best_sim = -1.0

        for i, ref_image in enumerate(reference_images):
            ref_emb = self.get_embedding(ref_image).image_embedding
            sim = float(np.dot(query_emb, ref_emb))

            if sim > best_sim:
                best_sim = sim
                best_idx = i

        return best_idx, best_sim

    def hierarchical_classify(
        self,
        image: np.ndarray,
        hierarchy: Dict[str, List[str]],
    ) -> Dict[str, ClassificationResult]:
        """
        Hierarchical classification with parent-child labels.

        Args:
            image: RGB image
            hierarchy: Dict of parent -> [children] labels

        Returns:
            Dict of level -> ClassificationResult
        """
        results = {}

        # First level: classify among parent categories
        parents = list(hierarchy.keys())
        parent_result = self.classify(image, parents)
        results["level_1"] = parent_result

        # Second level: classify among children of top parent
        top_parent = parent_result.top_label
        if top_parent in hierarchy and hierarchy[top_parent]:
            children = hierarchy[top_parent]
            child_result = self.classify(image, children)
            results["level_2"] = child_result

        return results

    def _expand_with_templates(self, labels: List[str]) -> List[str]:
        """Expand labels with prompt templates."""
        expanded = []
        for label in labels:
            for template in self.templates:
                expanded.append(template.format(label))
        return expanded

    def _mock_classify(self, labels: List[str]) -> List[float]:
        """Generate mock classification probabilities."""
        probs = np.random.rand(len(labels))
        probs = probs / probs.sum()
        return probs.tolist()


class MockCLIPModel:
    """Mock CLIP model for testing."""

    def encode_image(self, x):
        import numpy as np

        class MockTensor:
            def __init__(self, data):
                self.data = data

            def norm(self, dim=-1, keepdim=True):
                norm = np.linalg.norm(self.data, axis=dim, keepdims=keepdim)
                return MockTensor(norm)

            def __truediv__(self, other):
                if isinstance(other, MockTensor):
                    return MockTensor(self.data / other.data)
                return MockTensor(self.data / other)

            def __matmul__(self, other):
                if isinstance(other, MockTensor):
                    return MockTensor(np.dot(self.data, other.data.T))
                return MockTensor(np.dot(self.data, other.T))

            def softmax(self, dim=-1):
                exp = np.exp(self.data - self.data.max())
                return MockTensor(exp / exp.sum())

            def cpu(self):
                return self

            def numpy(self):
                return self.data

            def __getitem__(self, idx):
                return MockTensor(self.data[idx])

            @property
            def T(self):
                return MockTensor(self.data.T)

        batch_size = x.shape[0] if hasattr(x, 'shape') else 1
        return MockTensor(np.random.randn(batch_size, 512).astype(np.float32))

    def encode_text(self, x):
        return self.encode_image(x)
