#!/usr/bin/env python3
"""
Database migration management script
"""

import argparse
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from alembic import command
from alembic.config import Config

from app.core.config import settings
from app.core.logging import log


def get_alembic_config() -> Config:
    """Get Alembic configuration"""
    config_path = Path(__file__).parent.parent / "alembic.ini"
    config = Config(str(config_path))
    
    # Override database URL from settings
    config.set_main_option("sqlalchemy.url", str(settings.database_url))
    
    return config


def init_alembic():
    """Initialize Alembic for the first time"""
    config = get_alembic_config()
    command.init(config, "alembic")
    log.info("Alembic initialized successfully")


def create_migration(message: str):
    """Create a new migration"""
    config = get_alembic_config()
    command.revision(config, message=message, autogenerate=True)
    log.info(f"Created new migration: {message}")


def upgrade_database(revision: str = "head"):
    """Upgrade database to a revision"""
    config = get_alembic_config()
    command.upgrade(config, revision)
    log.info(f"Database upgraded to {revision}")


def downgrade_database(revision: str = "-1"):
    """Downgrade database by one revision"""
    config = get_alembic_config()
    command.downgrade(config, revision)
    log.info(f"Database downgraded to {revision}")


def show_current_revision():
    """Show current database revision"""
    config = get_alembic_config()
    command.current(config)


def show_history():
    """Show migration history"""
    config = get_alembic_config()
    command.history(config)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Database migration management")
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Init command
    subparsers.add_parser("init", help="Initialize Alembic")
    
    # Create migration command
    create_parser = subparsers.add_parser("create", help="Create a new migration")
    create_parser.add_argument("message", help="Migration message")
    
    # Upgrade command
    upgrade_parser = subparsers.add_parser("upgrade", help="Upgrade database")
    upgrade_parser.add_argument("revision", nargs="?", default="head", help="Target revision (default: head)")
    
    # Downgrade command
    downgrade_parser = subparsers.add_parser("downgrade", help="Downgrade database")
    downgrade_parser.add_argument("revision", nargs="?", default="-1", help="Target revision (default: -1)")
    
    # Current command
    subparsers.add_parser("current", help="Show current revision")
    
    # History command
    subparsers.add_parser("history", help="Show migration history")
    
    args = parser.parse_args()
    
    if args.command == "init":
        init_alembic()
    elif args.command == "create":
        create_migration(args.message)
    elif args.command == "upgrade":
        upgrade_database(args.revision)
    elif args.command == "downgrade":
        downgrade_database(args.revision)
    elif args.command == "current":
        show_current_revision()
    elif args.command == "history":
        show_history()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
