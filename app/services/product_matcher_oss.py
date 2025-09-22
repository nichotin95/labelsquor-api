"""
Open-Source Product Matching Service
Uses free models that can run locally or on minimal infrastructure
"""

import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import faiss  # Facebook's similarity search
import numpy as np
import pandas as pd
import torch
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from app.core.logging import logger


class OpenSourceProductMatcher:
    """
    Product matching using completely free open-source models

    Models used:
    1. sentence-transformers/all-MiniLM-L6-v2 - Lightweight embeddings (22M params)
    2. sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 - For Indian languages
    3. cross-encoder/ms-marco-MiniLM-L-6-v2 - For reranking
    """

    def __init__(self, model_cache_dir: Optional[Path] = None):
        """Initialize with local model caching"""
        self.cache_dir = model_cache_dir or Path.home() / ".cache" / "labelsquor"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Load lightweight models
        logger.info("Loading open-source models...")

        # English product embeddings (22M params, 80MB)
        self.encoder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", cache_folder=str(self.cache_dir))

        # Multilingual for Indian text (51M params, 200MB)
        self.multilingual_encoder = SentenceTransformer(
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", cache_folder=str(self.cache_dir)
        )

        # Initialize FAISS index for fast similarity search
        self.embedding_dim = 384  # MiniLM-L6 dimension
        self.index = None
        self.product_mapping = {}  # Maps index position to product ID

        logger.info("Models loaded successfully!")

    def build_product_index(self, products: List[Dict[str, Any]]):
        """
        Build FAISS index for fast similarity search
        This is much faster than comparing all products every time
        """
        if not products:
            return

        logger.info(f"Building index for {len(products)} products...")

        # Create product texts
        texts = []
        for i, product in enumerate(products):
            text = self._create_product_text(product)
            texts.append(text)
            self.product_mapping[i] = product.get("id", i)

        # Generate embeddings in batches
        embeddings = self.encoder.encode(
            texts, batch_size=32, show_progress_bar=len(texts) > 100, convert_to_numpy=True
        )

        # Build FAISS index
        self.index = faiss.IndexFlatL2(self.embedding_dim)
        self.index.add(embeddings.astype("float32"))

        # Save index to disk for reuse
        self._save_index()

        logger.info("Index built successfully!")

    def find_similar_products(
        self, query_product: Dict[str, Any], top_k: int = 5, threshold: float = 0.85
    ) -> List[Tuple[Dict[str, Any], float]]:
        """
        Find similar products using FAISS
        Much faster than brute force comparison
        """
        if not self.index:
            return []

        # Create query embedding
        query_text = self._create_product_text(query_product)
        query_embedding = self.encoder.encode([query_text], convert_to_numpy=True)

        # Search in FAISS
        distances, indices = self.index.search(query_embedding.astype("float32"), top_k)

        results = []
        for i, (dist, idx) in enumerate(zip(distances[0], indices[0])):
            if idx == -1:  # No more results
                break

            # Convert L2 distance to similarity score
            similarity = 1 / (1 + dist)

            if similarity >= threshold:
                product_id = self.product_mapping.get(idx)
                results.append((product_id, similarity))

        return results

    def train_custom_matcher(self, training_data: List[Dict[str, Any]], save_path: Optional[Path] = None):
        """
        Fine-tune a model on your own product matching data
        Uses Siamese network approach
        """
        logger.info("Training custom product matcher...")

        # Prepare training pairs
        positive_pairs = []
        negative_pairs = []

        for item in training_data:
            # item should have: {'product1': {...}, 'product2': {...}, 'match': bool}
            text1 = self._create_product_text(item["product1"])
            text2 = self._create_product_text(item["product2"])

            if item["match"]:
                positive_pairs.append((text1, text2))
            else:
                negative_pairs.append((text1, text2))

        # Use Sentence Transformers training
        from sentence_transformers import InputExample, losses
        from torch.utils.data import DataLoader

        # Create training examples
        train_examples = []

        for text1, text2 in positive_pairs:
            train_examples.append(InputExample(texts=[text1, text2], label=1.0))

        for text1, text2 in negative_pairs:
            train_examples.append(InputExample(texts=[text1, text2], label=0.0))

        # Create DataLoader
        train_dataloader = DataLoader(train_examples, shuffle=True, batch_size=16)

        # Use Contrastive loss
        train_loss = losses.CosineSimilarityLoss(self.encoder)

        # Train
        self.encoder.fit(
            train_objectives=[(train_dataloader, train_loss)], epochs=5, warmup_steps=100, show_progress_bar=True
        )

        # Save fine-tuned model
        if save_path:
            self.encoder.save(str(save_path))
            logger.info(f"Model saved to {save_path}")

    def match_products_batch(self, products: List[Dict[str, Any]], threshold: float = 0.85) -> List[List[int]]:
        """
        Find all matching groups in a batch of products
        Returns groups of matching product indices
        """
        if len(products) < 2:
            return [[0]] if products else []

        # Generate embeddings for all products
        texts = [self._create_product_text(p) for p in products]
        embeddings = self.encoder.encode(texts, convert_to_numpy=True)

        # Compute pairwise similarities
        similarities = cosine_similarity(embeddings)

        # Find matching groups using Union-Find
        parent = list(range(len(products)))

        def find(x):
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]

        def union(x, y):
            px, py = find(x), find(y)
            if px != py:
                parent[px] = py

        # Union products that match
        for i in range(len(products)):
            for j in range(i + 1, len(products)):
                if similarities[i][j] >= threshold:
                    # Additional brand check
                    brand1 = products[i].get("brand", "").lower()
                    brand2 = products[j].get("brand", "").lower()

                    if brand1 and brand2 and brand1 == brand2:
                        union(i, j)

        # Group by parent
        groups = {}
        for i in range(len(products)):
            root = find(i)
            if root not in groups:
                groups[root] = []
            groups[root].append(i)

        return list(groups.values())

    def _create_product_text(self, product: Dict[str, Any]) -> str:
        """Create text representation for embedding"""
        parts = []

        # Brand is most important
        if brand := product.get("brand"):
            parts.append(f"Brand: {brand}")

        # Product name
        if name := product.get("name"):
            parts.append(f"Name: {name}")

        # Size/Pack
        if size := product.get("pack_size"):
            parts.append(f"Size: {size}")

        # Category for context
        if category := product.get("category"):
            parts.append(f"Category: {category}")

        return " ".join(parts)

    def _save_index(self):
        """Save FAISS index to disk"""
        if self.index:
            index_path = self.cache_dir / "product_index.faiss"
            mapping_path = self.cache_dir / "product_mapping.pkl"

            faiss.write_index(self.index, str(index_path))

            with open(mapping_path, "wb") as f:
                pickle.dump(self.product_mapping, f)

            logger.info(f"Index saved to {index_path}")

    def load_index(self):
        """Load previously saved index"""
        index_path = self.cache_dir / "product_index.faiss"
        mapping_path = self.cache_dir / "product_mapping.pkl"

        if index_path.exists() and mapping_path.exists():
            self.index = faiss.read_index(str(index_path))

            with open(mapping_path, "rb") as f:
                self.product_mapping = pickle.load(f)

            logger.info("Index loaded from disk")
            return True

        return False


