"""
Plugin registry for managing attack plugins.
"""
from typing import Dict, List, Optional, Type
from pathlib import Path
import importlib
import inspect
import logging

from .base import AttackPlugin, AttackCategory

logger = logging.getLogger(__name__)


class AttackPluginRegistry:
    """
    Registry for managing adversarial attack plugins.

    This class handles plugin discovery, registration, and retrieval.
    """

    def __init__(self):
        self._plugins: Dict[str, Type[AttackPlugin]] = {}
        self._instances: Dict[str, AttackPlugin] = {}

    def register(self, plugin_class: Type[AttackPlugin]) -> None:
        """
        Register an attack plugin.

        Args:
            plugin_class: Plugin class to register
        """
        if not issubclass(plugin_class, AttackPlugin):
            raise TypeError(f"{plugin_class} is not a subclass of AttackPlugin")

        # Create instance to get metadata
        instance = plugin_class()
        plugin_name = instance.name

        if plugin_name in self._plugins:
            logger.warning(f"Plugin '{plugin_name}' already registered. Overwriting.")

        self._plugins[plugin_name] = plugin_class
        self._instances[plugin_name] = instance

        logger.info(f"Registered attack plugin: {plugin_name} v{instance.version}")

    def unregister(self, plugin_name: str) -> None:
        """
        Unregister an attack plugin.

        Args:
            plugin_name: Name of plugin to unregister
        """
        if plugin_name in self._plugins:
            del self._plugins[plugin_name]
            del self._instances[plugin_name]
            logger.info(f"Unregistered attack plugin: {plugin_name}")

    def get_plugin(self, plugin_name: str) -> Optional[AttackPlugin]:
        """
        Get plugin instance by name.

        Args:
            plugin_name: Name of the plugin

        Returns:
            Plugin instance or None if not found
        """
        return self._instances.get(plugin_name)

    def get_plugin_class(self, plugin_name: str) -> Optional[Type[AttackPlugin]]:
        """
        Get plugin class by name.

        Args:
            plugin_name: Name of the plugin

        Returns:
            Plugin class or None if not found
        """
        return self._plugins.get(plugin_name)

    def list_plugins(
        self,
        category: Optional[AttackCategory] = None,
        requires_model: Optional[bool] = None
    ) -> List[Dict]:
        """
        List all registered plugins.

        Args:
            category: Filter by category
            requires_model: Filter by model requirement

        Returns:
            List of plugin info dicts
        """
        plugins = []

        for name, instance in self._instances.items():
            # Apply filters
            if category is not None and instance.category != category:
                continue

            if requires_model is not None and instance.requires_model != requires_model:
                continue

            plugins.append(instance.get_info())

        return plugins

    def discover_plugins(self, plugin_dir: Optional[Path] = None) -> int:
        """
        Discover and load plugins from a directory.

        Args:
            plugin_dir: Directory to search for plugins (default: app/plugins/attacks/)

        Returns:
            Number of plugins discovered
        """
        if plugin_dir is None:
            # Default plugin directory
            from pathlib import Path
            plugin_dir = Path(__file__).parent / "attacks"

        if not plugin_dir.exists():
            logger.warning(f"Plugin directory not found: {plugin_dir}")
            return 0

        discovered_count = 0

        # Search for Python files
        for py_file in plugin_dir.glob("*.py"):
            if py_file.name.startswith("_"):
                continue

            try:
                # Import module
                module_name = f"app.plugins.attacks.{py_file.stem}"
                module = importlib.import_module(module_name)

                # Find AttackPlugin subclasses
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if (issubclass(obj, AttackPlugin) and
                        obj is not AttackPlugin and
                        obj.__module__ == module_name):

                        self.register(obj)
                        discovered_count += 1

            except Exception as e:
                logger.error(f"Error loading plugin from {py_file}: {e}")

        logger.info(f"Discovered {discovered_count} attack plugins")
        return discovered_count

    def get_by_category(self, category: AttackCategory) -> List[AttackPlugin]:
        """
        Get all plugins in a category.

        Args:
            category: Attack category

        Returns:
            List of plugin instances
        """
        return [
            instance for instance in self._instances.values()
            if instance.category == category
        ]

    def validate_plugin_name(self, plugin_name: str) -> bool:
        """
        Check if a plugin name is valid/registered.

        Args:
            plugin_name: Plugin name to check

        Returns:
            True if plugin exists
        """
        return plugin_name in self._plugins

    def __contains__(self, plugin_name: str) -> bool:
        """Check if plugin is registered."""
        return plugin_name in self._plugins

    def __len__(self) -> int:
        """Get number of registered plugins."""
        return len(self._plugins)

    def __repr__(self) -> str:
        """String representation."""
        return f"<AttackPluginRegistry: {len(self)} plugins>"


# Global registry instance
attack_plugin_registry = AttackPluginRegistry()
