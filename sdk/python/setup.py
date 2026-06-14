"""
Setup script for Enterprise Architecture Python SDK
"""

from setuptools import find_packages, setup

with open("README.md", "r", encoding="utf - 8") as fh:
    long_description = fh.read()

setup(
    name="enterprise-sdk",
    version="2.0.0",
    author="Enterprise Architecture Team",
    author_email="ea-team@company.com",
    description="Python SDK for Enterprise Architecture Platform API",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Anioko/archie",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.8",
    install_requires=[
        "requests>=2.25.0",
        "urllib3>=1.26.0",
    ],
    extras_require={
        "dev": [
            "pytest>=6.0.0",
            "pytest-cov>=2.0.0",
            "black>=21.0.0",
            "isort>=5.0.0",
            "flake8>=3.8.0",
            "mypy>=0.800",
        ],
    },
)
