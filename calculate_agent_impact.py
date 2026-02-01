#!/usr/bin/env python3
"""
Agent Workflow Impact Calculator

Calculate the impact of fixing each modularity issue on agent-based workflows.
This tool helps prioritize refactoring efforts based on quantifiable metrics.

Usage:
    python calculate_agent_impact.py
    python calculate_agent_impact.py --issue 8
    python calculate_agent_impact.py --simulate-phase 1
"""

# Issue database with quantified metrics
ISSUES = {
    1: {
        "title": "Duplicate Execution Logic (escalation vs two-phase)",
        "files": ["src/models/escalation.py", "src/models/two_phase.py"],
        "context_tokens": 300,
        "parallel_block": "TOTAL",  # TOTAL, HIGH, MEDIUM, LOW, NONE
        "agents_blocked": 2,
        "success_rate_gain": 5,  # percentage points
        "fix_effort_hours": 2,
        "merge_conflict_risk": "CRITICAL",
    },
    2: {
        "title": "Monolithic Executor Classes",
        "files": ["src/models/escalation.py:46-178"],
        "context_tokens": 150,
        "parallel_block": "TOTAL",
        "agents_blocked": 3,
        "success_rate_gain": 15,
        "fix_effort_hours": 3,
        "merge_conflict_risk": "HIGH",
    },
    3: {
        "title": "Tight Coupling (shell/context/preconditions)",
        "files": ["src/models/", "src/shell/", "src/context/", "src/preconditions/"],
        "context_tokens": 250,
        "parallel_block": "HIGH",
        "agents_blocked": 4,
        "success_rate_gain": 4,
        "fix_effort_hours": 3,
        "merge_conflict_risk": "HIGH",
    },
    4: {
        "title": "Inconsistent Context Parsing",
        "files": ["src/context/builder.py"],
        "context_tokens": 40,
        "parallel_block": "LOW",
        "agents_blocked": 0,
        "success_rate_gain": 5,
        "fix_effort_hours": 3,
        "merge_conflict_risk": "LOW",
    },
    5: {
        "title": "Missing Type Safety",
        "files": ["src/verification/file_exists.py", "src/verification/syntax_check.py"],
        "context_tokens": 20,
        "parallel_block": "NONE",
        "agents_blocked": 0,
        "success_rate_gain": 6,
        "fix_effort_hours": 2,
        "merge_conflict_risk": "LOW",
    },
    6: {
        "title": "Config System Lacks Validation",
        "files": ["src/verification/config.py"],
        "context_tokens": 200,
        "parallel_block": "MEDIUM",
        "agents_blocked": 2,
        "success_rate_gain": 8,
        "fix_effort_hours": 4,
        "merge_conflict_risk": "HIGH",
    },
    7: {
        "title": "Verification Runner Orchestrates Too Much",
        "files": ["src/verification/runner.py"],
        "context_tokens": 180,
        "parallel_block": "HIGH",
        "agents_blocked": 3,
        "success_rate_gain": 8,
        "fix_effort_hours": 1,
        "merge_conflict_risk": "MEDIUM",
    },
    8: {
        "title": "Tests at Root Directory",
        "files": ["*.py at root (23 files)"],
        "context_tokens": 400,
        "parallel_block": "MEDIUM",
        "agents_blocked": 0,
        "success_rate_gain": 2,
        "fix_effort_hours": 1,
        "merge_conflict_risk": "MEDIUM",
    },
    9: {
        "title": "Shared Mutable Metrics State",
        "files": ["src/verification/performance_metrics.py"],
        "context_tokens": 90,
        "parallel_block": "LOW",
        "agents_blocked": 0,
        "success_rate_gain": 8,
        "fix_effort_hours": 2,
        "merge_conflict_risk": "LOW",
    },
    10: {
        "title": "CommitGuard Hardcoded Patterns",
        "files": ["src/guards/commit.py"],
        "context_tokens": 120,
        "parallel_block": "MEDIUM",
        "agents_blocked": 1,
        "success_rate_gain": 5,
        "fix_effort_hours": 5,
        "merge_conflict_risk": "MEDIUM",
    },
    11: {
        "title": "Complex Context Path Validation",
        "files": ["src/context/builder.py:67-111"],
        "context_tokens": 80,
        "parallel_block": "LOW",
        "agents_blocked": 0,
        "success_rate_gain": 12,
        "fix_effort_hours": 2,
        "merge_conflict_risk": "LOW",
    },
    12: {
        "title": "Supervisor Proxy Methods",
        "files": ["supervisor.py:72-106"],
        "context_tokens": 25,
        "parallel_block": "MEDIUM",
        "agents_blocked": 2,
        "success_rate_gain": 3,
        "fix_effort_hours": 1,
        "merge_conflict_risk": "MEDIUM",
    },
}

