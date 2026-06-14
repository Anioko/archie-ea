"""
AI Semantic Discovery Initialization Command

Management command to initialize and populate the vector database
for AI-powered semantic vendor discovery.

Usage:
    python manage.py init-semantic-discovery
    python manage.py init-semantic-discovery --reindex
    python manage.py init-semantic-discovery --products-only
    python manage.py init-semantic-discovery --capabilities-only
"""

import logging

import click
from flask.cli import with_appcontext

from app import db
from app.models.business_capabilities import BusinessCapability
from app.models.vendor.vendor_organization import VendorProduct
from app.services.ai_semantic_discovery_service import get_semantic_discovery_service

logger = logging.getLogger(__name__)


@click.command()
@click.option("--reindex", is_flag=True, help="Force reindexing of all data")
@click.option("--products-only", is_flag=True, help="Only index vendor products")
@click.option("--capabilities-only", is_flag=True, help="Only index business capabilities")
@click.option("--products-limit", default=1000, help="Limit number of products to index")
@click.option("--capabilities-limit", default=500, help="Limit number of capabilities to index")
@with_appcontext
def init_semantic_discovery(
    reindex, products_only, capabilities_only, products_limit, capabilities_limit
):
    """Initialize AI semantic discovery vector database."""

    click.echo("🚀 Initializing AI Semantic Discovery System...")

    # Get the semantic discovery service
    semantic_service = get_semantic_discovery_service()

    # Check service availability
    if not semantic_service.embedding_model:
        click.echo("❌ Error: Embedding model not available")
        click.echo("   Please ensure sentence-transformers is properly installed")
        return 1

    if not semantic_service.chroma_client:
        click.echo("❌ Error: Vector database not available")
        click.echo("   Please ensure ChromaDB is properly installed")
        return 1

    click.echo("✅ Semantic discovery service is available")

    # Get current statistics
    stats = semantic_service.get_discovery_statistics()
    click.echo(f"📊 Current Status:")
    click.echo(f"   - Indexed Products: {stats.get('indexed_products', 0)}")
    click.echo(f"   - Indexed Capabilities: {stats.get('indexed_capabilities', 0)}")
    click.echo(f"   - Device: {stats.get('device', 'unknown')}")
    click.echo(f"   - Embedding Dimension: {stats.get('embedding_dimension', 'unknown')}")

    # Check if reindex is needed
    if not reindex:
        total_products = db.session.query(VendorProduct).count()
        total_capabilities = db.session.query(BusinessCapability).count()

        indexed_products = stats.get("indexed_products", 0)
        indexed_capabilities = stats.get("indexed_capabilities", 0)

        if indexed_products >= total_products and indexed_capabilities >= total_capabilities:
            click.echo("✅ Vector database is already up to date")
            click.echo("   Use --reindex to force reindexing")
            return 0

    # Index vendor products
    if not capabilities_only:
        click.echo("\n📦 Indexing Vendor Products...")

        product_result = semantic_service.index_vendor_products(limit=products_limit)

        if product_result.get("success"):
            click.echo(f"   ✅ Successfully indexed {product_result['indexed_count']} products")
            click.echo(f"   📏 Embedding dimension: {product_result['embedding_dimension']}")
            click.echo(f"   📚 Collection size: {product_result['collection_size']}")
        else:
            click.echo(
                f"   ❌ Product indexing failed: {product_result.get('error', 'Unknown error')}"
            )
            if not products_only:
                click.echo("   Continuing with capability indexing...")

    # Index business capabilities
    if not products_only:
        click.echo("\n🎯 Indexing Business Capabilities...")

        capability_result = semantic_service.index_business_capabilities(limit=capabilities_limit)

        if capability_result.get("success"):
            click.echo(
                f"   ✅ Successfully indexed {capability_result['indexed_count']} capabilities"
            )
            click.echo(f"   📏 Embedding dimension: {capability_result['embedding_dimension']}")
            click.echo(f"   📚 Collection size: {capability_result['collection_size']}")
        else:
            click.echo(
                f"   ❌ Capability indexing failed: {capability_result.get('error', 'Unknown error')}"
            )

    # Final statistics
    final_stats = semantic_service.get_discovery_statistics()
    click.echo(f"\n📊 Final Status:")
    click.echo(f"   - Indexed Products: {final_stats.get('indexed_products', 0)}")
    click.echo(f"   - Indexed Capabilities: {final_stats.get('indexed_capabilities', 0)}")
    click.echo(f"   - Search Cache Size: {final_stats.get('search_cache_size', 0)}")

    click.echo("\n🎉 AI Semantic Discovery initialization complete!")
    click.echo("   You can now use semantic search at /api/vendor-discovery/search")

    return 0


