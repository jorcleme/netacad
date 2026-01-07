"""
Playwright configuration for containerized environments.

This module provides browser launch configurations optimized for:
- Docker containers
- OpenShift CAE Runtime
- Other Kubernetes environments
"""

import os
from typing import Any, Dict, List


def get_browser_args() -> List[str]:
    """
    Get browser arguments optimized for container environments.

    Returns:
        List of chromium arguments
    """
    args = [
        "--disable-gpu",
        "--shm-size=1g",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-setuid-sandbox",
        "--disable-software-rasterizer",
        "--disable-accelerated-2d-canvas",
        "--disable-web-security",
        "--single-process",  # Important for containers with limited resources
    ]

    # Add proxy settings if configured
    http_proxy = os.getenv("HTTP_PROXY") or os.getenv("http_proxy")
    if http_proxy:
        args.append(f"--proxy-server={http_proxy}")

    return args


def get_browser_launch_config(headless: bool = True) -> Dict[str, Any]:
    """
    Get complete browser launch configuration.

    Args:
        headless: Whether to run in headless mode

    Returns:
        Dictionary with browser launch options
    """
    config = {
        "headless": headless,
        "args": get_browser_args(),
        "timeout": 60000,  # 60 second timeout
    }

    # Use custom executable path if provided (for external browser service)
    executable_path = os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH")
    if executable_path and os.path.exists(executable_path):
        config["executable_path"] = executable_path

    return config


def get_context_config() -> Dict[str, Any]:
    """
    Get browser context configuration.

    Returns:
        Dictionary with context options
    """
    return {
        "viewport": {"width": 1920, "height": 1080},
        "accept_downloads": True,
        "bypass_csp": True,  # Bypass Content Security Policy
        "ignore_https_errors": True,  # For self-signed certs in dev
        "locale": "en-US",
        "timezone_id": "America/New_York",
        "user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    }


def is_containerized() -> bool:
    """
    Detect if running in a containerized environment.

    Returns:
        True if running in container, False otherwise
    """
    # Check for common container indicators
    if os.path.exists("/.dockerenv"):
        return True

    # Check cgroup (works for Docker and OpenShift)
    try:
        with open("/proc/1/cgroup", "r") as f:
            content = f.read()
            if "docker" in content or "kubepods" in content:
                return True
    except (FileNotFoundError, PermissionError):
        pass

    # Check for OpenShift-specific env vars
    if os.getenv("OPENSHIFT_BUILD_NAME") or os.getenv("KUBERNETES_SERVICE_HOST"):
        return True

    return False


def get_playwright_config() -> Dict[str, Any]:
    """
    Get comprehensive Playwright configuration.

    Returns:
        Complete configuration dict
    """
    config = {
        "browser_launch": get_browser_launch_config(),
        "context": get_context_config(),
        "is_containerized": is_containerized(),
    }

    # Add environment-specific settings
    if config["is_containerized"]:
        # More conservative settings for containers
        config["browser_launch"]["timeout"] = 120000  # 2 minutes
        config["navigation_timeout"] = 60000  # 1 minute per navigation
        config["wait_timeout"] = 30000  # 30 seconds for waits
    else:
        # Development settings
        config["navigation_timeout"] = 30000
        config["wait_timeout"] = 10000

    return config


# Export convenient function for external browser service
def get_ws_endpoint() -> str | None:
    """
    Get WebSocket endpoint for external browser service.

    Useful for connecting to browserless.io or similar services.

    Returns:
        WebSocket URL or None if not configured
    """
    return os.getenv("PLAYWRIGHT_WS_ENDPOINT")
