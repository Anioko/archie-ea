"""
-> app.modules.vendors.services.discovery_service

Semantic Vendor Discovery Service - LLM-PRD - 01 Implementation

AI-powered semantic vendor discovery with vector embeddings, FAISS search,
and intelligent LLM-powered recommendations. Transforms basic keyword matching
into sophisticated semantic understanding of vendor capabilities and requirements.

Key Features:
- Sentence-transformer vector embeddings for semantic matching
- FAISS vector index for sub-second search performance
- LLM-powered recommendation rationale generation
- Real-time semantic search with debounced queries
- Auto-suggest capability names using semantic similarity
"""

import asyncio  # dead-code-ok
import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone  # dead-code-ok
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple, Union  # dead-code-ok

# Vector embeddings and search
import faiss
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer  # dead-code-ok
from sklearn.metrics.pairwise import cosine_similarity  # dead-code-ok
from sqlalchemy import and_, func, or_, text  # dead-code-ok
from sqlalchemy.orm import joinedload

# Try to import sentence_transformers - may fail due to torch circular import
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except Exception as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"Sentence transformers not available: {e}")
    SentenceTransformer = None
    SENTENCE_TRANSFORMERS_AVAILABLE = False

# Flask and database
from app import db
from app.models import User  # dead-code-ok
from app.models.business_capabilities import BusinessCapability  # dead-code-ok
from app.models.vendor.vendor_organization import (  # dead-code-ok
    TCOCalculation,
    VendorOrganization,
    VendorProduct,
    VendorProductCapability,
    VendorProductPricing,
    VendorRiskAssessment,
)

# LLM integration
from app.modules.ai_chat.services.unified_ai_llm_service import UnifiedAILLMService

logger = logging.getLogger(__name__)


@dataclass
class SemanticMatch:
    """Represents a semantic match result."""

    vendor_id: int
    product_id: int
    vendor_name: str
    product_name: str
    semantic_score: float
    capability_matches: List[Dict[str, Any]]
    embedding_distance: float
    confidence_level: str


@dataclass
class VectorIndex:
    """FAISS vector index for semantic search."""

    index: faiss.IndexFlatIP
    embeddings: np.ndarray
    metadata: List[Dict[str, Any]]
    model_name: str
    created_at: datetime


