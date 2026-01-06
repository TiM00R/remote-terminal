"""
Prompt Detection Module
Intelligent detection of command completion by finding shell prompts in output
Handles edge cases like prompts in output, prompt changes, background commands
"""

import logging
from typing import Optional, Tuple, List

logger = logging.getLogger(__name__)

from .prompt_detector_patterns import PromptPattern, PromptChangingCommand, PromptPatternManager
from .prompt_detector_pager import PagerDetector
from .prompt_detector_checks import PromptChecker


class PromptDetector:
    """
    Detects command completion by finding shell prompt in output

    Features:
    - Pattern matching with variable substitution
    - Context analysis (clean vs suspicious prompts)
    - Active verification (send Enter to confirm)
    - Prompt-changing command detection
    - Background command detection
    """

    def __init__(self, config: dict, ssh_manager=None):
        """
        Initialize prompt detector

        Args:
            config: Configuration dictionary with prompt_detection section
            ssh_manager: SSH manager for active verification (optional)
        """
        self.config = config
        self.ssh_manager = ssh_manager

        # Initialize components
        self._pattern_manager = PromptPatternManager(config)
        self._pager_detector = PagerDetector()
        self._checker = PromptChecker(config, ssh_manager, self._pattern_manager, self._pager_detector)

        self.user = None
        self.host = None

    def set_credentials(self, user: str, host: str):
        """Set user and host for pattern substitution"""
        self.user = user
        self.host = host
        self._pattern_manager.set_credentials(user, host)

    def get_prompt_patterns(self) -> List[str]:
        """
        Get list of prompt patterns with substituted variables

        Returns:
            List of regex pattern strings
        """
        return self._pattern_manager.get_prompt_patterns()

    def detect_prompt_in_line(self, line: str, prompt_pattern: str) -> Tuple[bool, str]:
        """
        Detect if line contains prompt pattern

        Args:
            line: Line to check
            prompt_pattern: Regex pattern to match

        Returns:
            (detected, reason) tuple
            - detected: True if prompt found, "verify" if suspicious, False otherwise
            - reason: Description of detection result
        """
        return self._pattern_manager.detect_prompt_in_line(line, prompt_pattern)

    async def verify_prompt(self, buffer, prompt_pattern: str) -> Tuple[bool, str]:
        """
        Actively verify suspicious prompt by sending Enter

        Args:
            buffer: Output buffer to check
            prompt_pattern: Pattern to look for

        Returns:
            (verified, reason) tuple
        """
        return await self._checker.verify_prompt(buffer, prompt_pattern)

    async def check_completion(self, buffer, prompt_pattern: str) -> Tuple[bool, str]:
        """
        Check completion with clear priority order:
        1. Password prompts (HIGHEST priority - handled by is_sudo_prompt)
        2. Pager detection (quit if found)
        3. Normal prompt detection
        CRITICAL FIX: Only checks lines AFTER command_start_line to avoid
        detecting the old prompt that was in the buffer before command started.

        Args:
            buffer: FilteredBuffer to check
            prompt_pattern: Pattern to look for

        Returns:
            (completed, reason) tuple
        """
        return await self._checker.check_completion(buffer, prompt_pattern)

    def detect_prompt_changing_command(self, command: str) -> Optional[str]:
        """
        Check if command changes the prompt

        Args:
            command: Command to check

        Returns:
            New prompt pattern if command changes prompt, None otherwise
        """
        return self._pattern_manager.detect_prompt_changing_command(command)

    def is_background_command(self, command: str) -> bool:
        """
        Check if command is backgrounded with &

        Args:
            command: Command to check

        Returns:
            True if command ends with &
        """
        return self._pattern_manager.is_background_command(command)

    def detect_pager_old(self, buffer) -> Tuple[bool, str]:
        """
        Check if output contains pager indicators

        CRITICAL: Patterns designed to NOT match:
        - Shell prompts (user@host:~$)
        - Password prompts ([sudo] password:)

        Returns:
            (detected, pager_type) tuple
        """
        return self._pager_detector.detect_pager_old(buffer)

    def detect_pager_old1(self, buffer) -> Tuple[bool, str, str]:
        """
        Check if output contains pager indicators

        Returns:
            (detected, pager_type, action) tuple
            - detected: True if pager found
            - pager_type: Type of pager
            - action: "continue" (send Space), "quit" (send q), "none"
        """
        return self._pager_detector.detect_pager_old1(buffer)


    def detect_pager(self, buffer) -> Tuple[bool, str, str]:
        """
        Check if output contains pager indicators

        Returns:
            (detected, pager_type, action) tuple
            - action: "continue" (send Space), "quit" (send q), "none"
        """
        return self._pager_detector.detect_pager(buffer)


    def get_current_prompt(self) -> str:
        """
        Get the most likely current prompt pattern

        Returns:
            Regex pattern for current prompt
        """
        return self._pattern_manager.get_current_prompt()

    def is_sudo_prompt(self, buffer) -> bool:
        """
        Check if current output contains sudo password prompt

        Args:
            buffer: FilteredBuffer to check

        Returns:
            True if sudo prompt detected
        """
        return self._checker.is_sudo_prompt(buffer)
