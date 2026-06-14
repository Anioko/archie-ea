"""
MDD Code Generation Service - Hybrid Template + LLM Approach

Adapted from MDD flask-base-master for archie integration.
Uses Jinja2 templates for deterministic code structure and LLM for complex business logic.

This service provides the core MDD hybrid generation capability:
1. Template-first generation (deterministic, fast, validated)
2. LLM fallback for complex/custom scenarios
3. Code validation and quality checks
4. Multi-language support (Python, Java, TypeScript, Salesforce)
"""
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from flask import current_app
from jinja2 import Environment, FileSystemLoader
from jinja2 import Template as Jinja2Template
from jinja2 import select_autoescape

from app import db
from app.services.code_validator import CodeValidator, validate_code_artifact
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class TechnologyStack:
    """Technology stack configuration for code generation."""

    def __init__(
        self, primary_language: str, framework: str = None, primary_database: str = None, **kwargs
    ):
        self.primary_language = primary_language
        self.framework = framework or self._get_default_framework(primary_language)
        self.primary_database = primary_database or "postgresql"
        self.additional_config = kwargs

    @staticmethod
    def _get_default_framework(language: str) -> str:
        """Get default framework for language."""
        defaults = {
            "python": "Flask",
            "java": "Spring Boot",
            "typescript": "NestJS",
            "javascript": "Express",
            "salesforce": "Apex",
        }
        return defaults.get(language.lower(), "Generic")


class UMLElement:
    """
    Adapter class to represent UML elements from archie ApplicationComponent.
    This bridges the gap between archie's data model and MDD's UML-based generation.
    """

    def __init__(
        self,
        name: str,
        element_type: str = "class",
        stereotype: str = None,
        package: str = None,
        description: str = None,
        **kwargs,
    ):
        self.name = name
        self.element_type = element_type
        self.stereotype = stereotype or element_type
        self.package = package
        self.description = description
        self._attributes = []
        self._methods = []
        self.metadata = kwargs

    def add_attribute(
        self, name: str, data_type: str, visibility: str = "private", default_value: str = None
    ):
        """Add an attribute to this element."""
        self._attributes.append(
            {
                "name": name,
                "data_type": data_type,
                "visibility": visibility,
                "default_value": default_value,
            }
        )

    def add_method(
        self,
        name: str,
        return_type: str = "void",
        parameters: str = "",
        visibility: str = "public",
        is_constructor: bool = False,
    ):
        """Add a method to this element."""
        self._methods.append(
            {
                "name": name,
                "return_type": return_type,
                "parameters": parameters,
                "visibility": visibility,
                "is_constructor": is_constructor,
            }
        )

    @property
    def attributes(self):
        """Return attributes as a mock query result."""

        class AttributeList:
            def __init__(self, attrs):
                self._attrs = attrs

            def all(self):
                return [type("Attribute", (), attr) for attr in self._attrs]

        return AttributeList(self._attributes)

    @property
    def methods(self):
        """Return methods as a mock query result."""

        class MethodList:
            def __init__(self, meths):
                self._meths = meths

            def all(self):
                return [type("Method", (), meth) for meth in self._meths]

        return MethodList(self._methods)


class CodeArtifact:
    """Generated code artifact."""

    def __init__(
        self, name: str, type: str, language: str, content: str, architecture_id: int = None
    ):
        self.name = name
        self.type = type
        self.language = language
        self.content = content
        self.architecture_id = architecture_id
        self.metadata = {}
        self.created_at = datetime.utcnow()
        self.validation_status = None
        self.validation_errors = []
        self.validation_warnings = []


