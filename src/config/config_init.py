"""
Configuration initialization helper
Copies default config files to REMOTE_TERMINAL_ROOT on first run
"""
import os
import shutil
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def get_config_root() -> Path:
    """Get the configuration root directory (from env var or cwd)"""
    work_dir = os.getenv('REMOTE_TERMINAL_ROOT')
    if work_dir:
        return Path(work_dir)
    return Path.cwd()


def get_package_config_dir() -> Path:
    """Get the package's default config directory"""
    # This file is in src/ or standalone/, go up to find config/
    current_file = Path(__file__)
    
    # Try to find config/ directory
    # Could be at project root (GitHub) or in site-packages (pip)
    possible_locations = [
        current_file.parent.parent / 'config',  # From src/ or standalone/
        current_file.parent / 'config',         # If config is in same dir
    ]
    
    for location in possible_locations:
        if location.exists() and location.is_dir():
            return location
    
    raise FileNotFoundError("Could not find default config directory")


def ensure_config_files() -> tuple[Path, Path]:
    """
    Ensure config files exist in REMOTE_TERMINAL_ROOT.
    Copies defaults from package on first run.
    
    Returns:
        tuple: (config_path, hosts_path)
    """
    config_root = get_config_root()
    package_config = get_package_config_dir()
    
    logger.info(f"Config root: {config_root}")
    logger.info(f"Package config: {package_config}")
    
    # Ensure config root directory exists
    config_root.mkdir(parents=True, exist_ok=True)
    
    # Config file
    user_config = config_root / 'config.yaml'
    default_config = package_config / 'config.yaml'
    
    if not user_config.exists():
        if default_config.exists():
            logger.info(f"Copying default config.yaml to {user_config}")
            shutil.copy2(default_config, user_config)
        else:
            logger.warning(f"Default config not found at {default_config}")
    
    # Hosts file (only copy example if hosts.yaml doesn't exist)
    user_hosts = config_root / 'hosts.yaml'
    default_hosts_example = package_config / 'hosts.yaml.example'
    
    if not user_hosts.exists():
        if default_hosts_example.exists():
            logger.info(f"Copying hosts.yaml.example to {user_hosts}")
            shutil.copy2(default_hosts_example, user_hosts)
            logger.info("Please edit hosts.yaml with your server details")
        else:
            logger.warning(f"Default hosts.yaml.example not found at {default_hosts_example}")
    
    return user_config, user_hosts