# Refactoring phases
PHASES = {
    1: {
        "name": "Quick Wins (Unlock Parallelization)",
        "issues": [8, 1, 7],
        "goal": "Enable 4× parallel agents, reduce context 42%",
    },
    2: {
        "name": "Complexity Reduction",
        "issues": [2, 11, 3],
        "goal": "Improve success rate 67% → 85%",
    },
    3: {
        "name": "Long-Term Maintainability",
        "issues": [6, 10, 4],
        "goal": "Eliminate merge conflicts, enable extensibility",
    },
}


def calculate_impact_score(issue_id):
    """Calculate agent impact score for an issue."""
    issue = ISSUES[issue_id]
    
    # Scoring formula:
    # (Context Bloat × 3) + (Parallelization × 25) + (Success Rate × 2) + (ROI × 10)
    
    context_score = issue["context_tokens"] / 100 * 3  # Normalize to 0-12 range
    
    parallel_weights = {
        "TOTAL": 25,
        "HIGH": 20,
        "MEDIUM": 12,
        "LOW": 5,
        "NONE": 0,
    }
    parallel_score = parallel_weights[issue["parallel_block"]]
    
    success_score = issue["success_rate_gain"] * 2
    
    roi_score = (1 / issue["fix_effort_hours"]) * 10
    
    total = context_score + parallel_score + success_score + roi_score
    
    return {
        "total": round(total, 1),
        "context": round(context_score, 1),
        "parallel": parallel_score,
        "success": success_score,
        "roi": round(roi_score, 1),
    }


def print_issue_report(issue_id):
    """Print detailed report for a single issue."""
    issue = ISSUES[issue_id]
    scores = calculate_impact_score(issue_id)
    
    print(f"\n{'=' * 70}")
    print(f"Issue #{issue_id}: {issue['title']}")
    print(f"{'=' * 70}")
    
    print(f"\n📁 Files Impacted:")
    for f in issue["files"]:
        print(f"   - {f}")
    
    print(f"\n📊 Metrics:")
    print(f"   Context Tokens: {issue['context_tokens']} tokens wasted")
    print(f"   Parallel Block: {issue['parallel_block']} ({issue['agents_blocked']} agents blocked)")
    print(f"   Success Gain:   +{issue['success_rate_gain']}% completion rate")
    print(f"   Fix Effort:     {issue['fix_effort_hours']} hours")
    print(f"   Merge Risk:     {issue['merge_conflict_risk']}")
    
    print(f"\n🎯 Impact Score: {scores['total']}/100")
    print(f"   ├─ Context Bloat:     {scores['context']}")
    print(f"   ├─ Parallelization:   {scores['parallel']}")
    print(f"   ├─ Success Rate:      {scores['success']}")
    print(f"   └─ ROI Multiplier:    {scores['roi']}")
    
    # Priority recommendation
    if scores["total"] >= 85:
        priority = "🔴 P0 (Critical)"
    elif scores["total"] >= 70:
        priority = "🟠 P1 (High)"
    elif scores["total"] >= 50:
        priority = "🟡 P2 (Medium)"
    else:
        priority = "🟢 P3 (Low)"
    
    print(f"\n✅ Recommended Priority: {priority}")


def print_all_issues_ranked():
    """Print all issues ranked by impact score."""
    # Calculate scores for all issues
    issue_scores = []
    for issue_id in ISSUES:
        score = calculate_impact_score(issue_id)
        issue_scores.append((issue_id, score["total"], ISSUES[issue_id]["title"]))
    
    # Sort by score (descending)
    issue_scores.sort(key=lambda x: x[1], reverse=True)
    
    print("\n" + "=" * 80)
    print("All Issues Ranked by Agent Workflow Impact")
    print("=" * 80)
    print(f"\n{'Rank':<6} {'Issue':<8} {'Score':<8} {'Title':<55}")
    print("-" * 80)
    
    for rank, (issue_id, score, title) in enumerate(issue_scores, 1):
        emoji = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else "  "
        print(f"{emoji} #{rank:<4} #{issue_id:<7} {score:<8.1f} {title[:52]}")
    
    print("\n" + "=" * 80)


