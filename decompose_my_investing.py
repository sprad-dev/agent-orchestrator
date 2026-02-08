#!/usr/bin/env python3
"""Decompose my-investing beads into parallel-safe subtasks using the orchestrator's TaskDAG.

Reads open/in_progress task beads and generates SubtaskSpecs with file ownership
based on the project's hexagonal architecture (ports/adapters/graph).
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from src.decomposition.decomposer import TaskDecomposer, SubtaskSpec, DecompositionResult

# Base paths in my-investing
MI = "/home/wspradley/src/investing/my-investing"


def decompose_reflection_loops() -> list[SubtaskSpec]:
    """my-investing-5ix: FEAT-REFLECTION-LOOPS - Iterative Refinement.

    Description: Add conditional edges to LangGraph. Implement Scout refinement node.
    Update graph structure. Integration tests for reflection loops.
    """
    return [
        SubtaskSpec(
            id="5ix-conditional-edges",
            description="Add conditional edges to LangGraph workflow for reflection routing",
            file_ownership=[
                "src/graph/workflow.py",
            ],
            inputs=["src/graph/state.py", "src/graph/nodes/scout.py"],
            outputs=["src/graph/workflow.py"],
            dependencies=["5ix-scout-refinement", "5ix-state-management"],
            test_command="pytest tests/unit/graph/test_workflow.py -v",
        ),
        SubtaskSpec(
            id="5ix-scout-refinement",
            description="Implement Scout refinement node (refine_scout_thesis in LLM port)",
            file_ownership=[
                "src/graph/nodes/scout.py",
                "src/ports/llm_reasoning_port.py",
                "src/adapters/claude_llm_reasoning_adapter.py",
            ],
            inputs=["src/graph/state.py"],
            outputs=["src/graph/nodes/scout.py", "src/ports/llm_reasoning_port.py"],
            dependencies=["5ix-state-management"],
            test_command="pytest tests/unit/graph/test_scout_node.py tests/unit/graph/test_reflection_loops.py -v",
        ),
        SubtaskSpec(
            id="5ix-state-management",
            description="Update state management for reflection iteration tracking",
            file_ownership=[
                "src/graph/state.py",
                "src/graph/state_management.py",
            ],
            inputs=[],
            outputs=["src/graph/state.py", "src/graph/state_management.py"],
            dependencies=[],
            test_command="pytest tests/unit/graph/test_state_management.py tests/unit/graph/test_state_transitions.py -v",
        ),
        SubtaskSpec(
            id="5ix-integration-tests",
            description="Integration tests for full reflection loop workflow",
            file_ownership=[
                "tests/integration/test_reflection_loops.py",
            ],
            inputs=["src/graph/workflow.py"],
            outputs=["tests/integration/test_reflection_loops.py"],
            dependencies=["5ix-conditional-edges"],
            test_command="pytest tests/integration/test_reflection_loops.py -v",
        ),
    ]


def decompose_discovery_integration() -> list[SubtaskSpec]:
    """my-investing-izt: FEAT-DISCOVERY-INTEGRATION - Async Queue Processing.

    Description: Define DiscoveryPort interface. Implement queue-based adapter.
    Build batch analysis processor. Implement deduplication. Add queue monitoring CLI.
    """
    return [
        SubtaskSpec(
            id="izt-discovery-port",
            description="Define DiscoveryPort interface with queue contracts",
            file_ownership=[
                "src/ports/discovery_port.py",
            ],
            inputs=[],
            outputs=["src/ports/discovery_port.py"],
            dependencies=[],
            test_command="pytest tests/unit/ports/test_discovery_port.py -v",
        ),
        SubtaskSpec(
            id="izt-queue-adapter",
            description="Implement queue-based adapter for async discovery processing",
            file_ownership=[
                "src/adapters/queue_discovery_adapter.py",
            ],
            inputs=["src/ports/discovery_port.py"],
            outputs=["src/adapters/queue_discovery_adapter.py"],
            dependencies=["izt-discovery-port"],
            test_command="pytest tests/unit/adapters/test_queue_discovery_adapter.py -v",
        ),
        SubtaskSpec(
            id="izt-batch-processor",
            description="Build batch analysis processor that feeds queue items to evaluation workflow",
            file_ownership=[
                "src/graph/batch_processor.py",
            ],
            inputs=["src/ports/discovery_port.py", "src/graph/workflow.py"],
            outputs=["src/graph/batch_processor.py"],
            dependencies=["izt-discovery-port"],
            test_command="pytest tests/unit/graph/test_batch_processor.py -v",
        ),
        SubtaskSpec(
            id="izt-deduplication",
            description="Implement deduplication logic for discovery queue entries",
            file_ownership=[
                "src/adapters/deduplication.py",
            ],
            inputs=["src/ports/discovery_port.py"],
            outputs=["src/adapters/deduplication.py"],
            dependencies=["izt-discovery-port"],
            test_command="pytest tests/unit/adapters/test_deduplication.py -v",
        ),
        SubtaskSpec(
            id="izt-cli-monitoring",
            description="Add queue monitoring commands to CLI",
            file_ownership=[
                "src/cli_discovery.py",
            ],
            inputs=["src/adapters/queue_discovery_adapter.py"],
            outputs=["src/cli_discovery.py"],
            dependencies=["izt-queue-adapter"],
            test_command="pytest tests/unit/test_cli_discovery.py -v",
        ),
        SubtaskSpec(
            id="izt-integration",
            description="Integration tests for full discovery pipeline",
            file_ownership=[
                "tests/integration/test_discovery_integration.py",
            ],
            inputs=[
                "src/adapters/queue_discovery_adapter.py",
                "src/graph/batch_processor.py",
            ],
            outputs=["tests/integration/test_discovery_integration.py"],
            dependencies=["izt-queue-adapter", "izt-batch-processor", "izt-deduplication"],
            test_command="pytest tests/integration/test_discovery_integration.py -v",
        ),
    ]


def decompose_semantic_filter() -> list[SubtaskSpec]:
    """my-investing-4fo: FEAT-QUANTUM-SEMANTIC-FILTER - Hybrid Boolean + Semantic Search.

    Description: Research embedding models. Implement Boolean baseline search.
    Build semantic reranking. Create semantic anchors. Manually label validation set.
    Tune thresholds. Implement CLI.
    """
    return [
        SubtaskSpec(
            id="4fo-boolean-search",
            description="Implement Boolean baseline search for ticker/keyword filtering",
            file_ownership=[
                "src/discovery/boolean_search.py",
            ],
            inputs=[],
            outputs=["src/discovery/boolean_search.py"],
            dependencies=[],
            test_command="pytest tests/unit/discovery/test_boolean_search.py -v",
        ),
        SubtaskSpec(
            id="4fo-embedding-port",
            description="Define EmbeddingPort interface for semantic search",
            file_ownership=[
                "src/ports/embedding_port.py",
            ],
            inputs=[],
            outputs=["src/ports/embedding_port.py"],
            dependencies=[],
            test_command="pytest tests/unit/ports/test_embedding_port.py -v",
        ),
        SubtaskSpec(
            id="4fo-semantic-reranker",
            description="Build semantic reranking using embedding similarity",
            file_ownership=[
                "src/discovery/semantic_reranker.py",
                "src/adapters/embedding_adapter.py",
            ],
            inputs=["src/ports/embedding_port.py", "src/discovery/boolean_search.py"],
            outputs=["src/discovery/semantic_reranker.py"],
            dependencies=["4fo-boolean-search", "4fo-embedding-port"],
            test_command="pytest tests/unit/discovery/test_semantic_reranker.py -v",
        ),
        SubtaskSpec(
            id="4fo-semantic-anchors",
            description="Create semantic anchors (reference embeddings for known-good matches)",
            file_ownership=[
                "src/discovery/semantic_anchors.py",
            ],
            inputs=["src/ports/embedding_port.py"],
            outputs=["src/discovery/semantic_anchors.py"],
            dependencies=["4fo-embedding-port"],
            test_command="pytest tests/unit/discovery/test_semantic_anchors.py -v",
        ),
        SubtaskSpec(
            id="4fo-threshold-tuner",
            description="Threshold tuning and validation set evaluation",
            file_ownership=[
                "src/discovery/threshold_tuner.py",
                "tests/fixtures/validation_labels.json",
            ],
            inputs=["src/discovery/semantic_reranker.py"],
            outputs=["src/discovery/threshold_tuner.py"],
            dependencies=["4fo-semantic-reranker"],
            test_command="pytest tests/unit/discovery/test_threshold_tuner.py -v",
        ),
        SubtaskSpec(
            id="4fo-cli",
            description="CLI commands for semantic search",
            file_ownership=[
                "src/cli_search.py",
            ],
            inputs=["src/discovery/semantic_reranker.py"],
            outputs=["src/cli_search.py"],
            dependencies=["4fo-semantic-reranker"],
            test_command="pytest tests/unit/test_cli_search.py -v",
        ),
    ]


def decompose_real_time_alerts() -> list[SubtaskSpec]:
    """my-investing-nad: FEAT-REAL-TIME-ALERTS - Price & Valuation Triggers.

    Description: Implement background price monitoring. Build trigger rule engine.
    Implement AlertNotifier port with Email/Slack/SMS. Add alert history & deduplication.
    Create per-position config.
    """
    return [
        SubtaskSpec(
            id="nad-alert-port",
            description="Define AlertNotifierPort interface",
            file_ownership=[
                "src/ports/alert_notifier_port.py",
            ],
            inputs=[],
            outputs=["src/ports/alert_notifier_port.py"],
            dependencies=[],
            test_command="pytest tests/unit/ports/test_alert_notifier_port.py -v",
        ),
        SubtaskSpec(
            id="nad-price-monitor",
            description="Implement background price monitoring service",
            file_ownership=[
                "src/monitoring/price_monitor.py",
            ],
            inputs=["src/ports/fundamentals_port.py"],
            outputs=["src/monitoring/price_monitor.py"],
            dependencies=[],
            test_command="pytest tests/unit/monitoring/test_price_monitor.py -v",
        ),
        SubtaskSpec(
            id="nad-trigger-engine",
            description="Build trigger rule engine (price targets, valuation thresholds)",
            file_ownership=[
                "src/monitoring/trigger_engine.py",
                "src/monitoring/trigger_config.py",
            ],
            inputs=["src/monitoring/price_monitor.py"],
            outputs=["src/monitoring/trigger_engine.py"],
            dependencies=["nad-price-monitor"],
            test_command="pytest tests/unit/monitoring/test_trigger_engine.py -v",
        ),
        SubtaskSpec(
            id="nad-notifier-adapters",
            description="Implement Email/Slack/SMS notification adapters",
            file_ownership=[
                "src/adapters/email_notifier_adapter.py",
                "src/adapters/slack_notifier_adapter.py",
            ],
            inputs=["src/ports/alert_notifier_port.py"],
            outputs=["src/adapters/email_notifier_adapter.py", "src/adapters/slack_notifier_adapter.py"],
            dependencies=["nad-alert-port"],
            test_command="pytest tests/unit/adapters/test_notifier_adapters.py -v",
        ),
        SubtaskSpec(
            id="nad-alert-history",
            description="Alert history persistence and deduplication",
            file_ownership=[
                "src/adapters/sqlite_alert_history.py",
            ],
            inputs=["src/monitoring/trigger_engine.py"],
            outputs=["src/adapters/sqlite_alert_history.py"],
            dependencies=["nad-trigger-engine"],
            test_command="pytest tests/unit/adapters/test_sqlite_alert_history.py -v",
        ),
        SubtaskSpec(
            id="nad-integration",
            description="Integration tests for alert pipeline",
            file_ownership=[
                "tests/integration/test_alert_pipeline.py",
            ],
            inputs=[
                "src/monitoring/trigger_engine.py",
            ],
            outputs=["tests/integration/test_alert_pipeline.py"],
            dependencies=["nad-trigger-engine", "nad-notifier-adapters", "nad-alert-history"],
            test_command="pytest tests/integration/test_alert_pipeline.py -v",
        ),
    ]


def decompose_filing_diff() -> list[SubtaskSpec]:
    """my-investing-9mb: FEAT-FILING-DIFF-SURVEILLANCE - Semantic SEC Analysis.

    Description: Implement filing fetcher. Build document parser. Implement semantic diff
    using embeddings. Build risk factor clustering. Add sentiment analysis.
    Integrate with real-time alerts.
    """
    return [
        SubtaskSpec(
            id="9mb-filing-fetcher",
            description="Implement SEC filing fetcher (EDGAR API)",
            file_ownership=[
                "src/adapters/edgar_filing_adapter.py",
                "src/ports/filing_port.py",
            ],
            inputs=[],
            outputs=["src/ports/filing_port.py", "src/adapters/edgar_filing_adapter.py"],
            dependencies=[],
            test_command="pytest tests/unit/adapters/test_edgar_filing_adapter.py -v",
        ),
        SubtaskSpec(
            id="9mb-document-parser",
            description="Build SEC document parser (10-K, 10-Q sections)",
            file_ownership=[
                "src/surveillance/document_parser.py",
            ],
            inputs=["src/ports/filing_port.py"],
            outputs=["src/surveillance/document_parser.py"],
            dependencies=["9mb-filing-fetcher"],
            test_command="pytest tests/unit/surveillance/test_document_parser.py -v",
        ),
        SubtaskSpec(
            id="9mb-semantic-diff",
            description="Implement semantic diff using embeddings for filing comparison",
            file_ownership=[
                "src/surveillance/semantic_diff.py",
            ],
            inputs=["src/surveillance/document_parser.py", "src/ports/embedding_port.py"],
            outputs=["src/surveillance/semantic_diff.py"],
            dependencies=["9mb-document-parser"],
            test_command="pytest tests/unit/surveillance/test_semantic_diff.py -v",
        ),
        SubtaskSpec(
            id="9mb-risk-clustering",
            description="Build risk factor clustering from filing sections",
            file_ownership=[
                "src/surveillance/risk_clustering.py",
            ],
            inputs=["src/surveillance/document_parser.py"],
            outputs=["src/surveillance/risk_clustering.py"],
            dependencies=["9mb-document-parser"],
            test_command="pytest tests/unit/surveillance/test_risk_clustering.py -v",
        ),
        SubtaskSpec(
            id="9mb-sentiment-analysis",
            description="Add sentiment analysis for filing language changes",
            file_ownership=[
                "src/surveillance/sentiment_analysis.py",
            ],
            inputs=["src/surveillance/document_parser.py"],
            outputs=["src/surveillance/sentiment_analysis.py"],
            dependencies=["9mb-document-parser"],
            test_command="pytest tests/unit/surveillance/test_sentiment_analysis.py -v",
        ),
        SubtaskSpec(
            id="9mb-alert-integration",
            description="Integrate filing surveillance with real-time alert pipeline",
            file_ownership=[
                "src/surveillance/alert_bridge.py",
            ],
            inputs=[
                "src/surveillance/semantic_diff.py",
                "src/surveillance/risk_clustering.py",
                "src/monitoring/trigger_engine.py",
            ],
            outputs=["src/surveillance/alert_bridge.py"],
            dependencies=["9mb-semantic-diff", "9mb-risk-clustering", "9mb-sentiment-analysis"],
            test_command="pytest tests/unit/surveillance/test_alert_bridge.py -v",
        ),
    ]


def decompose_opportunity_feed() -> list[SubtaskSpec]:
    """my-investing-f8u: FEAT-QUANTUM-OPPORTUNITY-FEED - Scheduled Discovery.

    Description: Implement scheduled job runner. Create OpportunitiesDB.
    Build deduplication & evidence accumulation. Create feed API.
    Integrate with analysis queue.
    """
    return [
        SubtaskSpec(
            id="f8u-scheduler",
            description="Implement scheduled job runner for periodic discovery scans",
            file_ownership=[
                "src/discovery/scheduler.py",
            ],
            inputs=[],
            outputs=["src/discovery/scheduler.py"],
            dependencies=[],
            test_command="pytest tests/unit/discovery/test_scheduler.py -v",
        ),
        SubtaskSpec(
            id="f8u-opportunities-db",
            description="Create OpportunitiesDB schema and persistence",
            file_ownership=[
                "src/adapters/sqlite_opportunities_adapter.py",
                "src/ports/opportunities_port.py",
            ],
            inputs=[],
            outputs=["src/ports/opportunities_port.py", "src/adapters/sqlite_opportunities_adapter.py"],
            dependencies=[],
            test_command="pytest tests/unit/adapters/test_sqlite_opportunities_adapter.py -v",
        ),
        SubtaskSpec(
            id="f8u-evidence-accumulation",
            description="Build evidence accumulation and deduplication for opportunities",
            file_ownership=[
                "src/discovery/evidence_accumulator.py",
            ],
            inputs=["src/ports/opportunities_port.py"],
            outputs=["src/discovery/evidence_accumulator.py"],
            dependencies=["f8u-opportunities-db"],
            test_command="pytest tests/unit/discovery/test_evidence_accumulator.py -v",
        ),
        SubtaskSpec(
            id="f8u-feed-api",
            description="Create feed API for consuming discovered opportunities",
            file_ownership=[
                "src/discovery/feed_api.py",
            ],
            inputs=["src/discovery/evidence_accumulator.py"],
            outputs=["src/discovery/feed_api.py"],
            dependencies=["f8u-evidence-accumulation"],
            test_command="pytest tests/unit/discovery/test_feed_api.py -v",
        ),
        SubtaskSpec(
            id="f8u-analysis-queue",
            description="Integrate feed with analysis queue for automatic evaluation",
            file_ownership=[
                "src/discovery/analysis_bridge.py",
            ],
            inputs=["src/discovery/feed_api.py", "src/ports/discovery_port.py"],
            outputs=["src/discovery/analysis_bridge.py"],
            dependencies=["f8u-feed-api"],
            test_command="pytest tests/unit/discovery/test_analysis_bridge.py -v",
        ),
    ]


def print_result(name: str, bead_id: str, result: DecompositionResult):
    """Pretty-print a decomposition result."""
    print(f"\n{'='*70}")
    print(f"📋 {name}")
    print(f"   Bead: {bead_id}")
    print(f"   Parallel-safe: {'✅ YES' if result.is_parallel_safe else '❌ NO'}")
    print(f"   Subtasks: {len(result.execution_order)}")
    print(f"   Validation: {result.validation.summary}")
    
    if result.file_conflicts:
        print(f"\n   ⚠️  File conflicts:")
        for f, nodes in result.file_conflicts.items():
            print(f"      {f} → {', '.join(nodes)}")
    
    if not result.validation.passed:
        for rule, res in result.validation.rule_results.items():
            if not res.passed:
                print(f"\n   ❌ {rule}:")
                for v in res.violations:
                    print(f"      - {v}")
    
    print(f"\n   📊 Execution order:")
    for i, node in enumerate(result.execution_order, 1):
        deps_str = f" (after: {', '.join(node.dependencies)})" if node.dependencies else " (root - can start immediately)"
        print(f"      {i}. {node.id}: {node.description}{deps_str}")
        print(f"         Files: {', '.join(node.file_ownership)}")
    
    # Show parallelism opportunities
    roots = [n for n in result.execution_order if not n.dependencies]
    if len(roots) > 1:
        print(f"\n   🔀 Parallel roots ({len(roots)} tasks can run simultaneously):")
        for r in roots:
            print(f"      - {r.id}")


def print_bead_commands(bead_id: str, specs: list[SubtaskSpec]):
    """Print bd commands to create child beads."""
    print(f"\n   📝 Bead creation commands:")
    for spec in specs:
        child_id = f"{bead_id}.{spec.id.split('-', 1)[1]}"
        deps_arg = ""
        if spec.dependencies:
            parent_deps = [f"{bead_id}.{d.split('-', 1)[1]}" for d in spec.dependencies]
            deps_arg = f" --blocks {','.join(parent_deps)}"
        print(f"      bd add \"{spec.description}\" --parent {bead_id}{deps_arg}")


def main():
    decomposer = TaskDecomposer(journal_path="/dev/null")
    
    decompositions = [
        ("FEAT-REFLECTION-LOOPS", "my-investing-5ix", decompose_reflection_loops()),
        ("FEAT-DISCOVERY-INTEGRATION", "my-investing-izt", decompose_discovery_integration()),
        ("FEAT-QUANTUM-SEMANTIC-FILTER", "my-investing-4fo", decompose_semantic_filter()),
        ("FEAT-QUANTUM-OPPORTUNITY-FEED", "my-investing-f8u", decompose_opportunity_feed()),
        ("FEAT-REAL-TIME-ALERTS", "my-investing-nad", decompose_real_time_alerts()),
        ("FEAT-FILING-DIFF-SURVEILLANCE", "my-investing-9mb", decompose_filing_diff()),
    ]
    
    print("🔧 Task Decomposition Analysis for my-investing")
    print("=" * 70)
    
    all_passed = True
    for name, bead_id, specs in decompositions:
        try:
            result = decomposer.decompose(specs)
            print_result(name, bead_id, result)
            print_bead_commands(bead_id, specs)
            if not result.is_parallel_safe:
                all_passed = False
        except ValueError as e:
            print(f"\n❌ {name} ({bead_id}): DAG error - {e}")
            all_passed = False
    
    print(f"\n{'='*70}")
    print(f"Overall: {'✅ All decompositions are parallel-safe' if all_passed else '❌ Some decompositions have issues'}")
    
    # Summary stats
    total_subtasks = sum(len(specs) for _, _, specs in decompositions)
    total_roots = sum(
        len([s for s in specs if not s.dependencies])
        for _, _, specs in decompositions
    )
    print(f"Total subtasks: {total_subtasks}")
    print(f"Parallel roots: {total_roots} (can start immediately)")


if __name__ == "__main__":
    main()
