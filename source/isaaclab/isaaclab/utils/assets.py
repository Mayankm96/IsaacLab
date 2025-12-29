# Copyright (c) 2022-2025, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Sub-module that defines the host-server where assets and resources are stored.

By default, we use the Isaac Sim Nucleus Server for hosting assets and resources. This makes
distribution of the assets easier and makes the repository smaller in size code-wise.

For more information, please check information on `Omniverse Nucleus`_.

.. _Omniverse Nucleus: https://docs.omniverse.nvidia.com/nucleus/latest/overview/overview.html
"""

import asyncio
import hashlib
import io
import json
import logging
import os
import shutil
import tempfile
import time
from typing import Literal

import carb
import omni.client

# import logger
logger = logging.getLogger(__name__)

NUCLEUS_ASSET_ROOT_DIR = carb.settings.get_settings().get("/persistent/isaac/asset_root/cloud")  # type: ignore
"""Path to the root directory on the Nucleus Server."""

NVIDIA_NUCLEUS_DIR = f"{NUCLEUS_ASSET_ROOT_DIR}/NVIDIA"
"""Path to the root directory on the NVIDIA Nucleus Server."""

ISAAC_NUCLEUS_DIR = f"{NUCLEUS_ASSET_ROOT_DIR}/Isaac"
"""Path to the ``Isaac`` directory on the NVIDIA Nucleus Server."""

ISAACLAB_NUCLEUS_DIR = f"{ISAAC_NUCLEUS_DIR}/IsaacLab"
"""Path to the ``Isaac/IsaacLab`` directory on the NVIDIA Nucleus Server."""

# Asset caching configuration
ASSET_CACHE_ENABLED = os.getenv("ISAACLAB_CACHE_ASSETS", "true").lower() == "true"
"""Whether asset caching is enabled. Can be controlled via ISAACLAB_CACHE_ASSETS environment variable."""

ASSET_CACHE_DIR = os.getenv(
    "ISAACLAB_ASSET_CACHE_DIR", os.path.join(os.path.expanduser("~"), ".isaaclab", "asset_cache")
)
"""Directory where assets are cached. Can be controlled via ISAACLAB_ASSET_CACHE_DIR environment variable."""

ASSET_CACHE_METADATA_FILE = os.path.join(ASSET_CACHE_DIR, ".cache_metadata.json")
"""Path to the cache metadata file that tracks cached assets."""


def check_file_path(path: str) -> Literal[0, 1, 2]:
    """Checks if a file exists on the Nucleus Server or locally.

    Args:
        path: The path to the file.

    Returns:
        The status of the file. Possible values are listed below.

        * :obj:`0` if the file does not exist
        * :obj:`1` if the file exists locally
        * :obj:`2` if the file exists on the Nucleus Server
    """
    if os.path.isfile(path):
        return 1
    # we need to convert backslash to forward slash on Windows for omni.client API
    elif omni.client.stat(path.replace(os.sep, "/"))[0] == omni.client.Result.OK:
        return 2
    else:
        return 0


def retrieve_file_path(path: str, download_dir: str | None = None, force_download: bool = True) -> str:
    """Retrieves the path to a file on the Nucleus Server or locally.

    If the file exists locally, then the absolute path to the file is returned.
    If the file exists on the Nucleus Server, then the file is downloaded to the local machine
    and the absolute path to the file is returned.

    If no download directory is specified and caching is enabled, the file will be cached
    using the asset cache system. This allows the file to be reused across multiple runs.

    Args:
        path: The path to the file.
        download_dir: The directory where the file should be downloaded. Defaults to None, in which
            case the asset cache is used if enabled, otherwise the system's temporary directory.
        force_download: Whether to force download the file from the Nucleus Server. This will overwrite
            the local file if it exists. Defaults to True.

    Returns:
        The path to the file on the local machine.

    Raises:
        FileNotFoundError: When the file not found locally or on Nucleus Server.
        RuntimeError: When the file cannot be copied from the Nucleus Server to the local machine. This
            can happen when the file already exists locally and :attr:`force_download` is set to False.
    """
    # check file status
    file_status = check_file_path(path)
    if file_status == 1:
        return os.path.abspath(path)
    elif file_status == 2:
        # If no download dir specified, try to use cache
        if download_dir is None:
            cached_path = get_cached_asset_path(path, force_download=force_download)
            if cached_path is not None:
                return cached_path
            # Cache disabled or failed, use temp directory
            download_dir = tempfile.gettempdir()
        else:
            download_dir = os.path.abspath(download_dir)

        # create download directory if it does not exist
        if not os.path.exists(download_dir):
            os.makedirs(download_dir)
        # download file in temp directory using os
        file_name = os.path.basename(omni.client.break_url(path.replace(os.sep, "/")).path)
        target_path = os.path.join(download_dir, file_name)
        # check if file already exists locally
        if not os.path.isfile(target_path) or force_download:
            # copy file to local machine
            result = omni.client.copy(path.replace(os.sep, "/"), target_path, omni.client.CopyBehavior.OVERWRITE)
            if result != omni.client.Result.OK and force_download:
                raise RuntimeError(f"Unable to copy file: '{path}'. Is the Nucleus Server running?")
        return os.path.abspath(target_path)
    else:
        raise FileNotFoundError(f"Unable to find the file: {path}")


def read_file(path: str) -> io.BytesIO:
    """Reads a file from the Nucleus Server or locally.

    If the file is remote and caching is enabled, it will be cached locally first
    and then read from the cache. This allows subsequent reads to work offline.

    Args:
        path: The path to the file.

    Raises:
        FileNotFoundError: When the file not found locally or on Nucleus Server.

    Returns:
        The content of the file.
    """
    # check file status
    file_status = check_file_path(path)
    if file_status == 1:
        # File exists locally, read directly
        with open(path, "rb") as f:
            return io.BytesIO(f.read())
    elif file_status == 2:
        # File is remote - try to use cache first
        cached_path = get_cached_asset_path(path, force_download=False)
        if cached_path is not None:
            # Read from cached version
            with open(cached_path, "rb") as f:
                return io.BytesIO(f.read())
        else:
            # Cache disabled or failed, read directly from remote
            file_content = omni.client.read_file(path.replace(os.sep, "/"))[2]
            return io.BytesIO(memoryview(file_content).tobytes())
    else:
        raise FileNotFoundError(f"Unable to find the file: {path}")


"""
Nucleus Connection.
"""


def check_usd_path_with_timeout(usd_path: str, timeout: float = 300, log_interval: float = 30) -> bool:
    """Checks whether the given USD file path is available on the NVIDIA Nucleus server.

    This function synchronously runs an asynchronous USD path availability check,
    logging progress periodically until it completes. The file is available on the server
    if the HTTP status code is 200. Otherwise, the file is not available on the server.

    This is useful for checking server responsiveness before attempting to load a remote
    asset. It will block execution until the check completes or times out.

    Args:
        usd_path: The remote USD file path to check.
        timeout: Maximum time (in seconds) to wait for the server check.
        log_interval: Interval (in seconds) at which progress is logged.

    Returns:
        Whether the given USD path is available on the server.
    """
    start_time = time.time()
    loop = asyncio.get_event_loop()

    coroutine = _is_usd_path_available(usd_path, timeout)
    task = asyncio.ensure_future(coroutine)

    next_log_time = start_time + log_interval

    first_log = True
    while not task.done():
        now = time.time()
        if now >= next_log_time:
            elapsed = int(now - start_time)
            if first_log:
                logger.warning(f"Checking server availability for USD path: {usd_path} (timeout: {timeout}s)")
                first_log = False
            logger.warning(f"Waiting for server response... ({elapsed}s elapsed)")
            next_log_time += log_interval
        loop.run_until_complete(asyncio.sleep(0.1))  # Yield to allow async work

    return task.result()


"""
Asset Caching Functions.
"""


def _get_cache_key(remote_path: str) -> str:
    """Generate a unique cache key for a remote path.

    Args:
        remote_path: The remote path to generate a cache key for.

    Returns:
        A unique cache key based on the remote path.
    """
    # Use hash of the full path to create a unique key
    path_hash = hashlib.md5(remote_path.encode()).hexdigest()[:16]
    # Extract filename for readability
    filename = os.path.basename(omni.client.break_url(remote_path.replace(os.sep, "/")).path)
    return f"{path_hash}_{filename}"


def _load_cache_metadata() -> dict:
    """Load cache metadata from disk.

    Returns:
        Dictionary containing cache metadata.
    """
    if not os.path.exists(ASSET_CACHE_METADATA_FILE):
        return {}

    try:
        with open(ASSET_CACHE_METADATA_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to load cache metadata: {e}")
        return {}


def _save_cache_metadata(metadata: dict) -> None:
    """Save cache metadata to disk.

    Args:
        metadata: Dictionary containing cache metadata.
    """
    try:
        os.makedirs(os.path.dirname(ASSET_CACHE_METADATA_FILE), exist_ok=True)
        with open(ASSET_CACHE_METADATA_FILE, "w") as f:
            json.dump(metadata, f, indent=2)
    except OSError as e:
        logger.warning(f"Failed to save cache metadata: {e}")


def _is_remote_path(path: str) -> bool:
    """Check if a path is a remote path (HTTP/HTTPS or Omniverse).

    Args:
        path: The path to check.

    Returns:
        True if the path is remote, False otherwise.
    """
    path_lower = path.lower()
    return (
        path_lower.startswith("http://") or path_lower.startswith("https://") or path_lower.startswith("omniverse://")
    )


def _extract_usd_references(usd_file_path: str) -> list[str]:
    """Extract references from a USD file.

    This function reads a USD file and extracts all remote references (HTTP/HTTPS/Omniverse URLs)
    that it contains. This includes sublayers, references, and payloads.

    Args:
        usd_file_path: Path to the local USD file to scan.

    Returns:
        List of remote paths referenced in the USD file.
    """
    references = []

    try:
        # Read the USD file as text to extract references
        # We use a simple text-based approach to avoid heavy USD API dependencies
        with open(usd_file_path, encoding="utf-8", errors="ignore") as f:
            content = f.read()

        # Look for common USD reference patterns
        import re

        # Pattern for various USD reference types
        # Matches @http...@, @https...@, @omniverse...@
        patterns = [
            r"@(https?://[^@\s]+)@",
            r"@(omniverse://[^@\s]+)@",
            r'"(https?://[^"\s]+\.usd[^"]*)"',
            r'"(omniverse://[^"\s]+\.usd[^"]*)"',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if match not in references:
                    references.append(match)

    except Exception as e:
        logger.debug(f"Could not extract references from {usd_file_path}: {e}")

    return references


def cache_asset_with_dependencies(remote_path: str, force_download: bool = False, max_depth: int = 3) -> str | None:
    """Cache an asset and all its dependencies recursively.

    This function caches a remote asset and recursively caches any USD files it references.
    This ensures that all dependencies are available locally.

    Args:
        remote_path: The remote path to the asset.
        force_download: Whether to force re-download assets even if cached. Defaults to False.
        max_depth: Maximum recursion depth for dependency resolution. Defaults to 3.

    Returns:
        The local path to the cached asset, or None if caching failed.
    """
    # Cache the main asset
    cached_path = get_cached_asset_path(remote_path, force_download)

    if cached_path is None or max_depth <= 0:
        return cached_path

    # Check if it's a USD file that might have dependencies
    if not cached_path.lower().endswith((".usd", ".usda", ".usdc", ".usdz")):
        return cached_path

    try:
        # Extract and cache dependencies
        references = _extract_usd_references(cached_path)

        if references:
            logger.debug(f"Found {len(references)} references in {os.path.basename(cached_path)}")

            for ref_path in references:
                if _is_remote_path(ref_path):
                    logger.debug(f"Caching dependency: {ref_path}")
                    # Recursively cache dependencies
                    cache_asset_with_dependencies(ref_path, force_download, max_depth - 1)

    except Exception as e:
        logger.debug(f"Error processing dependencies for {cached_path}: {e}")

    return cached_path


def get_cached_asset_path(remote_path: str, force_download: bool = False) -> str | None:
    """Get the local path for a cached remote asset, downloading if necessary.

    This function checks if a remote asset is already cached locally. If not, and caching
    is enabled, it downloads the asset and caches it. If caching is disabled, returns None.

    Args:
        remote_path: The remote path to the asset.
        force_download: Whether to force re-download the asset even if cached. Defaults to False.

    Returns:
        The local path to the cached asset, or None if caching is disabled or failed.
    """
    # Check if caching is enabled
    if not ASSET_CACHE_ENABLED:
        return None

    # Check if path is actually remote
    if not _is_remote_path(remote_path):
        return None

    try:
        # Generate cache key
        cache_key = _get_cache_key(remote_path)
        filename = os.path.basename(omni.client.break_url(remote_path.replace(os.sep, "/")).path)
        cached_path = os.path.join(ASSET_CACHE_DIR, cache_key)

        # Load metadata
        metadata = _load_cache_metadata()

        # Check if asset is already cached and valid
        if os.path.exists(cached_path) and not force_download:
            logger.debug(f"Using cached asset: {cached_path}")
            # Update access time in metadata
            if cache_key in metadata:
                metadata[cache_key]["last_accessed"] = time.time()
                _save_cache_metadata(metadata)
            return cached_path

        # Download asset to cache
        logger.info(f"Caching asset from: {remote_path}")
        os.makedirs(ASSET_CACHE_DIR, exist_ok=True)

        # Use retrieve_file_path to download
        result = omni.client.copy(remote_path.replace(os.sep, "/"), cached_path, omni.client.CopyBehavior.OVERWRITE)

        if result != omni.client.Result.OK:
            logger.warning(f"Failed to cache asset: {remote_path}")
            return None

        # Update metadata
        metadata[cache_key] = {
            "remote_path": remote_path,
            "local_path": cached_path,
            "filename": filename,
            "cached_at": time.time(),
            "last_accessed": time.time(),
            "size_bytes": os.path.getsize(cached_path) if os.path.exists(cached_path) else 0,
        }
        _save_cache_metadata(metadata)

        logger.info(f"Asset cached successfully: {cached_path}")
        return cached_path

    except Exception as e:
        logger.warning(f"Error caching asset '{remote_path}': {e}")
        return None


def get_cache_statistics() -> dict:
    """Get statistics about the asset cache.

    Returns:
        Dictionary containing cache statistics including:
        - num_assets: Number of cached assets
        - total_size_mb: Total size of cache in MB
        - assets: List of cached assets with details
    """
    metadata = _load_cache_metadata()

    total_size = 0
    assets = []

    for cache_key, info in metadata.items():
        local_path = info.get("local_path", "")
        if os.path.exists(local_path):
            size = os.path.getsize(local_path)
            total_size += size
            assets.append({
                "remote_path": info.get("remote_path", ""),
                "filename": info.get("filename", ""),
                "size_mb": size / (1024 * 1024),
                "cached_at": info.get("cached_at", 0),
                "last_accessed": info.get("last_accessed", 0),
            })

    return {
        "num_assets": len(assets),
        "total_size_mb": total_size / (1024 * 1024),
        "cache_dir": ASSET_CACHE_DIR,
        "assets": assets,
    }


def clear_asset_cache(older_than_days: int | None = None) -> int:
    """Clear the asset cache.

    Args:
        older_than_days: If specified, only clear assets not accessed in this many days.
            If None, clears all cached assets.

    Returns:
        Number of assets removed from cache.
    """
    metadata = _load_cache_metadata()
    removed_count = 0

    if older_than_days is None:
        # Remove everything
        if os.path.exists(ASSET_CACHE_DIR):
            try:
                shutil.rmtree(ASSET_CACHE_DIR)
                logger.info(f"Cleared all cached assets from: {ASSET_CACHE_DIR}")
                removed_count = len(metadata)
            except Exception as e:
                logger.error(f"Failed to clear cache: {e}")
        return removed_count

    # Remove only old assets
    current_time = time.time()
    cutoff_time = current_time - (older_than_days * 24 * 60 * 60)

    keys_to_remove = []
    for cache_key, info in metadata.items():
        last_accessed = info.get("last_accessed", 0)
        if last_accessed < cutoff_time:
            local_path = info.get("local_path", "")
            if os.path.exists(local_path):
                try:
                    os.remove(local_path)
                    removed_count += 1
                    logger.debug(f"Removed cached asset: {local_path}")
                except Exception as e:
                    logger.warning(f"Failed to remove cached asset {local_path}: {e}")
            keys_to_remove.append(cache_key)

    # Update metadata
    for key in keys_to_remove:
        del metadata[key]

    _save_cache_metadata(metadata)
    logger.info(f"Removed {removed_count} cached assets older than {older_than_days} days")

    return removed_count


"""
Helper functions.
"""


async def _is_usd_path_available(usd_path: str, timeout: float) -> bool:
    """Checks whether the given USD path is available on the Omniverse Nucleus server.

    This function is a asynchronous routine to check the availability of the given USD path on the Omniverse Nucleus server.
    It will return True if the USD path is available on the server, False otherwise.

    Args:
        usd_path: The remote or local USD file path to check.
        timeout: Timeout in seconds for the async stat call.

    Returns:
        Whether the given USD path is available on the server.
    """
    try:
        result, _ = await asyncio.wait_for(omni.client.stat_async(usd_path), timeout=timeout)
        return result == omni.client.Result.OK
    except asyncio.TimeoutError:
        logger.warning(f"Timed out after {timeout}s while checking for USD: {usd_path}")
        return False
    except Exception as ex:
        logger.warning(f"Exception during USD file check: {type(ex).__name__}: {ex}")
        return False