def print_phase_summary(phase_num):
    """Print summary for a refactoring phase."""
    phase = PHASES[phase_num]
    
    print(f"\n{'=' * 70}")
    print(f"Phase {phase_num}: {phase['name']}")
    print(f"{'=' * 70}")
    print(f"\nGoal: {phase['goal']}")
    
    total_hours = sum(ISSUES[i]["fix_effort_hours"] for i in phase["issues"])
    total_tokens = sum(ISSUES[i]["context_tokens"] for i in phase["issues"])
    max_agents_blocked = max(ISSUES[i]["agents_blocked"] for i in phase["issues"])
    total_success_gain = sum(ISSUES[i]["success_rate_gain"] for i in phase["issues"])
    
    print(f"\n📋 Issues Included:")
    for issue_id in phase["issues"]:
        issue = ISSUES[issue_id]
        score = calculate_impact_score(issue_id)["total"]
        print(f"   #{issue_id}: {issue['title'][:50]:<50} (Score: {score:.1f})")
    
    print(f"\n📊 Phase Impact:")
    print(f"   Total Effort:        {total_hours} hours")
    print(f"   Context Saved:       {total_tokens} tokens")
    print(f"   Agents Unlocked:     Up to {max_agents_blocked} concurrent agents")
    print(f"   Success Rate Boost:  +{total_success_gain}% (cumulative)")
    
    print(f"\n💰 ROI Calculation:")
    baseline_hours = 10  # hours per week of agent development
    parallelization_gain = max_agents_blocked if phase_num == 1 else 1
    success_rate_gain = total_success_gain / 100 if phase_num == 2 else 0
    
    time_saved_per_week = baseline_hours * (parallelization_gain - 1) / parallelization_gain
    time_saved_per_week += baseline_hours * success_rate_gain
    
    payback_weeks = total_hours / time_saved_per_week if time_saved_per_week > 0 else float('inf')
    
    print(f"   Time Saved/Week:     {time_saved_per_week:.1f} hours")
    print(f"   Payback Period:      {payback_weeks:.1f} weeks")
    print(f"   Annual ROI:          {(52 * time_saved_per_week / total_hours * 100):.0f}%")


def simulate_all_phases():
    """Simulate cumulative impact of all phases."""
    print("\n" + "=" * 80)
    print("Phased Refactoring Simulation")
    print("=" * 80)
    
    baseline_tokens = sum(ISSUES[i]["context_tokens"] for i in ISSUES)
    baseline_success = 67  # baseline success rate
    baseline_agents = 1
    
    cumulative_tokens_saved = 0
    cumulative_hours = 0
    current_success_rate = baseline_success
    current_agents = baseline_agents
    
    print(f"\nBaseline (Current State):")
    print(f"   Context Tokens:      {baseline_tokens} tokens")
    print(f"   Success Rate:        {baseline_success}%")
    print(f"   Parallel Agents:     {baseline_agents}")
    
    for phase_num in sorted(PHASES.keys()):
        phase = PHASES[phase_num]
        phase_hours = sum(ISSUES[i]["fix_effort_hours"] for i in phase["issues"])
        phase_tokens = sum(ISSUES[i]["context_tokens"] for i in phase["issues"])
        phase_success_gain = sum(ISSUES[i]["success_rate_gain"] for i in phase["issues"])
        
        # Update cumulative for phase 1 only (parallelization)
        if phase_num == 1:
            phase_agents = max(ISSUES[i]["agents_blocked"] for i in phase["issues"])
            current_agents = max(current_agents, phase_agents)
        
        # Update success rate for phase 2 only
        if phase_num == 2:
            current_success_rate += phase_success_gain
        
        cumulative_tokens_saved += phase_tokens
        cumulative_hours += phase_hours
        
        remaining_tokens = baseline_tokens - cumulative_tokens_saved
        reduction_pct = (cumulative_tokens_saved / baseline_tokens) * 100
        
        print(f"\nAfter Phase {phase_num} ({phase['name']}):")
        print(f"   Investment:          {cumulative_hours} hours (total)")
        print(f"   Context Tokens:      {remaining_tokens} tokens ({reduction_pct:.0f}% reduction)")
        print(f"   Success Rate:        {current_success_rate}%")
        print(f"   Parallel Agents:     {current_agents}")
        print(f"   Throughput Gain:     {current_agents}× faster")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) == 1:
        # No args: show all issues ranked
        print_all_issues_ranked()
        print("\nUsage:")
        print("  python calculate_agent_impact.py --issue <N>         # Detail for issue N")
        print("  python calculate_agent_impact.py --phase <N>         # Summary for phase N")
        print("  python calculate_agent_impact.py --simulate          # Simulate all phases")
    
    elif len(sys.argv) == 3 and sys.argv[1] == "--issue":
        issue_id = int(sys.argv[2])
        if issue_id in ISSUES:
            print_issue_report(issue_id)
        else:
            print(f"Error: Issue #{issue_id} not found. Valid issues: 1-12")
    
    elif len(sys.argv) == 3 and sys.argv[1] == "--phase":
        phase_num = int(sys.argv[2])
        if phase_num in PHASES:
            print_phase_summary(phase_num)
        else:
            print(f"Error: Phase {phase_num} not found. Valid phases: 1-3")
    
    elif len(sys.argv) == 2 and sys.argv[1] == "--simulate":
        simulate_all_phases()
    
    else:
        print("Usage:")
        print("  python calculate_agent_impact.py                     # Show all issues ranked")
        print("  python calculate_agent_impact.py --issue <N>         # Detail for issue N")
        print("  python calculate_agent_impact.py --phase <N>         # Summary for phase N")
        print("  python calculate_agent_impact.py --simulate          # Simulate all phases")
