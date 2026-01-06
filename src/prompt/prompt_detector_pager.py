"""
Pager Detection
Detects and handles pager output (less, more, systemctl)
"""

import re
import logging
from typing import Tuple

logger = logging.getLogger(__name__)


class PagerDetector:
    """Detects pager output in command results"""

    def detect_pager_old(self, buffer) -> Tuple[bool, str]:
        """
        Check if output contains pager indicators

        CRITICAL: Patterns designed to NOT match:
        - Shell prompts (user@host:~$)
        - Password prompts ([sudo] password:)

        Returns:
            (detected, pager_type) tuple
        """
        # Very specific pager patterns that WON'T match prompts/passwords
        pager_patterns = [
            # Systemctl/nmcli style: "lines 1-29" or "lines 1-29/50"
            (r'lines\s+\d+-\d+', 'systemctl_pager'),

            # Less at end: "(END)" with optional whitespace
            (r'\(END\)\s*$', 'less_end'),

            # Traditional more: "--More--" often followed by percentage
            (r'--More--', 'more_pager'),

            # Less prompt: ONLY if it's literally just ":" and whitespace
            # NOT "password:" or "path:"
            (r'^:\s*$', 'less_prompt'),  # Must be START of line, ONLY colon
        ]

        # Check current_output (partial line)
        if hasattr(buffer, 'buffer') and hasattr(buffer.buffer, 'current_output'):
            current = buffer.buffer.current_output.strip()  # Strip for cleaner matching

            # SAFETY: Skip if it looks like a password prompt
            if 'password' in current.lower():
                return False, "password_prompt_excluded"

            # SAFETY: Skip if it looks like a shell prompt (has @ symbol)
            if '@' in current:
                return False, "shell_prompt_excluded"

            for pattern, pager_type in pager_patterns:
                if re.search(pattern, current, re.IGNORECASE):
                    logger.info(f"PAGER DETECTED in partial line: {pager_type} - '{current}'")
                    return True, pager_type

        # Check last completed line
        if hasattr(buffer, 'buffer') and hasattr(buffer.buffer, 'lines'):
            lines_list = list(buffer.buffer.lines)
            if lines_list:
                last_line = lines_list[-1]
                line_text = last_line.text if hasattr(last_line, 'text') else str(last_line)
                line_stripped = line_text.strip()

                # SAFETY: Skip if it looks like a password prompt
                if 'password' in line_stripped.lower():
                    return False, "password_prompt_excluded"

                # SAFETY: Skip if it looks like a shell prompt
                if '@' in line_stripped:
                    return False, "shell_prompt_excluded"

                for pattern, pager_type in pager_patterns:
                    if re.search(pattern, line_stripped, re.IGNORECASE):
                        logger.info(f"PAGER DETECTED in last line: {pager_type} - '{line_stripped}'")
                        return True, pager_type

        return False, "none"

    def detect_pager_old1(self, buffer) -> Tuple[bool, str, str]:
        """
        Check if output contains pager indicators

        Returns:
            (detected, pager_type, action) tuple
            - detected: True if pager found
            - pager_type: Type of pager
            - action: "continue" (send Space), "quit" (send q), "none"
        """
        pager_patterns = [
            # Pattern, pager_type, action
            (r'lines\s+\d+-\d+', 'systemctl_pager', 'continue'),  # Still more lines
            (r'\(END\)\s*$', 'less_end', 'quit'),                 # At end, quit
            (r'--More--', 'more_pager', 'continue'),              # More to show
            (r'^:\s*$', 'less_prompt', 'continue'),               # Less waiting for input
        ]

        # Check current_output (partial line)
        if hasattr(buffer, 'buffer') and hasattr(buffer.buffer, 'current_output'):
            current = buffer.buffer.current_output.strip()

            # SAFETY: Skip if password prompt
            if 'password' in current.lower():
                return False, "password_prompt_excluded", "none"

            # SAFETY: Skip if shell prompt
            if '@' in current:
                return False, "shell_prompt_excluded", "none"

            for pattern, pager_type, action in pager_patterns:
                if re.search(pattern, current, re.IGNORECASE):
                    logger.info(f"PAGER DETECTED in partial line: {pager_type} - action={action} - '{current}'")
                    return True, pager_type, action

        # Check last completed line
        if hasattr(buffer, 'buffer') and hasattr(buffer.buffer, 'lines'):
            lines_list = list(buffer.buffer.lines)
            if lines_list:
                last_line = lines_list[-1]
                line_text = last_line.text if hasattr(last_line, 'text') else str(last_line)
                line_stripped = line_text.strip()

                # SAFETY: Skip if password prompt
                if 'password' in line_stripped.lower():
                    return False, "password_prompt_excluded", "none"

                # SAFETY: Skip if shell prompt
                if '@' in line_stripped:
                    return False, "shell_prompt_excluded", "none"

                for pattern, pager_type, action in pager_patterns:
                    if re.search(pattern, line_stripped, re.IGNORECASE):
                        logger.info(f"PAGER DETECTED in last line: {pager_type} - action={action} - '{line_stripped}'")
                        return True, pager_type, action

        return False, "none", "none"


    def detect_pager(self, buffer) -> Tuple[bool, str, str]:
        """
        Check if output contains pager indicators

        Returns:
            (detected, pager_type, action) tuple
            - action: "continue" (send Space), "quit" (send q), "none"
        """
        # Check current_output (partial line)
        if hasattr(buffer, 'buffer') and hasattr(buffer.buffer, 'current_output'):
            current = buffer.buffer.current_output.strip()

            # SAFETY: Skip if password prompt
            if 'password' in current.lower():
                return False, "password_prompt_excluded", "none"

            # SAFETY: Skip if shell prompt
            if '@' in current:
                return False, "shell_prompt_excluded", "none"

            # PRIORITY 1: Check for (END) FIRST - even if combined with lines X-Y
            if re.search(r'\(END\)', current):
                logger.info(f"PAGER at END in partial line: '{current}'")
                return True, 'less_end', 'quit'

            # PRIORITY 2: Check for continuation patterns
            if re.search(r'lines\s+\d+-\d+', current, re.IGNORECASE):
                logger.info(f"PAGER CONTINUE in partial line: '{current}'")
                return True, 'systemctl_pager', 'continue'

            if re.search(r'--More--', current):
                logger.info(f"PAGER CONTINUE (more) in partial line: '{current}'")
                return True, 'more_pager', 'continue'

            if re.search(r'^:\s*$', current):
                logger.info(f"PAGER CONTINUE (less prompt) in partial line: '{current}'")
                return True, 'less_prompt', 'continue'

        # Check last completed line
        if hasattr(buffer, 'buffer') and hasattr(buffer.buffer, 'lines'):
            lines_list = list(buffer.buffer.lines)
            if lines_list:
                last_line = lines_list[-1]
                line_text = last_line.text if hasattr(last_line, 'text') else str(last_line)
                line_stripped = line_text.strip()

                # SAFETY: Skip if password prompt
                if 'password' in line_stripped.lower():
                    return False, "password_prompt_excluded", "none"

                # SAFETY: Skip if shell prompt
                if '@' in line_stripped:
                    return False, "shell_prompt_excluded", "none"

                # PRIORITY 1: Check for (END) FIRST
                if re.search(r'\(END\)', line_stripped):
                    logger.info(f"PAGER at END in last line: '{line_stripped}'")
                    return True, 'less_end', 'quit'

                # PRIORITY 2: Check for continuation patterns
                if re.search(r'lines\s+\d+-\d+', line_stripped, re.IGNORECASE):
                    logger.info(f"PAGER CONTINUE in last line: '{line_stripped}'")
                    return True, 'systemctl_pager', 'continue'

                if re.search(r'--More--', line_stripped):
                    logger.info(f"PAGER CONTINUE (more) in last line: '{line_stripped}'")
                    return True, 'more_pager', 'continue'

                if re.search(r'^:\s*$', line_stripped):
                    logger.info(f"PAGER CONTINUE (less prompt) in last line: '{line_stripped}'")
                    return True, 'less_prompt', 'continue'

        return False, "none", "none"
