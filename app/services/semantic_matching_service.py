import math
import re
from collections import Counter
from typing import Dict, List, Tuple


class SemanticMatchingService:
    """
    Semantic similarity matching for applications, vendors, and capabilities.
    Uses TF-IDF and cosine similarity - no external dependencies required.
    """

    def __init__(self):
        self.stop_words = set(
            [
                "the",
                "a",
                "an",
                "is",
                "are",
                "was",
                "were",
                "be",
                "been",
                "being",
                "have",
                "has",
                "had",
                "do",
                "does",
                "did",
                "will",
                "would",
                "could",
                "should",
                "may",
                "might",
                "must",
                "shall",
                "can",
                "need",
                "dare",
                "ought",
                "used",
                "to",
                "of",
                "in",
                "for",
                "on",
                "with",
                "at",
                "by",
                "from",
                "as",
                "into",
                "through",
                "during",
                "before",
                "after",
                "above",
                "below",
                "between",
                "under",
                "again",
                "further",
                "then",
                "once",
                "and",
                "but",
                "or",
                "nor",
                "so",
                "yet",
                "both",
                "either",
                "neither",
                "not",
                "only",
                "own",
                "same",
                "than",
                "too",
                "very",
                "just",
                "also",
                "now",
                "here",
                "there",
                "when",
                "where",
                "why",
                "how",
                "all",
                "each",
                "every",
                "both",
                "few",
                "more",
                "most",
                "other",
                "some",
                "such",
                "no",
                "any",
                "only",
                "this",
                "that",
                "these",
                "those",
                "it",
            ]
        )

        # Domain-specific synonyms for enterprise architecture
        self.synonyms = {
            "crm": ["customer relationship", "salesforce", "customer management", "sales"],
            "erp": ["enterprise resource", "sap", "oracle", "finance", "accounting"],
            "hrm": ["human resources", "hr", "workforce", "employee", "talent"],
            "scm": ["supply chain", "logistics", "procurement", "inventory"],
            "bi": ["business intelligence", "analytics", "reporting", "dashboard"],
            "api": ["integration", "interface", "service", "endpoint", "rest", "soap"],
            "cloud": ["aws", "azure", "gcp", "saas", "paas", "iaas"],
            "security": ["authentication", "authorization", "encryption", "compliance"],
            "data": ["database", "storage", "warehouse", "lake", "etl"],
            "microservices": ["containers", "kubernetes", "docker", "distributed"],
        }

    def tokenize(self, text: str) -> List[str]:
        """Tokenize and normalize text"""
        text = text.lower()
        text = re.sub(r"[^a-z0 - 9\s]", " ", text)
        tokens = text.split()
        tokens = [t for t in tokens if t not in self.stop_words and len(t) > 2]
        return tokens

    def expand_with_synonyms(self, tokens: List[str]) -> List[str]:
        """Expand tokens with domain synonyms"""
        expanded = list(tokens)
        for token in tokens:
            for key, synonyms in self.synonyms.items():
                if token == key or token in synonyms:
                    expanded.extend([key] + synonyms)
        return list(set(expanded))

    def compute_tf(self, tokens: List[str]) -> Dict[str, float]:
        """Compute term frequency"""
        tf = Counter(tokens)
        total = len(tokens)
        return {term: count / total for term, count in tf.items()} if total > 0 else {}

    def compute_idf(self, documents: List[List[str]]) -> Dict[str, float]:
        """Compute inverse document frequency"""
        n_docs = len(documents)
        idf = {}
        all_terms = set(term for doc in documents for term in doc)

        for term in all_terms:
            doc_count = sum(1 for doc in documents if term in doc)
            idf[term] = math.log(n_docs / (1 + doc_count)) + 1

        return idf

    def compute_tfidf(self, tokens: List[str], idf: Dict[str, float]) -> Dict[str, float]:
        """Compute TF-IDF vector"""
        tf = self.compute_tf(tokens)
        return {term: tf_val * idf.get(term, 1) for term, tf_val in tf.items()}

    def cosine_similarity(self, vec1: Dict[str, float], vec2: Dict[str, float]) -> float:
        """Compute cosine similarity between two vectors"""
        all_terms = set(vec1.keys()) | set(vec2.keys())

        dot_product = sum(vec1.get(t, 0) * vec2.get(t, 0) for t in all_terms)
        norm1 = math.sqrt(sum(v**2 for v in vec1.values())) or 1
        norm2 = math.sqrt(sum(v**2 for v in vec2.values())) or 1

        return dot_product / (norm1 * norm2)

    def match_applications(
        self,
        problem_description: str,
        applications: List[dict],
        top_n: int = 10,
        min_score: float = 0.1,
    ) -> List[dict]:
        """
        Match applications to a problem description using semantic similarity.

        Args:
            problem_description: The problem/solution description
            applications: List of app dicts with 'id', 'name', 'description', 'capabilities'
            top_n: Number of top matches to return
            min_score: Minimum similarity score threshold

        Returns:
            List of matched applications with scores and match explanations
        """
        # Tokenize problem
        problem_tokens = self.tokenize(problem_description)
        problem_tokens = self.expand_with_synonyms(problem_tokens)

        # Build corpus for IDF
        corpus = [problem_tokens]
        app_tokens_list = []

        for app in applications:
            app_text = f"{app.get('name', '')} {app.get('description', '')} {' '.join(app.get('capabilities', []))}"
            tokens = self.tokenize(app_text)
            tokens = self.expand_with_synonyms(tokens)
            app_tokens_list.append(tokens)
            corpus.append(tokens)

        # Compute IDF
        idf = self.compute_idf(corpus)

        # Compute TF-IDF for problem
        problem_tfidf = self.compute_tfidf(problem_tokens, idf)

        # Score each application
        results = []
        for i, app in enumerate(applications):
            app_tfidf = self.compute_tfidf(app_tokens_list[i], idf)
            score = self.cosine_similarity(problem_tfidf, app_tfidf)

            if score >= min_score:
                # Find matching terms for explanation
                matching_terms = set(problem_tokens) & set(app_tokens_list[i])

                results.append(
                    {
                        "application": app,
                        "score": round(score * 100, 2),  # Convert to 0 - 100
                        "matching_terms": list(matching_terms)[:10],
                        "match_explanation": self._generate_match_explanation(
                            matching_terms, score
                        ),
                    }
                )

        # Sort by score descending
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_n]

    def match_vendors(
        self, requirements: List[str], vendors: List[dict], top_n: int = 5, min_score: float = 0.1
    ) -> List[dict]:
        """Match vendor products to requirements"""
        req_text = " ".join(requirements)
        req_tokens = self.tokenize(req_text)
        req_tokens = self.expand_with_synonyms(req_tokens)

        corpus = [req_tokens]
        vendor_tokens_list = []

        for vendor in vendors:
            vendor_text = f"{vendor.get('name', '')} {vendor.get('description', '')} {' '.join(vendor.get('features', []))}"
            tokens = self.tokenize(vendor_text)
            tokens = self.expand_with_synonyms(tokens)
            vendor_tokens_list.append(tokens)
            corpus.append(tokens)

        idf = self.compute_idf(corpus)
        req_tfidf = self.compute_tfidf(req_tokens, idf)

        results = []
        for i, vendor in enumerate(vendors):
            vendor_tfidf = self.compute_tfidf(vendor_tokens_list[i], idf)
            score = self.cosine_similarity(req_tfidf, vendor_tfidf)

            if score >= min_score:
                matching_terms = set(req_tokens) & set(vendor_tokens_list[i])
                results.append(
                    {
                        "vendor": vendor,
                        "score": round(score * 100, 2),
                        "matching_terms": list(matching_terms)[:10],
                        "coverage_areas": self._identify_coverage_areas(matching_terms),
                    }
                )

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_n]

    def match_capabilities(
        self, problem_description: str, capabilities: List[dict], top_n: int = 10
    ) -> List[dict]:
        """Match business capabilities to a problem"""
        problem_tokens = self.tokenize(problem_description)
        problem_tokens = self.expand_with_synonyms(problem_tokens)

        corpus = [problem_tokens]
        cap_tokens_list = []

        for cap in capabilities:
            cap_text = f"{cap.get('name', '')} {cap.get('description', '')}"
            tokens = self.tokenize(cap_text)
            cap_tokens_list.append(tokens)
            corpus.append(tokens)

        idf = self.compute_idf(corpus)
        problem_tfidf = self.compute_tfidf(problem_tokens, idf)

        results = []
        for i, cap in enumerate(capabilities):
            cap_tfidf = self.compute_tfidf(cap_tokens_list[i], idf)
            score = self.cosine_similarity(problem_tfidf, cap_tfidf)

            if score > 0:
                results.append({"capability": cap, "relevance_score": round(score * 100, 2)})

        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        return results[:top_n]

    def _generate_match_explanation(self, matching_terms: set, score: float) -> str:
        """Generate human-readable explanation for a match"""
        if score > 0.7:
            strength = "Strong"
        elif score > 0.4:
            strength = "Moderate"
        else:
            strength = "Weak"

        if matching_terms:
            terms_str = ", ".join(list(matching_terms)[:5])
            return f"{strength} match based on: {terms_str}"
        return f"{strength} match based on semantic similarity"

    def _identify_coverage_areas(self, matching_terms: set) -> List[str]:
        """Identify which functional areas are covered by matching terms"""
        areas = []
        for key, synonyms in self.synonyms.items():
            if key in matching_terms or any(s in matching_terms for s in synonyms):
                areas.append(key.upper())
        return areas
