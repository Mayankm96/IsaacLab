# Isaac Lab Asset Caching System

## Overview

Isaac Lab now includes an automatic asset caching system that downloads and stores remote assets locally. This means **internet is only needed on the first run** - subsequent runs will use cached assets, allowing you to work offline and significantly speeding up load times.

## Features

✅ **Automatic caching** - Assets are automatically cached when loaded
✅ **Transparent** - Works with existing scripts, no code changes needed
✅ **Recursive dependencies** - Automatically caches USD file references
✅ **Configurable** - Control via environment variables
✅ **Cache management** - Tools to view, clean, and manage cached assets

## How It Works

When you run any Isaac Lab script that loads a remote asset (from Nucleus server):

1. **First Run**: Asset is downloaded from the internet and cached locally
2. **Subsequent Runs**: Cached version is used automatically (no internet needed)
3. **Dependencies**: Referenced USD files are also cached automatically
4. **File Operations**: Functions like `read_file()` and `retrieve_file_path()` also use the cache

## Configuration

### Environment Variables

Control the caching system using these environment variables:

```bash
# Enable/disable caching (default: true)
export ISAACLAB_CACHE_ASSETS=true

# Set custom cache directory (default: ~/.isaaclab/asset_cache)
export ISAACLAB_ASSET_CACHE_DIR=/path/to/your/cache
```

### Disable Caching

To disable caching temporarily:

```bash
export ISAACLAB_CACHE_ASSETS=false
./isaaclab.sh -p your_script.py
```

## Cache Management

### View Cache Statistics

```bash
./isaaclab.sh -p scripts/tools/manage_asset_cache.py --stats
```

This shows:
- Number of cached assets
- Total cache size
- Cache directory location

### List All Cached Assets

```bash
./isaaclab.sh -p scripts/tools/manage_asset_cache.py --list
```

Shows detailed information about each cached asset including:
- Filename and size
- When it was cached
- Last access time
- Remote path

### Pre-Download Assets

Download assets before running your script:

```bash
# Download single asset
./isaaclab.sh -p scripts/tools/manage_asset_cache.py \
    --download "{ISAAC_NUCLEUS_DIR}/Robots/Franka/franka_instanceable.usd"

# Force re-download
./isaaclab.sh -p scripts/tools/manage_asset_cache.py \
    --download "{ISAAC_NUCLEUS_DIR}/Robots/Franka/franka_instanceable.usd" \
    --force
```

### Clear Cache

```bash
# Clear all cached assets
./isaaclab.sh -p scripts/tools/manage_asset_cache.py --clear-all

# Clear assets not accessed in 30 days
./isaaclab.sh -p scripts/tools/manage_asset_cache.py --clear-old 30
```

## Using with Existing Scripts

The caching system works automatically with all existing Isaac Lab scripts. No code changes required!

```bash
# First run - downloads and caches
./isaaclab.sh -p source/standalone/workflows/robomimic/play.py \
    --task Isaac-Lift-Cube-Franka-v0

# Second run - uses cache (faster, no internet needed)
./isaaclab.sh -p source/standalone/workflows/robomimic/play.py \
    --task Isaac-Lift-Cube-Franka-v0
```

## Download Asset Tool Updates

The `download_asset.py` tool now supports caching:

```bash
# Download to cache (reusable across all scripts)
./isaaclab.sh -p scripts/tools/download_asset.py \
    --path "{ISAAC_NUCLEUS_DIR}/Robots/UniversalRobots/ur10e/ur10e.usd" \
    --cache

# Download with dependencies
./isaaclab.sh -p scripts/tools/download_asset.py \
    --path "{ISAAC_NUCLEUS_DIR}/Robots/UniversalRobots/ur10e/ur10e.usd" \
    --cache --cache-deps
```

## Cache Location

By default, assets are cached in:
```
~/.isaaclab/asset_cache/
```

Each asset is stored with a unique name combining a hash of its URL and the original filename.

## Cache Metadata

The cache maintains metadata in `.cache_metadata.json` that tracks:
- Remote URL for each cached asset
- Local path
- File size
- Cache timestamp
- Last access time

This metadata enables smart cache management and cleanup.

## Best Practices

### For Development

1. **Keep cache enabled** during development for faster iterations
2. **Pre-download assets** for your project to work offline
3. **Periodically clean old assets** to manage disk space

### For Production/CI

1. **Pre-populate cache** in Docker images or CI setup
2. **Share cache directory** across containers/runs
3. **Monitor cache size** and set up cleanup policies

### Managing Disk Space

