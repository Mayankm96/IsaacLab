#!/usr/bin/env python3

# Copyright (c) 2022-2025, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""
Simple test script to demonstrate asset caching functionality.

This script tests the asset caching system by:
1. Showing current cache status
2. Attempting to cache a small test asset
3. Showing updated cache status

Usage:
    ./isaaclab.sh -p scripts/tools/test_asset_cache.py
"""

from isaaclab.app import AppLauncher

# Launch the app
app_launcher = AppLauncher(headless=True)
simulation_app = app_launcher.app

"""Rest everything follows."""

import isaaclab.utils.assets as assets_utils


def print_separator():
    """Print a visual separator."""
    print("\n" + "=" * 70)


def main():
    """Main test function."""
    print_separator()
    print("Isaac Lab Asset Caching System - Test Script")
    print_separator()

    # Check if caching is enabled
    print(f"\n✓ Cache Enabled: {assets_utils.ASSET_CACHE_ENABLED}")
    print(f"✓ Cache Directory: {assets_utils.ASSET_CACHE_DIR}")

    # Show initial cache statistics
    print("\n--- Initial Cache Statistics ---")
    stats = assets_utils.get_cache_statistics()
    print(f"Number of cached assets: {stats['num_assets']}")
    print(f"Total cache size: {stats['total_size_mb']:.2f} MB")

    # Test caching a small asset
    print_separator()
    print("Testing Asset Caching")
    print_separator()

    # Use a small test asset from Isaac Sim
    test_asset = f"{assets_utils.ISAAC_NUCLEUS_DIR}/Props/Mounts/ThorlabsPost/M4_25mm.usd"
    print(f"\nTest Asset: {test_asset}")

    if assets_utils.ASSET_CACHE_ENABLED:
        print("\nAttempting to cache asset...")

        try:
            cached_path = assets_utils.get_cached_asset_path(test_asset, force_download=False)

            if cached_path:
                print(f"✓ Asset cached successfully!")
                print(f"  Local path: {cached_path}")

                # Show updated statistics
                print("\n--- Updated Cache Statistics ---")
                stats = assets_utils.get_cache_statistics()
                print(f"Number of cached assets: {stats['num_assets']}")
                print(f"Total cache size: {stats['total_size_mb']:.2f} MB")

                print("\n✓ Test completed successfully!")
                print("\nYou can now:")
                print("  - View cache: ./isaaclab.sh -p scripts/tools/manage_asset_cache.py --list")
                print("  - Clear cache: ./isaaclab.sh -p scripts/tools/manage_asset_cache.py --clear-all")
            else:
                print("✗ Failed to cache asset (cache may be disabled or asset not accessible)")
                return False

        except Exception as e:
            print(f"✗ Error during caching test: {e}")
            return False
    else:
        print("\n⚠ Caching is disabled!")
        print("  Enable it with: export ISAACLAB_CACHE_ASSETS=true")
        return False

    print_separator()
    return True


if __name__ == "__main__":
    # Run the test
    success = main()
    # Close the app
    simulation_app.close()
    # Exit with appropriate code
    exit(0 if success else 1)
