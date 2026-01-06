"""
SSH Connection Management
Handles SSH connection, reconnection, and lifecycle
"""

import paramiko
import socket
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class SSHConnection:
    """Manages SSH connection lifecycle"""

    def __init__(self, host: str = "", user: str = "", password: str = "", port: int = 22,
                 keepalive_interval: int = 30, reconnect_attempts: int = 3,
                 connection_timeout: int = 10):
        """
        Initialize SSH Connection Manager

        Args:
            host: Remote host address (can be empty for multi-server mode)
            user: Username for authentication (can be empty for multi-server mode)
            password: Password for authentication (can be empty for multi-server mode)
            port: SSH port (default 22)
            keepalive_interval: Seconds between keepalive packets
            reconnect_attempts: Number of reconnection attempts
            connection_timeout: Connection timeout in seconds
        """
        self.host = host
        self.user = user
        self.password = password
        self.port = port
        self.keepalive_interval = keepalive_interval
        self.reconnect_attempts = reconnect_attempts
        self.connection_timeout = connection_timeout

        self.client: Optional[paramiko.SSHClient] = None
        self.shell: Optional[paramiko.Channel] = None
        self.connected = False
        self.reconnecting = False
        self._sftp = None

    def reconfigure(self, host: str, user: str, password: str, port: int = 22) -> None:
        """
        Reconfigure connection parameters (disconnect first if connected)

        Args:
            host: New remote host address
            user: New username
            password: New password
            port: New SSH port
        """
        if self.connected:
            self.disconnect()

        self.host = host
        self.user = user
        self.password = password
        self.port = port
        logger.info(f"SSH connection reconfigured for {user}@{host}:{port}")

    def connect(self, host: str = None, user: str = None, password: str = None, port: int = None) -> bool:
        """
        Establish SSH connection

        Args:
            host: Remote host (optional, uses configured if not provided)
            user: Username (optional, uses configured if not provided)
            password: Password (optional, uses configured if not provided)
            port: SSH port (optional, uses configured if not provided)

        Returns:
            True if connection successful, False otherwise
        """
        # Allow override of connection parameters
        if host is not None:
            self.host = host
        if user is not None:
            self.user = user
        if password is not None:
            self.password = password
        if port is not None:
            self.port = port

        try:
            logger.info(f"Connecting to {self.user}@{self.host}:{self.port}")

            logger.info(f"DEBUG: password='{self.password}', type={type(self.password)}, len={len(self.password)}")  


            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            self.client.connect(
                hostname=self.host,
                port=self.port,
                username=self.user,
                password=self.password,
                timeout=self.connection_timeout,
                look_for_keys=False,
                allow_agent=False
            )

            # Set keepalive
            transport = self.client.get_transport()
            if transport:
                transport.set_keepalive(self.keepalive_interval)

            # Get interactive shell
            self.shell = self.client.invoke_shell(
                term='xterm-256color',
                width=120,
                height=40
            )

            self.connected = True
            logger.info("SSH connection established")

            # Wait for initial output (welcome message + prompt)
            time.sleep(0.5)

            return True

        except Exception as e:
            logger.error(f"Connection failed: {e}")
            self.connected = False
            return False

    def disconnect(self) -> None:
        """Close SSH connection"""
        logger.info("Disconnecting SSH")

        # Close SFTP client if exists
        if self._sftp is not None:
            try:
                self._sftp.close()
                logger.info("SFTP client closed")
            except Exception as e:
                logger.warning(f"Error closing SFTP client: {e}")
            finally:
                self._sftp = None

        if self.shell:
            try:
                self.shell.close()
            except:
                pass
            self.shell = None

        if self.client:
            try:
                self.client.close()
            except:
                pass
            self.client = None

        self.connected = False
        logger.info("SSH disconnected")

    def reconnect(self) -> bool:
        """
        Attempt to reconnect to remote machine

        Returns:
            True if reconnection successful
        """
        if self.reconnecting:
            return False

        self.reconnecting = True
        logger.info("Attempting reconnection...")

        self.disconnect()

        for attempt in range(self.reconnect_attempts):
            logger.info(f"Reconnection attempt {attempt + 1}/{self.reconnect_attempts}")
            time.sleep(2 ** attempt)  # Exponential backoff

            if self.connect():
                self.reconnecting = False
                logger.info("Reconnection successful")
                return True

        self.reconnecting = False
        logger.error("Reconnection failed after all attempts")
        return False

    def is_connected(self) -> bool:
        """Check if currently connected"""
        return self.connected and self.client and self.client.get_transport() and \
               self.client.get_transport().is_active()

    def get_connection_info(self) -> dict:
        """Get connection information"""
        return {
            'host': self.host,
            'port': self.port,
            'user': self.user,
            'connected': self.connected,
            'reconnecting': self.reconnecting
        }

    def get_sftp(self) -> paramiko.SFTPClient:
        """
        Get SFTP client from existing SSH connection.
        Creates a new SFTP client if needed or if the existing one is closed.

        Returns:
            paramiko.SFTPClient: Active SFTP client

        Raises:
            RuntimeError: If SSH not connected
        """
        if not self.is_connected():
            raise RuntimeError("SSH not connected. Use connect() first.")

        # Create new SFTP client if needed
        if self._sftp is None or self._sftp.get_channel().closed:
            logger.info("Creating new SFTP client")
            self._sftp = self.client.open_sftp()

        return self._sftp

    def resize_pty(self, cols: int, rows: int) -> bool:
        """
        Resize the pseudo-terminal

        Args:
            cols: Number of columns
            rows: Number of rows

        Returns:
            True if resize successful, False otherwise
        """
        if not self.connected or not self.shell:
            logger.warning("Cannot resize PTY: not connected")
            return False

        try:
            self.shell.resize_pty(width=cols, height=rows)
            logger.debug(f"PTY resized to {cols}x{rows}")
            return True
        except Exception as e:
            logger.error(f"Failed to resize PTY: {e}")
            return False
