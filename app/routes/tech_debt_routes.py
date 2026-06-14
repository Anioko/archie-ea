"""
Technical Debt Dashboard Routes

Provides API endpoints for technical debt metrics and dashboard functionality.
"""

import json
from datetime import datetime
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request
from flask_login import login_required

from app.decorators import audit_log

tech_debt_bp = Blueprint("tech_debt", __name__, url_prefix="/tech-debt")


@tech_debt_bp.route("/metrics")
@login_required
def get_metrics():
    """Get current technical debt metrics."""
    try:
        # Try to load the latest report
        artifacts_dir = Path(__file__).parent.parent.parent / "artifacts"
        
        # Find the most recent report
        reports = list(artifacts_dir.glob("tech-debt-report-*.json"))
        if not reports:
            return jsonify({"error": "No technical debt reports found"}), 404
        
        latest_report = max(reports, key=lambda p: p.stat().st_mtime)
        
        with open(latest_report, 'r') as f:
            metrics = json.load(f)
        
        return jsonify(metrics)
        
    except Exception as e:
        return jsonify({"error": f"Failed to load metrics: {str(e)}"}), 500


@tech_debt_bp.route("/collect", methods=["POST"])
@login_required
@audit_log("tech_debt_collect")
def collect_metrics():
    """Trigger technical debt metrics collection."""
    try:
        # Import and run the collector
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "metrics"))
        
        from collect_tech_debt import TechnicalDebtCollector
        
        collector = TechnicalDebtCollector()
        metrics = collector.collect_all_metrics()
        
        # Save the report
        report_path = collector.save_report()
        
        return jsonify({
            "success": True,
            "message": "Technical debt metrics collected successfully",
            "report_path": report_path,
            "summary": metrics.get("summary", {})
        })
        
    except Exception as e:
        return jsonify({"error": f"Failed to collect metrics: {str(e)}"}), 500


@tech_debt_bp.route("/history")
@login_required
def get_history():
    """Get historical technical debt data."""
    try:
        artifacts_dir = Path(__file__).parent.parent.parent / "artifacts"
        
        # Find all reports
        reports = list(artifacts_dir.glob("tech-debt-report-*.json"))
        reports.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        
        history = []
        for report_path in reports[:12]:  # Last 12 months
            try:
                with open(report_path, 'r') as f:
                    data = json.load(f)
                
                # Extract summary data
                summary = data.get("summary", {})
                timestamp = data.get("timestamp", "")
                
                history.append({
                    "date": timestamp.split('T')[0] if timestamp else "",
                    "overall_score": summary.get("overall_score", 0),
                    "debt_level": summary.get("debt_level", "UNKNOWN"),
                    "total_issues": summary.get("total_issues", 0),
                    "security_issues": data.get("security", {}).get("total_issues", 0),
                    "test_coverage": data.get("test_coverage", {}).get("overall_coverage", 0),
                    "high_complexity_files": data.get("code_duplication", {}).get("high_complexity_count", 0)
                })
                
            except Exception as e:
                current_app.logger.warning(f"Error reading report {report_path}: {e}")
                continue
        
        return jsonify({"history": history})
        
    except Exception as e:
        return jsonify({"error": f"Failed to load history: {str(e)}"}), 500


@tech_debt_bp.route("/baseline")
@login_required
def get_baseline():
    """Get technical debt baseline for comparison."""
    try:
        # Look for baseline documentation
        baseline_file = Path(__file__).parent.parent.parent / "docs" / "governance" / "TECHNICAL_DEBT_BASELINE.md"
        
        if not baseline_file.exists():
            return jsonify({"error": "Baseline documentation not found"}), 404
        
        with open(baseline_file, 'r') as f:
            baseline_content = f.read()
        
        return jsonify({
            "baseline": baseline_content,
            "established": datetime.fromtimestamp(baseline_file.stat().st_mtime).isoformat()
        })
        
    except Exception as e:
        return jsonify({"error": f"Failed to load baseline: {str(e)}"}), 500


