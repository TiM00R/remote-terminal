"""
Prompt Checking Logic
Command completion detection and verification
"""

import logging
from typing import Tuple

logger = logging.getLogger(__name__)


class PromptChecker:
    """Handles prompt detection and verification logic"""

    def __init__(self, config: dict, ssh_manager=None, pattern_manager=None, pager_detector=None):
        """
        Initialize prompt checker

        Args:
            config: Configuration dictionary
            ssh_manager: SSH manager for verification
            pattern_manager: PromptPatternManager instance
            pager_detector: PagerDetector instance
        """
        self.config = config
        self.ssh_manager = ssh_manager
        self.pattern_manager = pattern_manager
        self.pager_detector = pager_detector

        # Settings
        self.verification_enabled = config.get("prompt_detection", {}).get("verification_enabled", True)
        self.verification_delay = config.get("prompt_detection", {}).get("verification_delay", 0.3)

    async def verify_prompt(self, buffer, prompt_pattern: str) -> Tuple[bool, str]:
        """
        Actively verify suspicious prompt by sending Enter

        Args:
            buffer: Output buffer to check
            prompt_pattern: Pattern to look for

        Returns:
            (verified, reason) tuple
        """
        if not self.verification_enabled or not self.ssh_manager:
            return False, "verification_disabled"

        # Get current buffer state
        lines_before = len(buffer.buffer.lines)

        # Send Enter
        logger.info("Sending Enter to verify prompt")
        self.ssh_manager.send_input('\n')

        # Wait for response
        import asyncio
        await asyncio.sleep(self.verification_delay)

        # Check if new prompt appeared
        lines_after = len(buffer.buffer.lines)
        if lines_after > lines_before:
            # Check last few lines for prompt
            recent_lines = buffer.get_last_n(3)
            for line in recent_lines:
                detected, reason = self.pattern_manager.detect_prompt_in_line(line.text, prompt_pattern)
                if detected is True:
                    return True, "verified_by_enter"

        return False, "verification_failed"

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
        # DIAGNOSTIC: Log what we're checking
        logger.info(f"[PROMPT CHECK] Looking for pattern: {prompt_pattern}")
        logger.info(f"[PROMPT CHECK] command_start_line: {buffer.command_start_line}")
        logger.info(f"[PROMPT CHECK] total_lines in buffer: {len(buffer.buffer.lines)}")

        # ========== INSERT HERE - RIGHT AFTER THE 3 LOGGER LINES ==========
        # PRIORITY CHECK: Detect and quit pagers before checking for prompts
        pager_detected, pager_type, pager_action = self.pager_detector.detect_pager(buffer)
        if pager_detected and pager_type not in ["password_prompt_excluded", "shell_prompt_excluded"]:

            if pager_action == "continue":
                # Still more output to show - send Space to continue
                logger.info(f"Pager detected ({pager_type}), sending Space to continue")
                if self.ssh_manager and self.ssh_manager.shell:
                    self.ssh_manager.shell.send(' ')  # Space bar to continue
                    import asyncio
                    await asyncio.sleep(0.2)
                    return False, f"pager_continue_{pager_type}"

            elif pager_action == "quit":
                # At end - send 'q' to quit and return to prompt
                logger.info(f"Pager at end ({pager_type}), sending 'q' to quit")
                if self.ssh_manager and self.ssh_manager.shell:
                    self.ssh_manager.shell.send('q')
                    import asyncio
                    await asyncio.sleep(0.2)
                    return False, f"pager_quit_{pager_type}"
            else:
                logger.warning("Pager detected but no ssh_manager to send response.")
        # ================================================================

        # CRITICAL FIX: Check the partial line first (where NEW prompt lives!)
        # The NEW completion prompt doesn't have a newline, so it stays in current_output
        if hasattr(buffer, 'buffer') and hasattr(buffer.buffer, 'current_output'):
            current = buffer.buffer.current_output
            logger.info(f"[PROMPT CHECK] current_output: {repr(current)}")

            if current:
                detected, reason = self.pattern_manager.detect_prompt_in_line(current, prompt_pattern)

                logger.info(f"[PROMPT CHECK] Partial line check: detected={detected}, reason={reason}")

                if detected is True:
                    # Clean prompt found in partial line!
                    logger.info(f"PROMPT DETECTED in partial line: {reason}")
                    return True, f"partial_line_{reason}"

                elif detected == "verify":
                    # Suspicious prompt in partial line - verify it
                    logger.info(f"? Suspicious prompt in partial line: {reason}, verifying...")
                    verified, verify_reason = await self.verify_prompt(buffer, prompt_pattern)
                    if verified:
                        logger.info(f"PROMPT VERIFIED: {verify_reason}")
                        return True, verify_reason
                    else:
                        logger.info(f"Verification failed: {verify_reason}")
        else:
            logger.warning("[PROMPT CHECK] Buffer doesn't have current_output attribute!")

        # CRITICAL FIX: Check completed lines AFTER command_start_line ONLY
        # command_start_line contains the command echo (with old prompt)
        # We want to check lines starting from command_start_line + 1
        total_lines = len(buffer.buffer.lines)
        start_checking_from = buffer.command_start_line + 1  # Skip command echo line

        if start_checking_from >= total_lines:
            logger.info(f"[PROMPT CHECK] No completed output lines yet (start={start_checking_from}, total={total_lines})")
            return False, "no_output_yet"

        # Get lines AFTER command echo
        all_lines = list(buffer.buffer.lines)
        command_output_lines = all_lines[start_checking_from:]

        # Check last 5 lines from command output only
        recent_lines = command_output_lines[-5:] if len(command_output_lines) > 5 else command_output_lines
        logger.info(f"[PROMPT CHECK] Checking {len(recent_lines)} recent lines from command output")

        for i, line in enumerate(recent_lines):
            logger.info(f"[PROMPT CHECK] Line {i}: {repr(line.text)}")
            detected, reason = self.pattern_manager.detect_prompt_in_line(line.text, prompt_pattern)

            if detected is True:
                # Clean prompt found
                logger.info(f"PROMPT DETECTED in output line {i}: {reason}")
                return True, reason

            elif detected == "verify":
                # Suspicious prompt - verify it
                logger.info(f"? Suspicious prompt in output line {i}: {reason}, verifying...")
                verified, verify_reason = await self.verify_prompt(buffer, prompt_pattern)
                if verified:
                    logger.info(f"PROMPT VERIFIED: {verify_reason}")
                    return True, verify_reason
                else:
                    logger.info(f"Verification failed: {verify_reason}")

        logger.info("[PROMPT CHECK] No prompt found in command output")
        return False, "no_prompt_found"

    def is_sudo_prompt(self, buffer) -> bool:
        """
        Check if current output contains sudo password prompt

        Args:
            buffer: FilteredBuffer to check

        Returns:
            True if sudo prompt detected
        """

        # Check partial line (current prompt area)
        if hasattr(buffer, 'current_output'):
            current = buffer.current_output.lower()
            if '[sudo] password' in current or 'password:' in current:
                logger.info(f"Sudo prompt detected in current_output: {current}")
                return True

        # Check ONLY the last line
        if hasattr(buffer, 'lines') and buffer.lines:
            lines_list = list(buffer.lines)
            if lines_list:
                last_line = lines_list[-1]  # Only check the most recent line
                line_text = last_line.text if hasattr(last_line, 'text') else str(last_line)
                line_lower = line_text.lower()
                if '[sudo] password' in line_lower:
                    logger.info(f"Sudo prompt detected in last line: {line_text}")
                    return True

        return False
