"""
Batch Script Helpers - Formatting and helper functions
Response formatting functions for batch execution results
"""


def _format_success_response(result: dict) -> str:
    """Format successful execution response for AI."""

    lines = [
        f"Batch script completed: {result['description']}",
        f"  Execution time: {result['execution_time_formatted']}",
        f"  Steps completed: {result['steps_completed']}",
    ]

    if result.get("all_complete"):
        lines.append("  Status: All diagnostics complete")

    if result.get("error_detected"):
        lines.append(f"  Errors detected: {result.get('error_summary', 'See output')}")

    # Add database tracking info if available
    if result.get("tracking", {}).get("database_saved"):
        tracking = result["tracking"]
        lines.append(f"  Database: batch_id={tracking.get('batch_execution_id')}, command_id={tracking.get('command_id')}")

    lines.extend([
        "",
        f"Log saved to: {result['local_log_file']}",
        ""
    ])

    # Include full output or preview based on output_mode
    if result.get('full_output'):
        # output_mode="full" - Include entire log content
        lines.extend([
            "Complete output:",
            "=" * 80,
            result['full_output'],
            "=" * 80
        ])
    else:
        # output_mode="summary" - Show preview only (token efficient)
        lines.extend([
            "Output preview (first 10 lines):",
            "---",
            result['output_preview']['first_lines'],
            "---",
            "",
            "Output preview (last 10 lines):",
            "---",
            result['output_preview']['last_lines'],
            "---"
        ])

    return '\n'.join(lines)


def _format_error_response(result: dict) -> str:
    """Format error response for AI."""

    lines = [
        f"Batch script failed: {result['description']}",
        f"  Status: {result['status']}",
        f"  Error: {result.get('error', 'Unknown error')}"
    ]

    if result.get('local_log_file'):
        lines.append(f"  Partial log may be at: {result['local_log_file']}")

    if result.get("tracking", {}).get("database_saved"):
        lines.append(f"  Batch execution recorded in database: {result['tracking'].get('batch_execution_id')}")

    return '\n'.join(lines)
