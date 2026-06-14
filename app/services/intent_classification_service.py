"""
Intent Classification Service - ML-based intent classification beyond template matching

Provides production-grade intent classification using machine learning models
with confidence scoring and entity extraction.
"""

import asyncio
import json
import logging
import pickle
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from flask import current_app
from sqlalchemy import text

from app import db

logger = logging.getLogger(__name__)


class IntentResult:
    """Result of intent classification"""

    def __init__(
        self,
        primary_intent: str,
        confidence: float,
        entities: List[Dict[str, Any]],
        alternative_intents: List[Dict[str, Any]],
    ):
        self.primary_intent = primary_intent
        self.confidence = confidence
        self.entities = entities
        self.alternative_intents = alternative_intents


class EntityExtractor:
    """Entity extraction for intent classification"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.entity_patterns = self._load_entity_patterns()

    def _load_entity_patterns(self) -> Dict[str, Any]:
        """Load entity extraction patterns"""
        return {
            "capability_name": {
                "patterns": [
                    r"\b(capability|capabilities?)\b",
                    r"\b(business capability|business capabilities?)\b",
                    r"\b(enterprise capability|enterprise capabilities?)\b",
                ],
                "extractors": [self._extract_capability_from_context],
            },
            "vendor_name": {
                "patterns": [
                    r"\b(vendor|vendors?)\b",
                    r"\b(supplier|suppliers?)\b",
                    r"\b(provider|providers?)\b",
                ],
                "extractors": [self._extract_vendor_from_context],
            },
            "technology": {
                "patterns": [
                    r"\b(technology|technologies?)\b",
                    r"\b(stack|stacks?)\b",
                    r"\b(platform|platforms?)\b",
                ],
                "extractors": [self._extract_technology_from_context],
            },
            "maturity_level": {
                "patterns": [
                    r"\b(mature|maturity|matured)\b",
                    r"\b(immature|immaturity|immatured)\b",
                    r"\b(initial|developing|defined|managed|optimized|innovating)\b",
                ],
                "extractors": [self._extract_maturity_from_context],
            },
            "severity": {
                "patterns": [
                    r"\b(severity|severe|critical|high|medium|low)\b",
                    r"\b(risk|risks?)\b",
                    r"\b(issue|issues?)\b",
                ],
                "extractors": [self._extract_severity_from_context],
            },
            "application": {
                "patterns": [
                    r"\b(application|applications?)\b",
                    r"\b(app|apps?)\b",
                    r"\b(system|systems?)\b",
                ],
                "extractors": [self._extract_application_from_context],
            },
        }

    def extract_entities(self, text: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract entities from text using pattern matching and context.

        Args:
            text: Text to extract entities from
            context: Additional context for entity extraction

        Returns:
            List of extracted entities
        """
        entities = []
        text_lower = text.lower()

        for entity_type, config in self.entity_patterns.items():
            # Check if patterns match
            pattern_matched = any(re.search(pattern, text_lower) for pattern in config["patterns"])

            if pattern_matched:
                # Extract entities using extractors
                for extractor in config["extractors"]:
                    extracted = extractor(text, context)
                    if extracted:
                        entities.extend(extracted)

        return entities

    def _extract_capability_from_context(
        self, text: str, context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Extract capability names from context"""
        entities = []
        text_lower = text.lower()

        # Get capabilities from context
        if "capabilities" in context:
            capabilities = context["capabilities"]

            for capability in capabilities:
                cap_name = capability.get("name", "").lower()
                if cap_name and cap_name in text_lower:
                    entities.append(
                        {
                            "type": "capability_name",
                            "value": capability["name"],
                            "confidence": 0.9,
                            "metadata": capability,
                        }
                    )

        # Extract generic capability mentions
        import re

        capability_patterns = [
            r'capability\s+["\']?([^"\']+)["\']?',
            r'capabilities?\s+["\']?([^"\']+)["\']?',
            r'analyze\s+["\']?([^"\']+)["\']?\s+capability',
        ]

        for pattern in capability_patterns:
            matches = re.findall(pattern, text_lower)
            for match in matches:
                entities.append(
                    {
                        "type": "capability_name",
                        "value": match,
                        "confidence": 0.7,
                        "metadata": {"source": "pattern_extraction"},
                    }
                )

        return entities

    def _extract_vendor_from_context(
        self, text: str, context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Extract vendor names from context"""
        entities = []
        text_lower = text.lower()

        # Get vendors from context
        if "vendors" in context:
            vendors = context["vendors"]

            for vendor in vendors:
                vendor_name = vendor.get("name", "").lower()
                if vendor_name and vendor_name in text_lower:
                    entities.append(
                        {
                            "type": "vendor_name",
                            "value": vendor["name"],
                            "confidence": 0.9,
                            "metadata": vendor,
                        }
                    )

        return entities

    def _extract_technology_from_context(
        self, text: str, context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Extract technology names from context"""
        entities = []

        # Common technology keywords
        tech_keywords = [
            "java",
            "python",
            "javascript",
            "react",
            "angular",
            "vue",
            "docker",
            "kubernetes",
            "aws",
            "azure",
            "gcp",
            "postgresql",
            "mysql",
            "mongodb",
            "redis",
            "microservices",
            "serverless",
            "api",
            "rest",
            "graphql",
        ]

        text_lower = text.lower()
        for tech in tech_keywords:
            if tech in text_lower:
                entities.append(
                    {"type": "technology", "value": tech, "confidence": 0.6, "metadata": {}}
                )

        return entities

    def _extract_maturity_from_context(
        self, text: str, context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Extract maturity levels from text"""
        entities = []

        maturity_mapping = {
            "initial": "Initial",
            "developing": "Developing",
            "defined": "Defined",
            "managed": "Managed",
            "optimized": "Optimized",
            "innovating": "Innovating",
        }

        text_lower = text.lower()
        for key, value in maturity_mapping.items():
            if key in text_lower:
                entities.append(
                    {
                        "type": "maturity_level",
                        "value": value,
                        "confidence": 0.8,
                        "metadata": {"level": key},
                    }
                )

        return entities

    def _extract_severity_from_context(
        self, text: str, context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Extract severity levels from text"""
        entities = []

        severity_mapping = {
            "critical": "Critical",
            "high": "High",
            "medium": "Medium",
            "low": "Low",
        }

        text_lower = text.lower()
        for key, value in severity_mapping.items():
            if key in text_lower:
                entities.append(
                    {
                        "type": "severity",
                        "value": value,
                        "confidence": 0.8,
                        "metadata": {"level": key},
                    }
                )

        return entities

    def _extract_application_from_context(
        self, text: str, context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Extract application names from context"""
        entities = []
        text_lower = text.lower()

        # Get applications from context
        if "applications" in context:
            applications = context["applications"]

            for app in applications:
                app_name = app.get("name", "").lower()
                if app_name and app_name in text_lower:
                    entities.append(
                        {
                            "type": "application",
                            "value": app["name"],
                            "confidence": 0.9,
                            "metadata": app,
                        }
                    )

        return entities


class IntentClassifier:
    """Machine learning based intent classifier"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.intent_mapping = self._load_intent_mapping()
        self.model_path = Path("models/intent_classifier.pkl")
        self.vectorizer_path = Path("models/intent_vectorizer.pkl")

        # Try to load trained model
        self.model = self._load_model()
        self.vectorizer = self._load_vectorizer()

        # Fallback to rule-based classification
        self.rule_classifier = RuleBasedIntentClassifier()

    def _load_intent_mapping(self) -> Dict[str, Any]:
        """Load intent configuration"""
        return {
            "capability_analysis": {
                "description": "Analyze business capabilities",
                "keywords": ["analyze", "assess", "evaluate", "capability", "maturity", "business"],
                "patterns": [
                    r"analyze\s+capability",
                    r"assess\s+maturity",
                    r"evaluate\s+business\s+capability",
                    r"capability\s+analysis",
                    r"maturity\s+assessment",
                ],
                "responses": ["capability_analysis_template"],
                "confidence_threshold": 0.7,
            },
            "gap_detection": {
                "description": "Identify gaps in capabilities",
                "keywords": ["gap", "missing", "identify", "detect", "gap analysis"],
                "patterns": [
                    r"identify\s+gaps?",
                    r"gap\s+analysis",
                    r"missing\s+capabilities?",
                    r"detect\s+gaps?",
                    r"capability\s+gaps?",
                ],
                "responses": ["gap_analysis_template"],
                "confidence_threshold": 0.7,
            },
            "vendor_evaluation": {
                "description": "Evaluate vendors and products",
                "keywords": ["vendor", "evaluate", "compare", "assessment", "product"],
                "patterns": [
                    r"evaluate\s+vendor",
                    r"compare\s+vendors?",
                    r"vendor\s+assessment",
                    r"product\s+evaluation",
                    r"vendor\s+analysis",
                ],
                "responses": ["vendor_evaluation_template"],
                "confidence_threshold": 0.7,
            },
            "technology_analysis": {
                "description": "Analyze technology stack and architecture",
                "keywords": ["technology", "stack", "architecture", "technical", "platform"],
                "patterns": [
                    r"analyze\s+technology",
                    r"technology\s+stack",
                    r"architecture\s+analysis",
                    r"technical\s+assessment",
                    r"platform\s+evaluation",
                ],
                "responses": ["technology_analysis_template"],
                "confidence_threshold": 0.7,
            },
            "risk_assessment": {
                "description": "Assess risks and issues",
                "keywords": ["risk", "assessment", "issue", "problem", "concern"],
                "patterns": [
                    r"risk\s+assessment",
                    r"assess\s+risk",
                    r"identify\s+risk",
                    r"risk\s+analysis",
                    r"issue\s+assessment",
                ],
                "responses": ["risk_assessment_template"],
                "confidence_threshold": 0.7,
            },
            "auto_mapping": {
                "description": "Auto-map applications to capabilities, processes, or ArchiMate elements",
                "keywords": [
                    "auto-map",
                    "automap",
                    "map applications",
                    "map apps",
                    "auto map",
                    "mapping",
                    "map to capabilities",
                    "map to processes",
                    "map to apqc",
                    "generate mappings",
                ],
                "patterns": [
                    r"auto[- ]?map",
                    r"map\s+(all\s+)?applications?",
                    r"map\s+(all\s+)?apps?",
                    r"map\s+to\s+(capabilities?|processes?|apqc)",
                    r"generate\s+mappings?",
                    r"create\s+mappings?",
                    r"bulk\s+map",
                    r"intelligent\s+map",
                    r"ai\s+map",
                ],
                "responses": ["auto_mapping_template"],
                "confidence_threshold": 0.75,
            },
            "information_request": {
                "description": "General information request",
                "keywords": ["what", "how", "show", "list", "find", "search"],
                "patterns": [r"what\s+is", r"how\s+to", r"show\s+me", r"find\s+", r"search\s+for"],
                "responses": ["general_query_template"],
                "confidence_threshold": 0.6,
            },
            "data_modification": {
                "description": "Modify or create data",
                "keywords": ["create", "add", "update", "modify", "delete", "remove"],
                "patterns": [
                    r"create\s+capability",
                    r"add\s+capability",
                    r"update\s+capability",
                    r"modify\s+data",
                    r"delete\s+",
                ],
                "responses": ["data_modification_template"],
                "confidence_threshold": 0.8,
            },
        }

    def _load_model(self):
        """Load trained ML model"""
        try:
            if self.model_path.exists():
                with open(self.model_path, "rb") as f:
                    return pickle.load(f)
            else:
                self.logger.info("No trained model found, using rule-based classification")
                return None
        except Exception as e:
            self.logger.error(f"Error loading model: {e}")
            return None

    def _load_vectorizer(self):
        """Load text vectorizer"""
        try:
            if self.vectorizer_path.exists():
                with open(self.vectorizer_path, "rb") as f:
                    return pickle.load(f)
            else:
                self.logger.info("No vectorizer found, using rule-based classification")
                return None
        except Exception as e:
            self.logger.error(f"Error loading vectorizer: {e}")
            return None

    def classify_intent(self, text: str, context: Dict[str, Any]) -> IntentResult:
        """
        Classify intent using ML model or rule-based fallback.

        Args:
            text: Text to classify
            context: Additional context for classification

        Returns:
            Intent classification result
        """
        try:
            # Try ML classification first
            if self.model and self.vectorizer:
                return self._ml_classify(text, context)
            else:
                # Fallback to rule-based classification
                return self.rule_classifier.classify(text, context)

        except Exception as e:
            self.logger.error(f"Error in intent classification: {e}")
            # Fallback to rule-based classification
            return self.rule_classifier.classify(text, context)

    def _ml_classify(self, text: str, context: Dict[str, Any]) -> IntentResult:
        """Classify intent using trained ML model"""
        try:
            # Preprocess text
            processed_text = self._preprocess_text(text)

            # Vectorize text
            text_vector = self.vectorizer.transform([processed_text])

            # Predict probabilities
            probabilities = self.model.predict_proba(text_vector)[0]

            # Get top intents
            intent_names = list(self.intent_mapping.keys())
            sorted_indices = np.argsort(probabilities)[::-1]

            # Build result
            top_intent = intent_names[sorted_indices[0]]
            top_confidence = float(probabilities[sorted_indices[0]])

            # Alternative intents
            alternatives = []
            for i in range(1, min(3, len(sorted_indices))):
                alt_intent = intent_names[sorted_indices[i]]
                alt_confidence = float(probabilities[sorted_indices[i]])
                alternatives.append({"intent": alt_intent, "confidence": alt_confidence})

            # Extract entities
            entity_extractor = EntityExtractor()
            entities = entity_extractor.extract_entities(text, context)

            return IntentResult(
                primary_intent=top_intent,
                confidence=top_confidence,
                entities=entities,
                alternative_intents=alternatives,
            )

        except Exception as e:
            self.logger.error(f"ML classification failed: {e}")
            raise

    def _preprocess_text(self, text: str) -> str:
        """Preprocess text for classification"""
        import re

        # Convert to lowercase
        text = text.lower()

        # Remove special characters
        text = re.sub(r"[^\w\s]", " ", text)

        # Remove extra whitespace
        text = re.sub(r"\s+", " ", text).strip()

        return text

    async def train_model(self, training_data: List[Dict[str, Any]]):
        """Train the intent classification model"""
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.naive_bayes import MultinomialNB
            from sklearn.pipeline import Pipeline

            # Extract texts and labels
            texts = [item["text"] for item in training_data]
            labels = [item["intent"] for item in training_data]

            # Create pipeline
            pipeline = Pipeline(
                [
                    ("vectorizer", TfidfVectorizer(max_features=5000, stop_words="english")),
                    ("classifier", MultinomialNB()),
                ]
            )

            # Train model
            pipeline.fit(texts, labels)

            # Save model and vectorizer
            self.model_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.model_path, "wb") as f:
                pickle.dump(pipeline, f)

            with open(self.vectorizer_path, "wb") as f:
                pickle.dump(pipeline.named_steps["vectorizer"], f)

            # Update loaded models
            self.model = pipeline
            self.vectorizer = pipeline.named_steps["vectorizer"]

            self.logger.info(f"Model trained on {len(training_data)} examples")

        except Exception as e:
            self.logger.error(f"Error training model: {e}")
            raise


class RuleBasedIntentClassifier:
    """Rule-based intent classifier as fallback"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.intent_mapping = self._load_intent_mapping()

    def _load_intent_mapping(self) -> Dict[str, Any]:
        """Load intent configuration for rule-based classification"""
        return {
            "capability_analysis": {
                "description": "Analyze business capabilities",
                "keywords": ["analyze", "assess", "evaluate", "capability", "maturity", "business"],
                "patterns": [
                    r"analyze\s+capability",
                    r"assess\s+maturity",
                    r"evaluate\s+business\s+capability",
                    r"capability\s+analysis",
                    r"maturity\s+assessment",
                ],
                "confidence_threshold": 0.7,
            },
            "gap_detection": {
                "description": "Identify gaps in capabilities",
                "keywords": ["gap", "missing", "identify", "detect", "gap analysis"],
                "patterns": [
                    r"identify\s+gaps?",
                    r"gap\s+analysis",
                    r"missing\s+capabilities?",
                    r"detect\s+gaps?",
                    r"capability\s+gaps?",
                ],
                "confidence_threshold": 0.7,
            },
            "vendor_evaluation": {
                "description": "Evaluate vendors and products",
                "keywords": ["vendor", "evaluate", "compare", "assessment", "product"],
                "patterns": [
                    r"evaluate\s+vendor",
                    r"compare\s+vendors?",
                    r"vendor\s+assessment",
                    r"product\s+evaluation",
                    r"vendor\s+analysis",
                ],
                "confidence_threshold": 0.7,
            },
            "technology_analysis": {
                "description": "Analyze technology stack and architecture",
                "keywords": ["technology", "stack", "architecture", "technical", "platform"],
                "patterns": [
                    r"analyze\s+technology",
                    r"technology\s+stack",
                    r"architecture\s+analysis",
                    r"technical\s+assessment",
                    r"platform\s+evaluation",
                ],
                "confidence_threshold": 0.7,
            },
            "risk_assessment": {
                "description": "Assess risks and issues",
                "keywords": ["risk", "assessment", "issue", "problem", "concern"],
                "patterns": [
                    r"risk\s+assessment",
                    r"assess\s+risk",
                    r"identify\s+risk",
                    r"risk\s+analysis",
                    r"issue\s+assessment",
                ],
                "confidence_threshold": 0.7,
            },
            "auto_mapping": {
                "description": "Auto-map applications to capabilities, processes, or ArchiMate elements",
                "keywords": [
                    "auto-map",
                    "automap",
                    "map applications",
                    "map apps",
                    "auto map",
                    "mapping",
                    "map to capabilities",
                    "map to processes",
                    "map to apqc",
                    "generate mappings",
                ],
                "patterns": [
                    r"auto[- ]?map",
                    r"map\s+(all\s+)?applications?",
                    r"map\s+(all\s+)?apps?",
                    r"map\s+to\s+(capabilities?|processes?|apqc)",
                    r"generate\s+mappings?",
                    r"create\s+mappings?",
                    r"bulk\s+map",
                    r"intelligent\s+map",
                    r"ai\s+map",
                ],
                "confidence_threshold": 0.75,
            },
            "information_request": {
                "description": "General information request",
                "keywords": ["what", "how", "show", "list", "find", "search"],
                "patterns": [r"what\s+is", r"how\s+to", r"show\s+me", r"find\s+", r"search\s+for"],
                "confidence_threshold": 0.6,
            },
            "data_modification": {
                "description": "Modify or create data",
                "keywords": ["create", "add", "update", "modify", "delete", "remove"],
                "patterns": [
                    r"create\s+capability",
                    r"add\s+capability",
                    r"update\s+capability",
                    r"modify\s+data",
                    r"delete\s+",
                ],
                "confidence_threshold": 0.8,
            },
        }

    def classify(self, text: str, context: Dict[str, Any]) -> IntentResult:
        """
        Classify intent using rule-based approach.

        Args:
            text: Text to classify
            context: Additional context for classification

        Returns:
            Intent classification result
        """
        text_lower = text.lower()
        intent_scores = {}

        # Score each intent
        for intent, config in self.intent_mapping.items():
            score = 0.0

            # Keyword matching
            keyword_matches = sum(1 for keyword in config["keywords"] if keyword in text_lower)
            score += keyword_matches * 0.3

            # Pattern matching
            import re

            pattern_matches = sum(
                1 for pattern in config["patterns"] if re.search(pattern, text_lower)
            )
            score += pattern_matches * 0.7

            intent_scores[intent] = score

        # Get top intent
        if not intent_scores or max(intent_scores.values()) == 0:
            # Default to information request
            primary_intent = "information_request"
            confidence = 0.5
        else:
            primary_intent = max(intent_scores, key=intent_scores.get)
            confidence = min(intent_scores[primary_intent] / 2.0, 1.0)

        # Get alternative intents
        sorted_intents = sorted(intent_scores.items(), key=lambda x: x[1], reverse=True)
        alternatives = []
        for intent, score in sorted_intents[1:3]:  # Top 3 alternatives
            if score > 0:
                alternatives.append({"intent": intent, "confidence": min(score / 2.0, 1.0)})

        # Extract entities
        entity_extractor = EntityExtractor()
        entities = entity_extractor.extract_entities(text, context)

        return IntentResult(
            primary_intent=primary_intent,
            confidence=confidence,
            entities=entities,
            alternative_intents=alternatives,
        )


class IntentClassificationService:
    """Main service for intent classification"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.intent_classifier = IntentClassifier()
        self.entity_extractor = EntityExtractor()
        self.intent_mapping = self.intent_classifier.intent_mapping

        # Learning data storage
        self.interaction_log = []

    def classify_intent(self, message: str, context: Dict[str, Any]) -> IntentResult:
        """
        Classify intent with confidence scoring and entity extraction.

        Args:
            message: User message
            context: Additional context

        Returns:
            Intent classification result
        """
        try:
            # Preprocess message
            cleaned_message = self._preprocess_message(message)

            # Extract entities
            entities = self.entity_extractor.extract_entities(cleaned_message, context)

            # Classify intent
            intent_result = self.intent_classifier.classify_intent(cleaned_message, context)

            # Update entities from classifier
            intent_result.entities.extend(entities)

            # Remove duplicate entities
            intent_result.entities = self._deduplicate_entities(intent_result.entities)

            # Log interaction for learning
            self._log_interaction(message, intent_result, context)

            return intent_result

        except Exception as e:
            self.logger.error(f"Error in intent classification: {e}")
            # Return default result
            return IntentResult(
                primary_intent="information_request",
                confidence=0.5,
                entities=[],
                alternative_intents=[],
            )

    def _preprocess_message(self, message: str) -> str:
        """Preprocess message for classification"""
        import re

        # Remove special characters but keep spaces
        message = re.sub(r"[^\w\s]", " ", message)

        # Normalize whitespace
        message = re.sub(r"\s+", " ", message).strip()

        return message

    def _deduplicate_entities(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate entities"""
        seen = set()
        deduplicated = []

        for entity in entities:
            key = (entity["type"], entity["value"])
            if key not in seen:
                seen.add(key)
                deduplicated.append(entity)

        return deduplicated

    def _log_interaction(self, message: str, intent_result: IntentResult, context: Dict[str, Any]):
        """Log interaction for learning and analytics"""
        self.interaction_log.append(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "message": message,
                "predicted_intent": intent_result.primary_intent,
                "confidence": intent_result.confidence,
                "entities": intent_result.entities,
                "context": context,
            }
        )

        # Keep log size manageable
        if len(self.interaction_log) > 10000:
            self.interaction_log = self.interaction_log[-5000:]

    def update_intent_from_feedback(self, message: str, actual_intent: str):
        """
        Update intent classification based on user feedback.

        Args:
            message: Original message
            actual_intent: Correct intent from user feedback
        """
        try:
            # Find the interaction
            for interaction in reversed(self.interaction_log):
                if interaction["message"] == message:
                    interaction["actual_intent"] = actual_intent
                    break

            # Retrain model if we have enough feedback
            feedback_data = [
                interaction
                for interaction in self.interaction_log
                if "actual_intent" in interaction
            ]

            if len(feedback_data) >= 100:  # Minimum data for retraining
                self._retrain_model(feedback_data)

        except Exception as e:
            self.logger.error(f"Error updating intent from feedback: {e}")

    def _retrain_model(self, feedback_data: List[Dict[str, Any]]):
        """Retrain the intent classification model with feedback data"""
        try:
            # Prepare training data
            training_data = [
                {"text": item["message"], "intent": item["actual_intent"]} for item in feedback_data
            ]

            # Retrain the model
            self.intent_classifier.train_model(training_data)

            self.logger.info(f"Model retrained with {len(training_data)} feedback examples")

        except Exception as e:
            self.logger.error(f"Error retraining model: {e}")

    def get_intent_stats(self) -> Dict[str, Any]:
        """Get intent classification statistics"""
        try:
            total_interactions = len(self.interaction_log)

            if total_interactions == 0:
                return {
                    "total_interactions": 0,
                    "intent_distribution": {},
                    "average_confidence": 0.0,
                    "feedback_rate": 0.0,
                }

            # Intent distribution
            intent_counts = {}
            confidence_sum = 0.0
            feedback_count = 0

            for interaction in self.interaction_log:
                intent = interaction["predicted_intent"]
                confidence = interaction["confidence"]

                intent_counts[intent] = intent_counts.get(intent, 0) + 1
                confidence_sum += confidence

                if "actual_intent" in interaction:
                    feedback_count += 1

            return {
                "total_interactions": total_interactions,
                "intent_distribution": intent_counts,
                "average_confidence": confidence_sum / total_interactions,
                "feedback_rate": feedback_count / total_interactions
                if total_interactions > 0
                else 0.0,
            }

        except Exception as e:
            self.logger.error(f"Error getting intent stats: {e}")
            return {}

    def get_available_intents(self) -> List[Dict[str, Any]]:
        """Get list of available intents with descriptions"""
        return [
            {
                "intent": intent,
                "description": config["description"],
                "keywords": config["keywords"],
                "confidence_threshold": config["confidence_threshold"],
            }
            for intent, config in self.intent_mapping.items()
        ]