class MDDCodeGenerationService:
    """
    MDD Hybrid Code Generation Service.

    Combines template-based generation with LLM fallback for robust code generation.
    """

    @staticmethod
    def get_template_env(language: str) -> Environment:
        """
        Get Jinja2 environment for code templates.

        Args:
            language: Programming language

        Returns:
            Configured Jinja2 Environment
        """
        templates_path = os.path.join(
            current_app.root_path, "services", "code_templates", language.lower()
        )

        os.makedirs(templates_path, exist_ok=True)

        env = Environment(
            loader=FileSystemLoader(templates_path),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        return env

    @staticmethod
    def generate_from_uml(
        uml_elements: List[UMLElement],
        technology_stack: TechnologyStack,
        architecture_context: Dict = None,
    ) -> List[CodeArtifact]:
        """
        Generate code artifacts from UML using hybrid template + LLM approach.

        Args:
            uml_elements: List of UMLElement instances
            technology_stack: TechnologyStack configuration
            architecture_context: Optional architecture metadata

        Returns:
            List of CodeArtifact instances
        """
        artifacts = []
        language = technology_stack.primary_language
        framework = technology_stack.framework

        template_env = MDDCodeGenerationService.get_template_env(language)

        for element in uml_elements:
            template_name = MDDCodeGenerationService._get_template_name(
                element, language, framework
            )

            try:
                artifact = MDDCodeGenerationService._generate_from_template(
                    template_env, template_name, element, technology_stack
                )
                if artifact:
                    artifacts.append(artifact)
                    logger.info(f"✓ Template generation succeeded: {artifact.name}")
                    continue
            except Exception as e:
                logger.info(f"Template generation failed for {element.name}: {str(e)}")

            try:
                artifact = MDDCodeGenerationService._generate_from_llm(element, technology_stack)
                if artifact:
                    artifacts.append(artifact)
                    logger.info(f"✓ LLM generation succeeded: {artifact.name}")
            except Exception as e:
                logger.error(f"LLM generation failed for {element.name}: {str(e)}")

        return artifacts

    @staticmethod
    def _get_template_name(element: UMLElement, language: str, framework: str) -> str:
        """Determine template name based on element type and stereotype."""
        stereotype = (
            element.stereotype.lower() if element.stereotype else element.element_type.lower()
        )

        template_map = {
            "entity": "entity.j2",
            "model": "entity.j2",
            "controller": "controller.j2",
            "service": "service.j2",
            "repository": "repository.j2",
            "dto": "dto.j2",
            "interface": "interface.j2",
            "enum": "enum.j2",
        }

        template_name = template_map.get(stereotype, f"{stereotype}.j2")

        if framework:
            normalized_framework = framework.lower().replace(" ", "-").replace("_", "-")
            framework_template = f"{normalized_framework}_{template_name}"
            return framework_template

        return template_name

    @staticmethod
    def _generate_from_template(
        template_env: Environment,
        template_name: str,
        element: UMLElement,
        technology_stack: TechnologyStack,
    ) -> Optional[CodeArtifact]:
        """
        Generate code using Jinja2 template.

        Args:
            template_env: Jinja2 Environment
            template_name: Template file name
            element: UMLElement instance
            technology_stack: TechnologyStack configuration

        Returns:
            CodeArtifact instance or None if template not found
        """
        try:
            template = template_env.get_template(template_name)
            logger.info(f"[TEMPLATE] Using: {template_name}")
        except Exception as e:
            logger.info(f"[TEMPLATE] Not found: {template_name} - {str(e)}")
            return None

        relationships = MDDCodeGenerationService._extract_relationships(element, technology_stack)

        context = {
            "element": element,
            "class_name": element.name,
            "package": element.package or "com.generated",
            "attributes": [
                {
                    "name": attr.name,
                    "type": attr.data_type,
                    "visibility": attr.visibility or "private",
                    "default_value": attr.default_value,
                }
                for attr in element.attributes.all()
            ],
            "methods": [
                {
                    "name": method.name,
                    "return_type": method.return_type or "void",
                    "parameters": method.parameters or "",
                    "visibility": method.visibility or "public",
                    "is_constructor": method.is_constructor,
                }
                for method in element.methods.all()
            ],
            "relationships": relationships,
            "technology_stack": {
                "language": technology_stack.primary_language,
                "framework": technology_stack.framework,
                "database": technology_stack.primary_database,
                "orm": "sqlalchemy" if technology_stack.primary_language == "python" else "jpa",
            },
            "imports": MDDCodeGenerationService._get_imports(element, technology_stack),
        }

        try:
            code_content = template.render(**context)

            code_content = MDDCodeGenerationService._optimize_imports(
                code_content, technology_stack.primary_language, technology_stack.framework
            )

        except Exception as e:
            logger.error(f"[TEMPLATE] Rendering failed: {str(e)}")
            return None

        file_name = MDDCodeGenerationService._get_file_name(element, technology_stack)

        try:
            validation_result = validate_code_artifact(
                code_content, technology_stack.primary_language, file_name
            )
            logger.info(f"✓ Code validation passed: {file_name}")
        except ValueError as e:
            logger.error(f"✗ Code validation failed: {file_name}: {e}")
            raise ValueError(f"Generated code failed validation: {e}")

        artifact = CodeArtifact(
            name=file_name,
            type="source",
            language=technology_stack.primary_language,
            content=code_content,
        )

        artifact.metadata["validation"] = {
            "validated": True,
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": validation_result.metrics,
            "warnings": validation_result.warnings,
            "source": "template",
        }

        return artifact

    @staticmethod
    def _generate_from_llm(
        element: UMLElement, technology_stack: TechnologyStack
    ) -> Optional[CodeArtifact]:
        """
        Generate code using LLM when template not available.

        Args:
            element: UMLElement instance
            technology_stack: TechnologyStack configuration

        Returns:
            CodeArtifact instance
        """
        attributes = element.attributes.all()
        methods = element.methods.all()

        attrs_str = "\n".join(
            [f"  - {attr.name}: {attr.data_type} ({attr.visibility})" for attr in attributes]
        )

        methods_str = "\n".join(
            [
                f"  - {method.name}({method.parameters}): {method.return_type} ({method.visibility})"
                for method in methods
            ]
        )

        prompt = f"""Generate {technology_stack.primary_language} code for a {element.element_type} named {element.name}.

Framework: {technology_stack.framework}
Database: {technology_stack.primary_database}
Stereotype: {element.stereotype or 'N/A'}

Class: {element.name}
Package: {element.package or 'com.example'}

Attributes:
{attrs_str or '  (none)'}

Methods:
{methods_str or '  (none)'}

Requirements:
- Follow {technology_stack.framework} best practices
- Use proper dependency injection
- Include input validation
- Add comprehensive error handling
- Include docstrings/javadoc
- Follow clean code principles
- Add type hints/annotations

Output ONLY the source code, no markdown or explanations."""

        try:
            code_content = LLMService.generate_from_prompt(prompt)
            code_content = MDDCodeGenerationService._clean_llm_response(code_content)
        except Exception as e:
            logger.error(f"LLM generation failed: {str(e)}")
            raise

        file_name = MDDCodeGenerationService._get_file_name(element, technology_stack)

        try:
            validation_result = validate_code_artifact(
                code_content, technology_stack.primary_language, file_name
            )
            logger.info(f"✓ LLM code validation passed: {file_name}")
        except ValueError as e:
            logger.error(f"✗ LLM code validation failed: {file_name}: {e}")
            raise ValueError(f"LLM-generated code failed validation: {e}")

        artifact = CodeArtifact(
            name=file_name,
            type="source",
            language=technology_stack.primary_language,
            content=code_content,
        )

        artifact.metadata["validation"] = {
            "validated": True,
            "source": "llm",
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": validation_result.metrics,
            "warnings": validation_result.warnings,
        }

        return artifact

    @staticmethod
    def _extract_relationships(element: UMLElement, technology_stack: TechnologyStack) -> Dict:
        """Extract and format relationships for code generation."""
        return {
            "foreign_keys": [],
            "collections": [],
            "inherits_from": None,
            "implements": [],
            "dependencies": [],
        }

    @staticmethod
    def _get_file_name(element: UMLElement, technology_stack: TechnologyStack) -> str:
        """Generate framework-specific file name."""
        import re

        language = technology_stack.primary_language.lower()
        framework = technology_stack.framework.lower() if technology_stack.framework else ""
        stereotype = (element.stereotype or "").lower()

        extensions = {
            "python": ".py",
            "java": ".java",
            "typescript": ".ts",
            "javascript": ".js",
            "csharp": ".cs",
            "salesforce": ".cls",
        }
        ext = extensions.get(language, ".txt")

        def to_snake_case(name):
            s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
            return re.sub("([a-z0 - 9])([A-Z])", r"\1_\2", s1).lower()

        if language == "python":
            base_name = to_snake_case(element.name)
            if "fastapi" in framework:
                if stereotype == "controller":
                    return f"{base_name}_router{ext}"
                elif stereotype in ["service", "repository"]:
                    return f"{base_name}_{stereotype}{ext}"
            return f"{base_name}{ext}"

        elif language == "java":
            base_name = element.name
            if "spring" in framework:
                if stereotype in ["controller", "service", "repository"]:
                    return f"{base_name}{stereotype.capitalize()}{ext}"
            return f"{base_name}{ext}"

        elif language == "typescript":
            base_name = to_snake_case(element.name)
            if "nestjs" in framework or "nest" in framework:
                if stereotype in ["controller", "service", "repository", "entity"]:
                    return f"{base_name}.{stereotype}{ext}"
            return f"{base_name}{ext}"

        elif language == "salesforce":
            return f"{element.name}{ext}"

        return f"{element.name}{ext}"

    @staticmethod
    def _get_imports(element: UMLElement, technology_stack: TechnologyStack) -> List[str]:
        """Generate standard imports based on element type and technology stack."""
        language = technology_stack.primary_language.lower()
        imports = []

        if language == "python":
            if element.element_type == "class" or element.stereotype == "Entity":
                if technology_stack.framework == "FastAPI":
                    imports.extend(
                        [
                            "from pydantic import BaseModel, Field",
                            "from typing import Optional",
                            "from datetime import datetime",
                        ]
                    )
                elif technology_stack.framework == "Flask":
                    imports.extend(
                        ["from flask_sqlalchemy import SQLAlchemy", "from datetime import datetime"]
                    )

        elif language == "java":
            if element.stereotype == "Entity":
                imports.extend(["import javax.persistence.*;", "import java.time.LocalDateTime;"])
            elif element.stereotype == "Controller":
                imports.extend(
                    [
                        "import org.springframework.web.bind.annotation.*;",
                        "import org.springframework.beans.factory.annotation.Autowired;",
                    ]
                )

        elif language == "typescript":
            if element.stereotype == "Controller":
                imports.extend(["import { Controller, Get, Post, Body } from '@nestjs/common';"])

        return imports

    @staticmethod
    def _clean_llm_response(content: str) -> str:
        """Remove markdown code blocks from LLM response."""
        if content.startswith("```"):
            lines = content.split("\n")
            lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            content = "\n".join(lines)
        return content.strip()

    @staticmethod
    def _optimize_imports(code_content: str, language: str, framework: str) -> str:
        """Optimize imports - remove duplicates, sort, group."""
        if language == "python":
            return MDDCodeGenerationService._optimize_python_imports(code_content)
        elif language == "java":
            return MDDCodeGenerationService._optimize_java_imports(code_content)
        return code_content

    @staticmethod
    def _optimize_python_imports(code_content: str) -> str:
        """Optimize Python imports."""
        lines = code_content.split("\n")
        imports = []
        from_imports = []
        other_lines = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("import "):
                imports.append(line)
            elif stripped.startswith("from "):
                from_imports.append(line)
            else:
                other_lines.append(line)

        imports = sorted(list(dict.fromkeys(imports)))
        from_imports = sorted(list(dict.fromkeys(from_imports)))

        result = []
        if imports:
            result.extend(imports)
            result.append("")
        if from_imports:
            result.extend(from_imports)
            result.append("")
        result.extend(other_lines)
        return "\n".join(result)

    @staticmethod
    def _optimize_java_imports(code_content: str) -> str:
        """Optimize Java imports."""
        lines = code_content.split("\n")
        imports = []
        other_lines = []

        for line in lines:
            if line.strip().startswith("import "):
                imports.append(line.strip())
            else:
                other_lines.append(line)

        imports = sorted(list(dict.fromkeys(imports)))

        package_line = next(
            (line for line in other_lines if line.strip().startswith("package ")), None
        )
        if package_line:
            other_lines.remove(package_line)
            result = [package_line, ""] + imports
            if imports:
                result.append("")
            result.extend(other_lines)
            return "\n".join(result)

        result = imports
        if imports:
            result.append("")
        result.extend(other_lines)
        return "\n".join(result)
