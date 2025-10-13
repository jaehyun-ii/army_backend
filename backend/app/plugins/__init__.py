"""
Adversarial attack plugins module.
"""
from .registry import attack_plugin_registry
from .base import AttackPlugin, AttackCategory, AttackConfig, AttackResult
from .patch_2d_base import Patch2DGenerationPlugin, Patch2DConfig, Patch2DResult
from .noise_2d_base import (
    Noise2DAttackPlugin,
    GradientBasedNoise2DPlugin,
    RandomNoise2DPlugin,
    Noise2DConfig,
    Noise2DResult
)


def initialize_plugins():
    """
    Initialize and register all attack plugins.

    This function should be called on application startup.
    """
    import logging
    logger = logging.getLogger(__name__)

    logger.info("Initializing attack plugins...")

    # Discover and register plugins from attacks directory
    count = attack_plugin_registry.discover_plugins()

    logger.info(f"Registered {count} attack plugins")

    # List all registered plugins
    plugins = attack_plugin_registry.list_plugins()
    for plugin_info in plugins:
        logger.info(f"  - {plugin_info['name']} v{plugin_info['version']}: {plugin_info['description']}")

    return count


__all__ = [
    "attack_plugin_registry",
    "initialize_plugins",
    "AttackPlugin",
    "AttackCategory",
    "AttackConfig",
    "AttackResult",
    "Patch2DGenerationPlugin",
    "Patch2DConfig",
    "Patch2DResult",
    "Noise2DAttackPlugin",
    "GradientBasedNoise2DPlugin",
    "RandomNoise2DPlugin",
    "Noise2DConfig",
    "Noise2DResult",
]