@tech_debt_bp.route("/export")
@login_required
def export_report():
    """Export technical debt report in various formats."""
    try:
        format_type = request.args.get("format", "json")
        
        # Load latest metrics
        artifacts_dir = Path(__file__).parent.parent.parent / "artifacts"
        reports = list(artifacts_dir.glob("tech-debt-report-*.json"))
        
        if not reports:
            return jsonify({"error": "No technical debt reports found"}), 404
        
        latest_report = max(reports, key=lambda p: p.stat().st_mtime)
        
        with open(latest_report, 'r') as f:
            metrics = json.load(f)
        
        if format_type == "json":
            return jsonify(metrics)
        
        elif format_type == "csv":
            import csv
            from io import StringIO
            
            output = StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow(["Metric", "Value", "Details"])
            
            # Write summary data
            summary = metrics.get("summary", {})
            writer.writerow(["Overall Score", summary.get("overall_score", ""), ""])
            writer.writerow(["Debt Level", summary.get("debt_level", ""), ""])
            writer.writerow(["Total Issues", summary.get("total_issues", ""), ""])
            
            # Write detailed metrics
            for category, data in metrics.items():
                if category in ["timestamp", "summary"]:
                    continue
                    
                if isinstance(data, dict) and "error" not in data:
                    if category == "security":
                        writer.writerow(["Security Issues", data.get("total_issues", ""), ""])
                        writer.writerow(["High Severity", data.get("high_severity", ""), ""])
                        writer.writerow(["Medium Severity", data.get("medium_severity", ""), ""])
                        writer.writerow(["Low Severity", data.get("low_severity", ""), ""])
                    elif category == "test_coverage":
                        writer.writerow(["Test Coverage", f"{data.get('overall_coverage', 0)}%", ""])
                        writer.writerow(["Files Analyzed", data.get("files_analyzed", ""), ""])
                    elif category == "code_duplication":
                        writer.writerow(["Average Complexity", data.get("average_complexity", ""), ""])
                        writer.writerow(["High Complexity Files", data.get("high_complexity_count", ""), ""])
            
            output.seek(0)
            return output.getvalue(), 200, {
                'Content-Type': 'text/csv',
                'Content-Disposition': f'attachment; filename=tech-debt-report-{datetime.now().strftime("%Y-%m-%d")}.csv'
            }
        
        else:
            return jsonify({"error": f"Unsupported format: {format_type}"}), 400
            
    except Exception as e:
        return jsonify({"error": f"Failed to export report: {str(e)}"}), 500


@tech_debt_bp.route("/trends")
@login_required
def get_trends():
    """Get technical debt trends over time."""
    try:
        # Load historical data
        artifacts_dir = Path(__file__).parent.parent.parent / "artifacts"
        reports = list(artifacts_dir.glob("tech-debt-report-*.json"))
        reports.sort(key=lambda p: p.stat().st_mtime)
        
        trends = {
            "dates": [],
            "scores": [],
            "security_issues": [],
            "test_coverage": [],
            "complexity": []
        }
        
        for report_path in reports[-6:]:  # Last 6 reports
            try:
                with open(report_path, 'r') as f:
                    data = json.load(f)
                
                timestamp = data.get("timestamp", "")
                date = timestamp.split('T')[0] if timestamp else ""
                
                trends["dates"].append(date)
                trends["scores"].append(data.get("summary", {}).get("overall_score", 0))
                trends["security_issues"].append(data.get("security", {}).get("total_issues", 0))
                trends["test_coverage"].append(data.get("test_coverage", {}).get("overall_coverage", 0))
                trends["complexity"].append(data.get("code_duplication", {}).get("average_complexity", 0))
                
            except Exception as e:
                current_app.logger.warning(f"Error reading report {report_path}: {e}")
                continue
        
        return jsonify(trends)
        
    except Exception as e:
        return jsonify({"error": f"Failed to load trends: {str(e)}"}), 500