@click.command()
@click.option("--query", default="enterprise ERP system", help="Test query for semantic search")
@click.option("--limit", default=5, help="Number of results to return")
@with_appcontext
def test_semantic_search(query, limit):
    """Test the semantic search functionality."""

    click.echo(f"🔍 Testing Semantic Search...")
    click.echo(f"   Query: '{query}'")
    click.echo(f"   Limit: {limit}")

    semantic_service = get_semantic_discovery_service()

    if not semantic_service.embedding_model or not semantic_service.product_collection:
        click.echo("❌ Semantic discovery service not available")
        click.echo("   Run 'python manage.py init-semantic-discovery' first")
        return 1

    # Perform semantic search
    results = semantic_service.semantic_search_vendors(
        query=query, n_results=limit, similarity_threshold=0.3
    )

    if "error" in results:
        click.echo(f"❌ Search failed: {results['error']}")
        return 1

    click.echo(f"\n📊 Search Results:")
    click.echo(f"   Found: {results['total_found']} vendors")
    click.echo(f"   Query: '{results['query']}'")

    if results["results"]:
        click.echo(f"\n🏆 Top Results:")
        for i, result in enumerate(results["results"][:limit], 1):
            click.echo(f"   {i}. {result['product_name']} ({result['vendor_name']})")
            click.echo(f"      Similarity: {result['similarity_score']:.3f}")
            click.echo(f"      Coverage: {result['capability_coverage']:.1f}%")
            click.echo(f"      Confidence: {result['confidence_level']}")
            if result["relevance_factors"]:
                click.echo(f"      Factors: {', '.join(result['relevance_factors'])}")
            click.echo()
    else:
        click.echo("   No results found")

    click.echo("✅ Semantic search test completed successfully!")
    return 0


@click.command()
@with_appcontext
def semantic_discovery_status():
    """Show the status of the semantic discovery system."""

    click.echo("📊 AI Semantic Discovery Status")
    click.echo("=" * 40)

    semantic_service = get_semantic_discovery_service()
    stats = semantic_service.get_discovery_statistics()

    # Service status
    click.echo(f"🔧 Service Status:")
    click.echo(
        f"   Embedding Model: {'✅ Available' if stats.get('embedding_model_loaded') else '❌ Not Available'}"
    )
    click.echo(
        f"   Vector Database: {'✅ Available' if stats.get('vector_db_available') else '❌ Not Available'}"
    )
    click.echo(
        f"   LLM API: {'✅ Available' if stats.get('llm_api_available') else '❌ Not Available'}"
    )
    click.echo(f"   Device: {stats.get('device', 'Unknown')}")

    # Indexing status
    click.echo(f"\n📚 Indexing Status:")
    click.echo(f"   Indexed Products: {stats.get('indexed_products', 0)}")
    click.echo(f"   Indexed Capabilities: {stats.get('indexed_capabilities', 0)}")

    # Database counts
    total_products = db.session.query(VendorProduct).count()
    total_capabilities = db.session.query(BusinessCapability).count()

    click.echo(f"   Total Products in DB: {total_products}")
    click.echo(f"   Total Capabilities in DB: {total_capabilities}")

    # Coverage
    product_coverage = (
        (stats.get("indexed_products", 0) / total_products * 100) if total_products > 0 else 0
    )
    capability_coverage = (
        (stats.get("indexed_capabilities", 0) / total_capabilities * 100)
        if total_capabilities > 0
        else 0
    )

    click.echo(f"   Product Coverage: {product_coverage:.1f}%")
    click.echo(f"   Capability Coverage: {capability_coverage:.1f}%")

    # Cache status
    click.echo(f"\n💾 Cache Status:")
    click.echo(f"   Search Cache Size: {stats.get('search_cache_size', 0)}")

    # Overall status
    all_available = (
        stats.get("embedding_model_loaded", False)
        and stats.get("vector_db_available", False)
        and product_coverage >= 90
        and capability_coverage >= 90
    )

    click.echo(f"\n🎯 Overall Status: {'✅ Ready' if all_available else '⚠️ Needs Attention'}")

    if not all_available:
        click.echo("\n💡 Recommendations:")
        if not stats.get("embedding_model_loaded"):
            click.echo("   - Install sentence-transformers package")
        if not stats.get("vector_db_available"):
            click.echo("   - Install chromadb package")
        if product_coverage < 90:
            click.echo("   - Run 'python manage.py init-semantic-discovery' to index products")
        if capability_coverage < 90:
            click.echo("   - Run 'python manage.py init-semantic-discovery' to index capabilities")

    return 0


# Register commands with Flask CLI
def register_commands(cli):
    """Register semantic discovery commands with Flask CLI."""
    cli.add_command(init_semantic_discovery)
    cli.add_command(test_semantic_search)
    cli.add_command(semantic_discovery_status)
