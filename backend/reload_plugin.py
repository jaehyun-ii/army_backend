#!/usr/bin/env python3
"""
Force reload of iterative_gradient_2d plugin.
Run this with: python reload_plugin.py
"""
import sys
import importlib

# Remove from cache if exists
modules_to_remove = [
    'app.plugins.attacks.iterative_gradient_2d',
    'app.plugins.registry',
    'app.plugins'
]

for mod in modules_to_remove:
    if mod in sys.modules:
        del sys.modules[mod]
        print(f"Removed {mod} from cache")

# Clear __pycache__
import shutil
from pathlib import Path

plugin_dir = Path(__file__).parent / "app" / "plugins" / "attacks"
pycache_dir = plugin_dir / "__pycache__"

if pycache_dir.exists():
    shutil.rmtree(pycache_dir)
    print(f"Cleared {pycache_dir}")

# Reimport
from app.plugins import attack_plugin_registry

# Unregister old version
if "iterative_gradient_2d" in attack_plugin_registry._plugins:
    attack_plugin_registry.unregister("iterative_gradient_2d")
    print("Unregistered old iterative_gradient_2d")

# Discover plugins again
count = attack_plugin_registry.discover_plugins()
print(f"Discovered {count} plugins")

# Check version
plugin = attack_plugin_registry.get_plugin("iterative_gradient_2d")
if plugin:
    print(f"✓ Loaded iterative_gradient_2d v{plugin.version}")
    print(f"  Has _get_current_detections: {hasattr(plugin, '_get_current_detections')}")
else:
    print("✗ Failed to load iterative_gradient_2d")