```bash
# Check cache size
./isaaclab.sh -p scripts/tools/manage_asset_cache.py --stats

# Remove old assets (90+ days)
./isaaclab.sh -p scripts/tools/manage_asset_cache.py --clear-old 90

# Clear all if needed
./isaaclab.sh -p scripts/tools/manage_asset_cache.py --clear-all
```

## Troubleshooting

### Cache Not Working

1. Check if caching is enabled:
   ```bash
   echo $ISAACLAB_CACHE_ASSETS
   ```

2. Check cache directory permissions:
   ```bash
   ls -la ~/.isaaclab/asset_cache/
   ```

3. Enable debug logging:
   ```bash
   # In your script or environment
   import logging
   logging.getLogger("isaaclab.utils.assets").setLevel(logging.DEBUG)
   ```

### Assets Still Downloading

- First run will always download
- Check if `force_download` is being used in your code
- Verify the exact URL hasn't changed

### Cache Location

If you can't find the cache:
```bash
./isaaclab.sh -p scripts/tools/manage_asset_cache.py --stats
```

This shows the cache directory location.

## Technical Details

### How Caching is Implemented

1. **USD Spawner Hook**: The `_spawn_from_usd_file()` function checks for cached versions before loading
2. **File Reading**: The `read_file()` function uses cached versions when available
3. **File Retrieval**: The `retrieve_file_path()` function uses the cache by default
4. **Smart Caching**: Only remote URLs (HTTP/HTTPS/Omniverse) are cached
5. **Dependency Resolution**: USD files are scanned for references using regex patterns
6. **Metadata Tracking**: JSON metadata file tracks all cached assets

### Cache Key Generation

Each asset gets a unique cache key:
```
<16-char-hash>_<original-filename>
```

This ensures:
- No collisions between different assets
- Human-readable filenames in cache
- Easy to identify cached files

### Supported Asset Types

The caching system works with:
- `.usd`, `.usda`, `.usdc`, `.usdz` files (with dependency resolution)
- Textures and materials referenced in USD files
- Any other remote files loaded via Isaac Lab

## Examples

### Example 1: Pre-download Robot Assets

```bash
# Cache Franka robot and dependencies
./isaaclab.sh -p scripts/tools/manage_asset_cache.py \
    --download "{ISAAC_NUCLEUS_DIR}/Robots/Franka/franka_instanceable.usd"

# Cache UR10 robot
./isaaclab.sh -p scripts/tools/manage_asset_cache.py \
    --download "{ISAAC_NUCLEUS_DIR}/Robots/UniversalRobots/ur10e/ur10e.usd"

# Check cache
./isaaclab.sh -p scripts/tools/manage_asset_cache.py --list
```

### Example 2: Offline Development Workflow

```bash
# Day 1: Online - cache everything you need
export ISAACLAB_CACHE_ASSETS=true
./isaaclab.sh -p source/standalone/workflows/robomimic/play.py --task Isaac-Lift-Cube-Franka-v0
./isaaclab.sh -p source/standalone/tutorials/01_assets/create_articulation.py

# Day 2: Offline - use cached assets
# (disconnect from internet)
./isaaclab.sh -p source/standalone/workflows/robomimic/play.py --task Isaac-Lift-Cube-Franka-v0
# Works without internet! 🎉
```

### Example 3: Docker Image with Pre-cached Assets

```dockerfile
FROM isaac-lab-base

# Set cache directory
ENV ISAACLAB_ASSET_CACHE_DIR=/opt/isaaclab/asset_cache
ENV ISAACLAB_CACHE_ASSETS=true

# Pre-download common assets
RUN ./isaaclab.sh -p scripts/tools/manage_asset_cache.py \
    --download "{ISAAC_NUCLEUS_DIR}/Robots/Franka/franka_instanceable.usd"

# Now scripts run fast without downloading
```

## FAQ

**Q: Does this use extra disk space?**
A: Yes, but you control it. Use `--clear-old` to remove unused assets.

**Q: Will my scripts still work without caching?**
A: Yes! Just set `ISAACLAB_CACHE_ASSETS=false`.

**Q: Can I share cache across multiple users?**
A: Yes, set `ISAACLAB_ASSET_CACHE_DIR` to a shared directory with appropriate permissions.

**Q: What happens if a cached asset is corrupted?**
A: Use `--force` flag to re-download:
```bash
./isaaclab.sh -p scripts/tools/manage_asset_cache.py --download <path> --force
```

**Q: Does this work with custom assets?**
A: Yes! Any remote asset loaded via Isaac Lab's asset system will be cached.

## Summary

The asset caching system makes Isaac Lab development faster and enables offline work. It's enabled by default, works automatically, and requires no code changes. Use the management tools to view and control your cache as needed.

Happy developing! 🚀