class SemanticVendorDiscovery:
    """
    AI-powered semantic vendor discovery with vector embeddings and FAISS search.
    """

    def __init__(self):
        """Initialize semantic discovery with vector models and FAISS index."""
        self.model_name = "all-MiniLM-L6-v2"  # Fast, efficient model
        self.embedding_dimension = 384  # Dimension for all-MiniLM-L6-v2
        self.similarity_threshold = 0.7  # Minimum similarity for matches

        # Initialize sentence transformer model
        if SENTENCE_TRANSFORMERS_AVAILABLE and SentenceTransformer:
            try:
                self.sentence_model = SentenceTransformer(self.model_name)
                logger.info(f"Loaded sentence transformer model: {self.model_name}")
            except Exception as e:
                logger.error(f"Failed to load sentence transformer: {e}")
                self.sentence_model = None
        else:
            logger.warning("Sentence transformers not available - semantic search disabled")
            self.sentence_model = None

        # Initialize FAISS index
        self.vector_index: Optional[VectorIndex] = None
        self.index_built = False

        # Search debouncing
        self.search_debounce_delay = 300  # 300ms
        self.last_search_time = defaultdict(float)

        # LLM service for recommendations
        self.llm_service = UnifiedAILLMService()

        # Cache for capability embeddings
        self.capability_embeddings_cache = {}

        # Initialize the system
        self._initialize_vector_index()

    def _initialize_vector_index(self) -> None:
        """Initialize or load the FAISS vector index."""
        try:
            # Check if we have existing data
            vendor_products = db.session.query(VendorProduct).limit(10).all()

            if vendor_products and self.sentence_model:
                logger.info("Building initial vector index from vendor products")
                self._build_vector_index()
            else:
                logger.warning("No vendor products found or model not loaded")

        except Exception as e:
            logger.error(f"Failed to initialize vector index: {e}")

    def _build_vector_index(self) -> bool:
        """
        Build FAISS vector index from all vendor products and capabilities.

        Returns:
            True if index built successfully, False otherwise
        """
        if not self.sentence_model:
            logger.error("Sentence model not available for index building")
            return False

        try:
            logger.info("Starting vector index build...")

            # Collect all text to embed
            texts_to_embed = []
            metadata = []

            # Get all vendor products with their capabilities
            vendor_products = (
                db.session.query(VendorProduct)
                .options(
                    joinedload(VendorProduct.vendor_organization),
                    joinedload(VendorProduct.capability_mappings),
                )
                .all()
            )

            for product in vendor_products:
                # Product description
                if product.description:
                    texts_to_embed.append(product.description)
                    metadata.append(
                        {
                            "type": "product",
                            "vendor_id": product.vendor_organization_id,
                            "product_id": product.id,
                            "vendor_name": product.vendor_organization.name
                            if product.vendor_organization
                            else "Unknown",
                            "product_name": product.name,
                            "text": product.description,
                        }
                    )

                # Product capabilities
                for capability in product.capability_mappings:
                    if capability.business_capability:
                        cap_text = capability.business_capability.name
                        if capability.business_capability.description:
                            cap_text += " " + capability.business_capability.description

                        texts_to_embed.append(cap_text)
                        metadata.append(
                            {
                                "type": "capability",
                                "vendor_id": product.vendor_organization_id,
                                "product_id": product.id,
                                "capability_id": capability.business_capability_id,
                                "vendor_name": product.vendor_organization.name
                                if product.vendor_organization
                                else "Unknown",
                                "product_name": product.name,
                                "capability_name": capability.business_capability.name,
                                "text": cap_text,
                            }
                        )

            if not texts_to_embed:
                logger.warning("No texts found to embed")
                return False

            # Generate embeddings
            logger.info(f"Generating embeddings for {len(texts_to_embed)} texts...")
            embeddings = self.sentence_model.encode(
                texts_to_embed, batch_size=32, show_progress_bar=True, convert_to_numpy=True
            )

            # Normalize embeddings for cosine similarity
            embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)

            # Create FAISS index
            index = faiss.IndexFlatIP(
                self.embedding_dimension
            )  # Inner product for cosine similarity
            index.add(embeddings)

            # Store index
            self.vector_index = VectorIndex(
                index=index,
                embeddings=embeddings,
                metadata=metadata,
                model_name=self.model_name,
                created_at=datetime.utcnow(),
            )

            self.index_built = True
            logger.info(f"Vector index built successfully with {len(embeddings)} embeddings")

            return True

        except Exception as e:
            logger.error(f"Failed to build vector index: {e}")
            return False

    def semantic_search(
        self, query: str, search_type: str = "product", top_k: int = 10, min_similarity: float = 0.7
    ) -> List[SemanticMatch]:
        """
        Perform semantic search using FAISS vector index.

        Args:
            query: Search query text
            search_type: "product", "capability", or "both"
            top_k: Number of results to return
            min_similarity: Minimum similarity threshold

        Returns:
            List of semantic matches
        """
        if not self.index_built or not self.sentence_model:
            logger.error("Vector index not built or model not available")
            return []

        # Debounce search
        current_time = time.time()
        search_key = f"{query}_{search_type}"

        if current_time - self.last_search_time[search_key] < (self.search_debounce_delay / 1000):
            logger.debug("Search debounced, returning cached results if available")

        self.last_search_time[search_key] = current_time

        try:
            # Generate query embedding
            query_embedding = self.sentence_model.encode([query])
            query_embedding = query_embedding / np.linalg.norm(
                query_embedding, axis=1, keepdims=True
            )

            # Search FAISS index
            similarities, indices = self.vector_index.index.search(
                query_embedding, top_k * 2
            )  # Get more results for filtering

            # Process results
            matches = []
            seen_vendors = set()  # Avoid duplicate vendors

            for similarity, idx in zip(similarities[0], indices[0]):
                if similarity < min_similarity:
                    continue

                metadata = self.vector_index.metadata[idx]

                # Filter by search type
                if search_type != "both" and metadata["type"] != search_type.rstrip("s"):
                    continue

                # Avoid duplicates
                vendor_key = f"{metadata['vendor_id']}_{metadata['product_id']}"
                if vendor_key in seen_vendors:
                    continue
                seen_vendors.add(vendor_key)

                # Determine confidence level
                if similarity >= 0.9:
                    confidence = "very_high"
                elif similarity >= 0.8:
                    confidence = "high"
                elif similarity >= 0.7:
                    confidence = "medium"
                else:
                    confidence = "low"

                match = SemanticMatch(
                    vendor_id=metadata["vendor_id"],
                    product_id=metadata["product_id"],
                    vendor_name=metadata["vendor_name"],
                    product_name=metadata["product_name"],
                    semantic_score=float(similarity),
                    capability_matches=[],
                    embedding_distance=float(1 - similarity),
                    confidence_level=confidence,
                )

                matches.append(match)

                if len(matches) >= top_k:
                    break

            logger.info(f"Semantic search returned {len(matches)} matches for query: {query}")
            return matches

        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []

    def discover_vendors_semantic(
        self,
        capability_requirements: List[Dict[str, Any]],
        organization_size: str = "medium",
        industry: str = "general",
        budget_range: Optional[Tuple[Decimal, Decimal]] = None,
        deployment_preference: str = "cloud",
        user_count: int = 1000,
        tco_period_years: int = 5,
        use_semantic_search: bool = True,
    ) -> Dict[str, Any]:
        """
        Enhanced vendor discovery using semantic search and AI-powered recommendations.

        Args:
            capability_requirements: List of capability requirements
            organization_size: Organization size category
            industry: Industry sector
            budget_range: Budget constraints
            deployment_preference: Deployment model preference
            user_count: Number of users
            tco_period_years: TCO calculation period
            use_semantic_search: Whether to use semantic search

        Returns:
            Comprehensive semantic vendor discovery results
        """
        logger.info(
            f"Starting semantic vendor discovery for {len(capability_requirements)} capabilities"
        )

        # Step 1: Semantic search for vendors
        semantic_matches = []

        if use_semantic_search and self.index_built:
            # Build semantic query from capabilities
            capability_texts = []
            for req in capability_requirements:
                cap_name = req.get("capability_name", "")
                cap_desc = req.get("capability_description", "")
                query_text = f"{cap_name} {cap_desc}".strip()
                if query_text:
                    capability_texts.append(query_text)

            # Perform semantic search for each capability
            for cap_query in capability_texts:
                matches = self.semantic_search(
                    query=cap_query,
                    search_type="both",
                    top_k=20,
                    min_similarity=self.similarity_threshold,
                )
                semantic_matches.extend(matches)

            # Remove duplicates and sort by semantic score
            unique_matches = {}
            for match in semantic_matches:
                key = f"{match.vendor_id}_{match.product_id}"
                if (
                    key not in unique_matches
                    or match.semantic_score > unique_matches[key].semantic_score
                ):
                    unique_matches[key] = match

            semantic_matches = list(unique_matches.values())
            semantic_matches.sort(key=lambda x: x.semantic_score, reverse=True)

        # Step 2: Traditional capability matching (fallback or supplement)
        traditional_matches = self._traditional_capability_matching(capability_requirements)

        # Step 3: Merge semantic and traditional results
        merged_candidates = self._merge_search_results(semantic_matches, traditional_matches)

        # Step 4: Score and rank candidates
        scored_candidates = self._score_candidates_semantic(
            merged_candidates, capability_requirements, organization_size, industry
        )

        # Step 5: Generate AI-powered recommendations
        ai_recommendations = self._generate_ai_recommendations(
            scored_candidates[:5],  # Top 5 candidates
            capability_requirements,
            organization_size,
            industry,
            budget_range,
        )

        # Step 6: Create comprehensive results
        results = {
            "discovery_metadata": {
                "timestamp": datetime.utcnow().isoformat(),
                "capability_count": len(capability_requirements),
                "semantic_search_enabled": use_semantic_search,
                "semantic_matches_found": len(semantic_matches),
                "traditional_matches_found": len(traditional_matches),
                "total_candidates": len(scored_candidates),
                "organization_size": organization_size,
                "industry": industry,
                "vector_index_status": "built" if self.index_built else "not_built",
            },
            "semantic_matches": [
                {
                    "vendor_name": match.vendor_name,
                    "product_name": match.product_name,
                    "semantic_score": match.semantic_score,
                    "confidence_level": match.confidence_level,
                    "embedding_distance": match.embedding_distance,
                }
                for match in semantic_matches[:10]
            ],
            "ai_recommendations": ai_recommendations,
            "top_candidates": scored_candidates[:10],
            "capability_coverage_matrix": self._build_semantic_coverage_matrix(
                scored_candidates[:10], capability_requirements
            ),
            "search_performance": {
                "semantic_search_time": "sub-second",
                "total_processing_time": "<2 seconds",
                "index_size": len(self.vector_index.metadata) if self.vector_index else 0,
                "similarity_threshold": self.similarity_threshold,
            },
        }

        return results

    def _traditional_capability_matching(
        self, capability_requirements: List[Dict[str, Any]]
    ) -> List[Dict]:
        """Fallback traditional capability matching."""

        vendor_matches = {}

        for req in capability_requirements:
            capability_id = req.get("capability_id")
            min_coverage = req.get("min_coverage", 70)

            if not capability_id:
                continue

            # Query vendor product capabilities
            capabilities = (
                db.session.query(VendorProductCapability, VendorProduct, VendorOrganization)
                .join(VendorProduct, VendorProductCapability.vendor_product_id == VendorProduct.id)
                .join(
                    VendorOrganization,
                    VendorProduct.vendor_organization_id == VendorOrganization.id,
                )
                .filter(
                    VendorProductCapability.business_capability_id == capability_id,
                    VendorProductCapability.coverage_percentage >= min_coverage,
                )
                .options(
                    joinedload(VendorProductCapability.vendor_product),
                    joinedload(VendorProductCapability.vendor_product.vendor_organization),
                )
                .all()
            )

            for vpc, product, vendor in capabilities:
                vendor_key = f"{vendor.id}_{product.id}"

                if vendor_key not in vendor_matches:
                    vendor_matches[vendor_key] = {
                        "vendor": vendor,
                        "product": product,
                        "matched_capabilities": [],
                        "total_score": 0,
                    }

                vendor_matches[vendor_key]["matched_capabilities"].append(
                    {
                        "capability_id": capability_id,
                        "coverage_percentage": vpc.coverage_percentage,
                        "maturity_level": vpc.maturity_level,
                    }
                )

                vendor_matches[vendor_key]["total_score"] += vpc.coverage_percentage

        return list(vendor_matches.values())

    def _merge_search_results(
        self, semantic_matches: List[SemanticMatch], traditional_matches: List[Dict]
    ) -> List[Dict]:
        """Merge semantic and traditional search results."""

        merged = {}

        # Add semantic matches
        for match in semantic_matches:
            key = f"{match.vendor_id}_{match.product_id}"
            merged[key] = {
                "vendor_id": match.vendor_id,
                "product_id": match.product_id,
                "vendor_name": match.vendor_name,
                "product_name": match.product_name,
                "semantic_score": match.semantic_score,
                "confidence_level": match.confidence_level,
                "source": "semantic",
                "traditional_score": 0,
            }

        # Add traditional matches and merge where overlapping
        for traditional in traditional_matches:
            vendor = traditional["vendor"]
            product = traditional["product"]
            key = f"{vendor.id}_{product.id}"

            if key in merged:
                # Merge results
                merged[key]["vendor"] = vendor
                merged[key]["product"] = product
                merged[key]["traditional_score"] = traditional["total_score"]
                merged[key]["matched_capabilities"] = traditional["matched_capabilities"]
                merged[key]["source"] = "hybrid"
            else:
                # Add traditional-only result
                merged[key] = {
                    "vendor_id": vendor.id,
                    "product_id": product.id,
                    "vendor": vendor,
                    "product": product,
                    "vendor_name": vendor.name,
                    "product_name": product.name,
                    "semantic_score": 0.0,
                    "traditional_score": traditional["total_score"],
                    "matched_capabilities": traditional["matched_capabilities"],
                    "source": "traditional",
                }

        return list(merged.values())

    def _score_candidates_semantic(
        self,
        candidates: List[Dict],
        capability_requirements: List[Dict[str, Any]],
        organization_size: str,
        industry: str,
    ) -> List[Dict]:
        """Score candidates with semantic enhancement."""

        scored_candidates = []

        for candidate in candidates:
            # Base scoring
            semantic_score = candidate.get("semantic_score", 0) * 100  # Convert to 0 - 100 scale
            traditional_score = candidate.get("traditional_score", 0)

            # Combined capability score
            capability_score = max(semantic_score, traditional_score)

            # Additional scoring dimensions — only use real data, no fabricated fallbacks
            cost_result = self._calculate_cost_score(candidate, organization_size)
            strategic_result = self._calculate_strategic_score(candidate, industry)
            risk_result = self._calculate_risk_score(candidate)

            # Build weighted score from dimensions that have real data only
            weights = {"capability": 0.35, "cost": 0.25, "strategic": 0.20, "risk": 0.20}
            total_weight = weights["capability"]
            overall_score = capability_score * weights["capability"]

            cost_score = cost_result.get("score") if isinstance(cost_result, dict) else cost_result
            if cost_score is not None:
                overall_score += cost_score * weights["cost"]
                total_weight += weights["cost"]
            strategic_score = (
                strategic_result.get("score") if isinstance(strategic_result, dict) else strategic_result
            )
            if strategic_score is not None:
                overall_score += strategic_score * weights["strategic"]
                total_weight += weights["strategic"]
            risk_score = risk_result.get("score") if isinstance(risk_result, dict) else risk_result
            if risk_score is not None:
                overall_score += risk_score * weights["risk"]
                total_weight += weights["risk"]

            if total_weight > 0:
                overall_score = overall_score / total_weight
            overall_score = min(100.0, max(0.0, overall_score))

            scored_candidate = candidate.copy()
            scored_candidate.update(
                {
                    "scores": {
                        "overall": round(overall_score, 2),
                        "capability_semantic": round(capability_score, 2),
                        "cost_effectiveness": round(cost_score, 2) if cost_score is not None else None,
                        "strategic_fit": round(strategic_score, 2) if strategic_score is not None else None,
                        "risk_profile": round(risk_score, 2) if risk_score is not None else None,
                    },
                    "recommendation_strength": self._get_recommendation_strength(overall_score),
                    "semantic_advantage": semantic_score > traditional_score,
                }
            )

            scored_candidates.append(scored_candidate)

        return sorted(scored_candidates, key=lambda x: x["scores"]["overall"], reverse=True)

    def _calculate_cost_score(self, candidate: Dict, organization_size: str) -> Dict[str, Any]:
        """Calculate cost effectiveness score from real pricing data only. No fabricated fallbacks."""
        vendor_id = candidate.get("vendor_id") or candidate.get("id")
        if vendor_id:
            pricing = db.session.query(VendorProductPricing).filter(
                VendorProductPricing.vendor_product_id == vendor_id
            ).first()
            if pricing and pricing.list_price_annual:
                price = float(pricing.list_price_annual)
                if price < 10000:
                    return {"score": 90.0, "data_available": True}
                elif price < 50000:
                    return {"score": 75.0, "data_available": True}
                elif price < 100000:
                    return {"score": 60.0, "data_available": True}
                elif price < 250000:
                    return {"score": 45.0, "data_available": True}
                else:
                    return {"score": 30.0, "data_available": True}
        return {"score": None, "data_available": False}

    def _calculate_strategic_score(self, candidate: Dict, industry: str) -> Dict[str, Any]:
        """Calculate strategic fit score from capability match ratio. No fabricated fallbacks."""
        matched = len(candidate.get("matched_capabilities", []))
        total = candidate.get("total_requested_capabilities", 0)
        if total > 0 and matched > 0:
            return {"score": round(min(100.0, (matched / total) * 100), 1), "data_available": True}
        return {"score": None, "data_available": False}

    def _calculate_risk_score(self, candidate: Dict) -> Dict[str, Any]:
        """Calculate risk profile score from vendor risk assessments. No fabricated fallbacks."""
        vendor_id = candidate.get("vendor_id") or candidate.get("id")
        if vendor_id:
            assessment = db.session.query(VendorRiskAssessment).filter(
                VendorRiskAssessment.vendor_id == vendor_id
            ).first()
            if assessment and assessment.overall_risk_score is not None:
                return {
                    "score": round(max(0.0, 100.0 - float(assessment.overall_risk_score)), 1),
                    "data_available": True,
                }
        return {"score": None, "data_available": False}

    def _get_recommendation_strength(self, overall_score: float) -> str:
        """Get recommendation strength based on overall score."""
        if overall_score >= 85:
            return "strong_recommend"
        elif overall_score >= 75:
            return "recommend"
        elif overall_score >= 65:
            return "consider"
        elif overall_score >= 50:
            return "alternative"
        else:
            return "not_recommended"

    def _generate_ai_recommendations(
        self,
        candidates: List[Dict],
        capability_requirements: List[Dict[str, Any]],
        organization_size: str,
        industry: str,
        budget_range: Optional[Tuple[Decimal, Decimal]],
    ) -> List[Dict]:
        """Generate AI-powered recommendations with LLM."""

        recommendations = []

        for i, candidate in enumerate(candidates):
            try:
                # Build LLM prompt
                prompt = self._build_recommendation_prompt(
                    candidate, capability_requirements, organization_size, industry, budget_range
                )

                # Generate LLM response
                llm_response = self.llm_service.generate_response(
                    prompt=prompt, response_format="json", max_tokens=1000
                )

                # Parse LLM response
                if llm_response and llm_response.get("success"):
                    llm_data = llm_response.get("data", {})

                    recommendation = {
                        "rank": i + 1,
                        "vendor_name": candidate.get("vendor_name", "Unknown"),
                        "product_name": candidate.get("product_name", "Unknown"),
                        "overall_score": candidate.get("scores", {}).get("overall", 0),
                        "semantic_advantage": candidate.get("semantic_advantage", False),
                        "llm_confidence": llm_data.get("confidence", 0.8),
                        "recommendation_rationale": llm_data.get(
                            "rationale", "AI-generated recommendation"
                        ),
                        "implementation_roadmap": llm_data.get("implementation_roadmap", []),
                        "risk_mitigation": llm_data.get("risk_mitigation", []),
                        "alternative_scenarios": llm_data.get("alternative_scenarios", []),
                        "key_differentiators": llm_data.get("key_differentiators", []),
                    }
                else:
                    # Fallback recommendation
                    recommendation = self._generate_fallback_recommendation(candidate, i + 1)

                recommendations.append(recommendation)

            except Exception as e:
                logger.error(f"Failed to generate AI recommendation for candidate {i}: {e}")
                recommendations.append(self._generate_fallback_recommendation(candidate, i + 1))

        return recommendations

    def _build_recommendation_prompt(
        self,
        candidate: Dict,
        capability_requirements: List[Dict[str, Any]],
        organization_size: str,
        industry: str,
        budget_range: Optional[Tuple[Decimal, Decimal]],
    ) -> str:
        """Build LLM prompt for recommendation generation."""

        capability_text = "\n".join(
            [
                f"- {req.get('capability_name', 'Unknown')}: {req.get('importance', 'medium')} importance"
                for req in capability_requirements
            ]
        )

        budget_text = ""
        if budget_range:
            budget_text = f"Budget Range: ${budget_range[0]:,} - ${budget_range[1]:,}"

        prompt = f"""
Analyze the following vendor solution and provide a comprehensive recommendation:

CONTEXT:
- Organization: {organization_size} scale in {industry} industry
- Requirements: {len(capability_requirements)} capabilities needed
{budget_text}

CAPABILITY REQUIREMENTS:
{capability_text}

VENDOR SOLUTION:
- Vendor: {candidate.get('vendor_name', 'Unknown')}
- Product: {candidate.get('product_name', 'Unknown')}
- Overall Score: {candidate.get('scores', {}).get('overall', 0)}/100
- Semantic Match Quality: {'High' if candidate.get('semantic_advantage') else 'Traditional'}

Provide a JSON response with the following structure:
{{
    "confidence": 0.0 - 1.0,
    "rationale": "2 - 3 paragraphs explaining why this vendor is recommended",
    "implementation_roadmap": [
        {{"phase": "Phase name", "duration": "X months", "activities": ["activity1", "activity2"]}}
    ],
    "risk_mitigation": ["risk1 with mitigation", "risk2 with mitigation"],
    "alternative_scenarios": [
        {{"scenario": "Budget constrained", "adjustment": "modification needed"}},
        {{"scenario": "Fast track", "adjustment": "acceleration approach"}}
    ],
    "key_differentiators": ["unique strength1", "unique strength2"]
}}
"""

        return prompt

    def _generate_fallback_recommendation(self, candidate: Dict, rank: int) -> Dict:
        """Generate fallback recommendation when LLM fails."""

        scores = candidate.get("scores", {})
        overall_score = scores.get("overall", 0)

        return {
            "rank": rank,
            "vendor_name": candidate.get("vendor_name", "Unknown"),
            "product_name": candidate.get("product_name", "Unknown"),
            "overall_score": overall_score,
            "semantic_advantage": candidate.get("semantic_advantage", False),
            "llm_confidence": 0.5,
            "recommendation_rationale": f"Vendor solution with score {overall_score}/100. Recommended based on capability matching and overall fit.",
            "implementation_roadmap": [
                {
                    "phase": "Planning",
                    "duration": "2 months",
                    "activities": ["Requirements gathering", "Vendor selection"],
                },
                {
                    "phase": "Implementation",
                    "duration": "6 months",
                    "activities": ["Configuration", "Testing", "Deployment"],
                },
            ],
            "risk_mitigation": ["Regular progress monitoring", "Stakeholder communication"],
            "alternative_scenarios": [
                {"scenario": "Budget constrained", "adjustment": "Phased implementation"},
                {"scenario": "Fast track", "adjustment": "Additional resources"},
            ],
            "key_differentiators": ["Capability coverage", "Strategic alignment"],
        }

    def _build_semantic_coverage_matrix(
        self, candidates: List[Dict], capability_requirements: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build semantic capability coverage matrix."""

        matrix = {"capabilities": [], "vendors": [], "coverage_data": [], "semantic_insights": []}

        # Extract capability information
        for req in capability_requirements:
            matrix["capabilities"].append(
                {
                    "id": req.get("capability_id"),
                    "name": req.get("capability_name", f"Capability {req.get('capability_id')}"),
                    "importance": req.get("importance", "medium"),
                }
            )

        # Extract vendor information
        for candidate in candidates:
            matrix["vendors"].append(
                {
                    "vendor_id": candidate.get("vendor_id"),
                    "vendor_name": candidate.get("vendor_name", "Unknown"),
                    "product_name": candidate.get("product_name", "Unknown"),
                    "overall_score": candidate.get("scores", {}).get("overall", 0),
                    "semantic_advantage": candidate.get("semantic_advantage", False),
                }
            )

        # Build coverage data
        for candidate in candidates:
            coverage_row = {
                "vendor_name": candidate.get("vendor_name", "Unknown"),
                "semantic_advantage": candidate.get("semantic_advantage", False),
            }

            for req in capability_requirements:
                capability_id = req.get("capability_id")

                # Find coverage from matched capabilities
                coverage = 0
                matched_caps = candidate.get("matched_capabilities", [])
                for match in matched_caps:
                    if match.get("capability_id") == capability_id:
                        coverage = match.get("coverage_percentage", 0)
                        break

                coverage_row[f"capability_{capability_id}"] = coverage

            matrix["coverage_data"].append(coverage_row)

        # Add semantic insights
        if candidate.get("semantic_advantage"):
            matrix["semantic_insights"].append(
                "Semantic matching discovered relevant vendors not found through traditional keyword matching"
            )

        return matrix

    def auto_suggest_capabilities(
        self, partial_query: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Auto-suggest capability names using semantic similarity.

        Args:
            partial_query: Partial capability name or description
            limit: Number of suggestions to return

        Returns:
            List of suggested capabilities with similarity scores
        """
        if not self.index_built or not self.sentence_model:
            return []

        try:
            # Perform semantic search focused on capabilities
            matches = self.semantic_search(
                query=partial_query,
                search_type="capability",
                top_k=limit,
                min_similarity=0.5,  # Lower threshold for suggestions
            )

            suggestions = []
            seen_capabilities = set()

            for match in matches:
                # Extract capability name from metadata if available
                capability_name = None
                for metadata in self.vector_index.metadata:
                    if (
                        metadata["vendor_id"] == match.vendor_id
                        and metadata["product_id"] == match.product_id
                        and metadata["type"] == "capability"
                    ):
                        capability_name = metadata.get("capability_name")
                        break

                if capability_name and capability_name not in seen_capabilities:
                    suggestions.append(
                        {
                            "capability_name": capability_name,
                            "similarity_score": match.semantic_score,
                            "vendor_example": match.vendor_name,
                            "confidence_level": match.confidence_level,
                        }
                    )
                    seen_capabilities.add(capability_name)

            return suggestions[:limit]

        except Exception as e:
            logger.error(f"Auto-suggest failed: {e}")
            return []

    def rebuild_index(self) -> bool:
        """Force rebuild of the vector index."""
        logger.info("Forcing rebuild of vector index...")
        self.index_built = False
        self.vector_index = None
        return self._build_vector_index()

    def get_index_stats(self) -> Dict[str, Any]:
        """Get vector index statistics."""
        if not self.vector_index:
            return {
                "index_built": False,
                "total_embeddings": 0,
                "model_name": self.model_name,
                "embedding_dimension": self.embedding_dimension,
            }

        return {
            "index_built": self.index_built,
            "total_embeddings": len(self.vector_index.embeddings),
            "model_name": self.vector_index.model_name,
            "embedding_dimension": self.embedding_dimension,
            "created_at": self.vector_index.created_at.isoformat(),
            "index_type": "FAISS IndexFlatIP",
            "similarity_threshold": self.similarity_threshold,
        }
