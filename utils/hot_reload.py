"""Hot reload system for Discord bot development."""

import asyncio
import logging
import os
from pathlib import Path
from typing import Set, Dict, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent

logger = logging.getLogger(__name__)


class CogReloader(FileSystemEventHandler):
    """Handles automatic cog reloading on file changes."""
    
    def __init__(self, bot):
        self.bot = bot
        self.cog_path = Path("cogs")
        self.reloading = set()
        self.reload_lock = asyncio.Lock()
        
    def on_modified(self, event):
        """Handle file modification events."""
        if event.is_directory or not event.src_path.endswith('.py'):
            return
            
        path = Path(event.src_path)
        if self.cog_path in path.parents:
            asyncio.create_task(self._reload_cog(path))
    
    async def _reload_cog(self, path: Path):
        """Reload a specific cog."""
        # Convert path to module name
        parts = path.relative_to(Path.cwd()).parts
        module_name = '.'.join(parts)[:-3]  # Remove .py
        
        # Skip if already reloading
        if module_name in self.reloading:
            return
            
        async with self.reload_lock:
            self.reloading.add(module_name)
            try:
                # Try to reload
                if module_name in self.bot.extensions:
                    await self.bot.reload_extension(module_name)
                    logger.info(f"✅ Reloaded: {module_name}")
                else:
                    # Try to load if not loaded
                    await self.bot.load_extension(module_name)
                    logger.info(f"✅ Loaded new: {module_name}")
                    
            except Exception as e:
                logger.error(f"❌ Failed to reload {module_name}: {e}")
            finally:
                self.reloading.discard(module_name)


class HotReloadManager:
    """Manages hot reload functionality."""
    
    def __init__(self, bot):
        self.bot = bot
        self.observer = Observer()
        self.handler = CogReloader(bot)
        
    def start(self):
        """Start watching for file changes."""
        self.observer.schedule(
            self.handler,
            path='cogs',
            recursive=True
        )
        self.observer.start()
        logger.info("🔥 Hot reload enabled - watching cogs/")
        
    def stop(self):
        """Stop watching for file changes."""
        self.observer.stop()
        self.observer.join()
        logger.info("Hot reload stopped")


async def setup_hot_reload(bot):
    """Setup hot reload for the bot."""
    if os.getenv('HOT_RELOAD', 'false').lower() == 'true':
        manager = HotReloadManager(bot)
        manager.start()
        bot.hot_reload_manager = manager
        return manager
    return None