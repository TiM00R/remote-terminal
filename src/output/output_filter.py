"""
Smart Output Filter
Intelligently filters command output to minimize token usage
"""

import logging
from typing import Optional, Dict, List
from utils.utils import count_lines, is_error_output, detect_command_type

# Import from split modules
from .output_filter_decision import (
    should_send_output,
    filter_with_errors,
    truncate_output
)
from .output_filter_commands import (
    filter_installation,
    filter_file_listing,
    filter_file_viewing,
    filter_system_info,
    filter_network_info,
    filter_log_search
)

logger = logging.getLogger(__name__)


class SmartOutputFilter:
    """
    Filters command output intelligently based on command type and length
    """

    def __init__(self, thresholds: Optional[Dict[str, int]] = None,
                 truncation: Optional[Dict[str, int]] = None,
                 error_patterns: Optional[List[str]] = None,
                 auto_send_errors: bool = True):
        """
        Initialize Smart Output Filter

        Args:
            thresholds: Line thresholds for different command types
            truncation: Truncation settings (head/tail lines)
            error_patterns: Patterns to detect errors
            auto_send_errors: Auto send error output to Claude
        """
        self.thresholds = thresholds or {
            'system_info': 50,
            'network_info': 100,
            'file_listing': 50,
            'file_viewing': 100,
            'install': 100,
            'generic': 50
        }

        self.truncation = truncation or {
            'head_lines': 30,
            'tail_lines': 20
        }

        self.error_patterns = error_patterns or [
            'ERROR', 'FAILED', 'FATAL', 'Cannot',
            'Permission denied', 'No such file', 'command not found'
        ]

        self.auto_send_errors = auto_send_errors

    def should_send(self, command: str, output: str) -> bool:
        """
        Determine if output should be sent to Claude

        Args:
            command: Command that was executed
            output: Command output

        Returns:
            True if should send to Claude
        """
        return should_send_output(
            command, output, self.error_patterns,
            self.thresholds, self.auto_send_errors
        )

    def filter_output(self, command: str, output: str) -> str:
        """
        Filter output based on command type and length

        Args:
            command: Command that was executed
            output: Full command output

        Returns:
            Filtered/summarized output
        """
        if not output or not output.strip():
            return "[No output]"

        # Detect command type
        cmd_type = detect_command_type(command)
        line_count = count_lines(output)

        # Check if contains errors
        has_errors = is_error_output(output, self.error_patterns)

        # Get threshold for this command type
        threshold = self.thresholds.get(cmd_type, self.thresholds['generic'])

        logger.debug(f"Filtering: cmd_type={cmd_type}, lines={line_count}, "
                    f"threshold={threshold}, has_errors={has_errors}")

        # If has errors, always include error context
        if has_errors:
            return filter_with_errors(command, output, cmd_type, self.error_patterns)

        # If within threshold, send full output
        if line_count <= threshold:
            return output

        # Otherwise, apply smart filtering based on command type
        return self._apply_smart_filter(command, output, cmd_type, line_count)

    def _apply_smart_filter(self, command: str, output: str,
                           cmd_type: str, line_count: int) -> str:
        """
        Apply smart filtering based on command type

        Args:
            command: Command executed
            output: Full output
            cmd_type: Command type
            line_count: Number of lines

        Returns:
            Filtered output
        """
        if cmd_type == 'install':
            return filter_installation(command, output, line_count)

        elif cmd_type == 'file_listing':
            return filter_file_listing(command, output, line_count)

        elif cmd_type == 'file_viewing':
            return filter_file_viewing(
                command, output, line_count,
                self.truncation['head_lines'],
                self.truncation['tail_lines']
            )

        elif cmd_type == 'system_info':
            return filter_system_info(
                command, output, line_count,
                self.thresholds['system_info']
            )

        elif cmd_type == 'network':
            return filter_network_info(command, output, line_count)

        elif cmd_type == 'log_search':
            return filter_log_search(command, output, line_count)

        else:
            return truncate_output(
                output,
                self.truncation['head_lines'],
                self.truncation['tail_lines']
            )

    def get_summary(self, command: str, output: str) -> dict:
        """
        Get summary statistics about command output

        Args:
            command: Command executed
            output: Command output

        Returns:
            Dictionary with summary statistics
        """
        return {
            'command': command,
            'command_type': detect_command_type(command),
            'line_count': count_lines(output),
            'char_count': len(output),
            'has_errors': is_error_output(output, self.error_patterns),
            'should_send': self.should_send(command, output)
        }