class LightweightDeduplicator:
    """
    Ultra-lightweight deduplication using hashing and simple rules
    No ML needed - runs on minimal resources
    """

    def __init__(self):
        self.seen_products = set()

    def create_product_hash(self, product: Dict[str, Any]) -> str:
        """Create a hash for quick duplicate detection"""
        # Normalize and combine key fields
        brand = (product.get("brand") or "").lower().strip()
        name = (product.get("name") or "").lower()

        # Remove common words
        stopwords = {"the", "a", "an", "and", "or", "of", "in", "with"}
        name_words = [w for w in name.split() if w not in stopwords]
        name_clean = " ".join(sorted(name_words))

        # Extract size
        import re

        size_match = re.search(r"(\d+\.?\d*)\s*(g|kg|ml|l|pcs)", name.lower())
        size = size_match.group(0) if size_match else ""

        # Create hash
        import hashlib

        key = f"{brand}|{name_clean}|{size}"
        return hashlib.md5(key.encode()).hexdigest()

    def is_duplicate(self, product: Dict[str, Any]) -> bool:
        """Quick duplicate check"""
        product_hash = self.create_product_hash(product)

        if product_hash in self.seen_products:
            return True

        self.seen_products.add(product_hash)
        return False

    def find_near_duplicates(self, product: Dict[str, Any], candidates: List[Dict[str, Any]]) -> List[int]:
        """Find near duplicates using simple rules"""
        matches = []

        product_brand = (product.get("brand") or "").lower()
        product_words = set(product.get("name", "").lower().split())

        for i, candidate in enumerate(candidates):
            # Must have same brand
            if (candidate.get("brand") or "").lower() != product_brand:
                continue

            # Check word overlap
            candidate_words = set(candidate.get("name", "").lower().split())
            overlap = len(product_words & candidate_words)
            total = len(product_words | candidate_words)

            if total > 0 and overlap / total > 0.7:
                matches.append(i)

        return matches


# Model recommendations by resource level
MODEL_RECOMMENDATIONS = {
    "minimal": {
        "description": "Runs on CPU with < 1GB RAM",
        "models": ["sentence-transformers/all-MiniLM-L6-v2", "hashing + rules (no ML)"],  # 22M params
    },
    "standard": {
        "description": "Runs on modest GPU or good CPU",
        "models": [
            "sentence-transformers/all-mpnet-base-v2",  # 110M params
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        ],
    },
    "advanced": {
        "description": "Requires GPU with 8GB+ VRAM",
        "models": ["BAAI/bge-large-en-v1.5", "intfloat/e5-large-v2"],  # 335M params
    },
}
