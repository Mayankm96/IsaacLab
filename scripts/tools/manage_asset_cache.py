#!/usr/bin/env python3

# Copyright (c) 2022-2025, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""
Script to manage the Isaac Lab asset cache.

This script provides utilities to manage cached assets downloaded from remote servers.
It allows you to:
- View cache statistics and contents
- Clear the cache (all or old assets)
- Pre-download specific assets
- Configure cache settings

The cache is used to store remote assets locally so that they don't need to be
downloaded every time a script is run. This significantly speeds up subsequent runs
and allows working offline after the initial download.

Usage:

.. code-block:: bash

    # View cache statistics
    ./isaaclab.sh -p scripts/tools/manage_asset_cache.py --stats

    # List all cached assets
    ./isaaclab.sh -p scripts/tools/manage_asset_cache.py --list

    # Clear all cached assets
    ./isaaclab.sh -p scripts/tools/manage_asset_cache.py --clear-all

    # Clear assets not accessed in 30 days
    ./isaaclab.sh -p scripts/tools/manage_asset_cache.py --clear-old 30

    # Pre-download an asset and its dependencies
    ./isaaclab.sh -p scripts/tools/manage_asset_cache.py \
        --download "{ISAAC_NUCLEUS_DIR}/Robots/UniversalRobots/ur10e/ur10e.usd"

Environment Variables:
    ISAACLAB_CACHE_ASSETS: Enable/disable caching (default: true)
    ISAACLAB_ASSET_CACHE_DIR: Cache directory (default: ~/.isaaclab/asset_cache)
