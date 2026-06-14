"""
flask codegen-drift — detect code drift between generated files and stored manifests.

Compares the current generated_files content hashes against the stored file_manifest
from the last code generation run. Reports added, modified, and deleted files.

Usage:
    flask codegen-drift --solution-id 3259
    flask codegen-drift --solution-id 3259 --module work_orders
    flask codegen-drift --solution-id 3259 --json
"""
import hashlib
import json

import click
from flask.cli import with_appcontext

from app import db


@click.command("codegen-drift")
@click.option("--solution-id", required=True, type=int, help="Solution ID to check for drift.")
@click.option("--module", default=None, help="Filter to files matching this module name.")
@click.option("--json-output", "json_out", is_flag=True, help="Output machine-readable JSON.")
@with_appcontext
def codegen_drift_command(solution_id, module, json_out):
    """Detect drift between generated code and stored file manifests."""
    from app.modules.codegen.models import CodegenGeneration, CodegenGenerationHistory

    gen = CodegenGeneration.query.filter_by(solution_id=solution_id).first()
    if not gen:
        click.echo(f"No codegen generation found for solution {solution_id}.")
        raise SystemExit(1)

    # Get current generated files
    current_files = gen.generated_files or {}
    if not current_files:
        click.echo(f"No generated files stored for solution {solution_id}.")
        raise SystemExit(1)

    # Get stored manifest from config or latest history entry
    manifest = {}
    if gen.config and gen.config.get("file_manifest"):
        manifest = {m["path"]: m["hash"] for m in gen.config["file_manifest"]}
    else:
        # Fall back to latest history entry
        history = (
            CodegenGenerationHistory.query
            .filter_by(codegen_generation_id=gen.id)
            .order_by(CodegenGenerationHistory.generated_at.desc())
            .first()
        )
        if history and history.file_manifest:
            manifest = {m["path"]: m["hash"] for m in history.file_manifest}

    if not manifest:
        click.echo(f"No file manifest found for solution {solution_id}. Generate code first.")
        raise SystemExit(1)

    # Compute current hashes
    current_hashes = {}
    for path, content in current_files.items():
        if module and module not in path:
            continue
        current_hashes[path] = hashlib.sha256(content.encode()).hexdigest()[:12]

    # Filter manifest if module specified
    if module:
        manifest = {p: h for p, h in manifest.items() if module in p}

    # Compare
    manifest_paths = set(manifest.keys())
    current_paths = set(current_hashes.keys())

    added = sorted(current_paths - manifest_paths)
    deleted = sorted(manifest_paths - current_paths)
    modified = []
    unchanged = []

    for path in sorted(manifest_paths & current_paths):
        if current_hashes[path] != manifest[path]:
            modified.append(path)
        else:
            unchanged.append(path)

    has_drift = bool(added or deleted or modified)

    if json_out:
        result = {
            "solution_id": solution_id,
            "status": "drifted" if has_drift else "clean",
            "module_filter": module,
            "added": added,
            "modified": modified,
            "deleted": deleted,
            "unchanged_count": len(unchanged),
            "total_files": len(current_paths | manifest_paths),
        }
        click.echo(json.dumps(result, indent=2))
    else:
        if not has_drift:
            click.echo(f"Solution {solution_id}: CLEAN — {len(unchanged)} files match the manifest.")
            return

        click.echo(f"Solution {solution_id}: DRIFT DETECTED")
        click.echo(f"  Total files: {len(current_paths | manifest_paths)}")
        click.echo(f"  Unchanged:   {len(unchanged)}")

        if added:
            click.echo(f"\n  Added ({len(added)}):")
            for p in added:
                click.echo(f"    + {p}")

        if modified:
            click.echo(f"\n  Modified ({len(modified)}):")
            for p in modified:
                click.echo(f"    ~ {p}")

        if deleted:
            click.echo(f"\n  Deleted ({len(deleted)}):")
            for p in deleted:
                click.echo(f"    - {p}")

        click.echo(
            f"\n  WARNING: Re-generating will overwrite {len(modified)} modified file(s) "
            f"and remove {len(deleted)} deleted file(s)."
        )


def register_codegen_drift_commands(app):
    app.cli.add_command(codegen_drift_command)