"""

import argparse
import sys
from datetime import datetime

from isaaclab.app import AppLauncher

# Parse arguments
parser = argparse.ArgumentParser(description="Manage Isaac Lab asset cache.")
parser.add_argument("--stats", action="store_true", help="Show cache statistics")
parser.add_argument("--list", action="store_true", help="List all cached assets")
parser.add_argument("--clear-all", action="store_true", help="Clear all cached assets")
parser.add_argument(
    "--clear-old", type=int, metavar="DAYS", help="Clear assets not accessed in specified number of days"
)
parser.add_argument(
    "--download", type=str, metavar="PATH", help="Pre-download an asset and its dependencies (supports placeholders)"
)
parser.add_argument("--force", action="store_true", help="Force re-download when using --download")

args_cli = parser.parse_args()

# Check if at least one action is specified
if not any([args_cli.stats, args_cli.list, args_cli.clear_all, args_cli.clear_old, args_cli.download]):
    parser.print_help()
    sys.exit(0)

# Launch the app
app_launcher = AppLauncher(headless=True)
simulation_app = app_launcher.app

"""Rest everything follows."""

import isaaclab.utils.assets as assets_utils

# Placeholder dictionary
NUCLEUS_DIR_PLACEHOLDERS = {
    "{ISAACLAB_NUCLEUS_DIR}": assets_utils.ISAACLAB_NUCLEUS_DIR,
    "{ISAAC_NUCLEUS_DIR}": assets_utils.ISAAC_NUCLEUS_DIR,
    "{NVIDIA_NUCLEUS_DIR}": assets_utils.NVIDIA_NUCLEUS_DIR,
    "{NUCLEUS_ASSET_ROOT_DIR}": assets_utils.NUCLEUS_ASSET_ROOT_DIR,
}


def format_size(size_mb: float) -> str:
    """Format size in MB to human-readable string."""
    if size_mb < 1:
        return f"{size_mb * 1024:.2f} KB"
    elif size_mb < 1024:
        return f"{size_mb:.2f} MB"
    else:
        return f"{size_mb / 1024:.2f} GB"


def format_timestamp(timestamp: float) -> str:
    """Format Unix timestamp to human-readable date."""
    if timestamp == 0:
        return "Unknown"
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def show_statistics():
    """Show cache statistics."""
    print("\n" + "=" * 70)
    print("Isaac Lab Asset Cache Statistics")
    print("=" * 70)

    stats = assets_utils.get_cache_statistics()

    print(f"\nCache Directory: {stats['cache_dir']}")
    print(f"Cache Enabled:   {assets_utils.ASSET_CACHE_ENABLED}")
    print(f"\nTotal Assets:    {stats['num_assets']}")
    print(f"Total Size:      {format_size(stats['total_size_mb'])}")

    if stats["num_assets"] == 0:
        print("\nCache is empty.")
    else:
        print(f"\nUse --list to see detailed information about cached assets.")

    print("=" * 70 + "\n")


def list_assets():
    """List all cached assets."""
    print("\n" + "=" * 70)
    print("Cached Assets")
    print("=" * 70)

    stats = assets_utils.get_cache_statistics()

    if stats["num_assets"] == 0:
        print("\nCache is empty.")
    else:
        # Sort by last accessed time (most recent first)
        assets = sorted(stats["assets"], key=lambda x: x["last_accessed"], reverse=True)

        for i, asset in enumerate(assets, 1):
            print(f"\n{i}. {asset['filename']}")
            print(f"   Size:         {format_size(asset['size_mb'])}")
            print(f"   Cached:       {format_timestamp(asset['cached_at'])}")
            print(f"   Last Access:  {format_timestamp(asset['last_accessed'])}")
            print(f"   Remote Path:  {asset['remote_path'][:80]}...")

    print("\n" + "=" * 70 + "\n")


def clear_all():
    """Clear all cached assets."""
    print("\nClearing all cached assets...")

    count = assets_utils.clear_asset_cache()

    if count > 0:
        print(f"✓ Successfully removed {count} cached asset(s).\n")
    else:
        print("✓ Cache was already empty.\n")


def clear_old(days: int):
    """Clear assets not accessed in specified days."""
    print(f"\nClearing assets not accessed in {days} days...")

    count = assets_utils.clear_asset_cache(older_than_days=days)

    if count > 0:
        print(f"✓ Successfully removed {count} cached asset(s).\n")
    else:
        print(f"✓ No assets found older than {days} days.\n")


def download_asset(path: str, force: bool = False):
    """Pre-download an asset and its dependencies."""
    # Resolve placeholders
    for placeholder, value in NUCLEUS_DIR_PLACEHOLDERS.items():
        if placeholder in path:
            path = path.replace(placeholder, value)
            print(f"Resolved {placeholder} -> {value}")

    print(f"\nDownloading asset and dependencies: {path}")

    if not assets_utils.ASSET_CACHE_ENABLED:
        print("ERROR: Asset caching is disabled. Set ISAACLAB_CACHE_ASSETS=true to enable.")
        return False

    try:
        cached_path = assets_utils.cache_asset_with_dependencies(path, force_download=force)

        if cached_path:
            print(f"✓ Successfully cached asset to: {cached_path}")

            # Show updated statistics
            stats = assets_utils.get_cache_statistics()
            print(f"\nCache now contains {stats['num_assets']} asset(s)")
            print(f"Total cache size: {format_size(stats['total_size_mb'])}\n")
            return True
        else:
            print(f"✗ Failed to cache asset: {path}\n")
            return False

    except Exception as e:
        print(f"✗ Error caching asset: {e}\n")
        return False


def main():
    """Main entry point."""
    success = True

    # Execute requested actions
    if args_cli.stats:
        show_statistics()

    if args_cli.list:
        list_assets()

    if args_cli.clear_all:
        clear_all()

    if args_cli.clear_old:
        clear_old(args_cli.clear_old)

    if args_cli.download:
        success = download_asset(args_cli.download, force=args_cli.force)

    return success


if __name__ == "__main__":
    # Run the main function
    success = main()
    # Close the app
    simulation_app.close()
    # Exit with appropriate code
    sys.exit(0 if success else 1)
