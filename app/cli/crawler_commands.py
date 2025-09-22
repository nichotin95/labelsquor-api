"""
CLI commands for managing crawler configuration
"""

from pathlib import Path

import typer
import yaml
from rich.console import Console
from rich.table import Table
from rich.tree import Tree

from app.core.crawler_config import crawler_config

app = typer.Typer(help="Crawler configuration management")
console = Console()


@app.command()
def show_search_terms(category: str = typer.Option(None, help="Filter by category (brand, product, health)")):
    """Show all configured search terms"""
    config = crawler_config.load_search_terms()

    table = Table(title="Search Terms Configuration")
    table.add_column("Category", style="cyan")
    table.add_column("Terms", style="green")
    table.add_column("Priority", style="yellow")

    # Priority brands
    if not category or category == "brand":
        brands = config.get("priority_brands", {})
        for tier, brand_list in brands.items():
            priority = {"tier1": "9", "tier2": "8", "tier3": "7"}.get(tier, "5")
            table.add_row(
                f"Brands ({tier})", ", ".join(brand_list[:5]) + ("..." if len(brand_list) > 5 else ""), priority
            )

    # Product categories
    if not category or category == "product":
        products = config.get("product_categories", {})
        for cat_name, terms in products.items():
            table.add_row(f"Products ({cat_name})", ", ".join(terms[:5]) + ("..." if len(terms) > 5 else ""), "6")

    # Health keywords
    if not category or category == "health":
        health = config.get("health_keywords", {})
        for health_cat, keywords in health.items():
            table.add_row(f"Health ({health_cat})", ", ".join(keywords[:3]) + ("..." if len(keywords) > 3 else ""), "7")

    console.print(table)


@app.command()
def show_categories(retailer: str = typer.Option(None, help="Show mappings for specific retailer")):
    """Show category mappings"""
    config = crawler_config.load_categories()
    categories = config.get("categories", {})

    tree = Tree("📂 Categories")

    for main_cat, sub_cats in categories.items():
        main_branch = tree.add(f"📁 {main_cat}")

        for sub_cat_key, sub_cat_data in sub_cats.items():
            display_name = sub_cat_data.get("display_name", sub_cat_key)
            sub_branch = main_branch.add(f"📄 {display_name}")

            # Show keywords
            keywords = sub_cat_data.get("keywords", [])
            if keywords:
                sub_branch.add(f"🔍 Keywords: {', '.join(keywords[:3])}")

            # Show retailer mappings
            retailers = sub_cat_data.get("retailers", {})
            if retailer:
                # Show specific retailer
                if retailer in retailers:
                    sub_branch.add(f"🛒 {retailer}: {retailers[retailer]}")
            else:
                # Show all retailers
                for ret, path in retailers.items():
                    sub_branch.add(f"🛒 {ret}: {path}")

    console.print(tree)


@app.command()
def add_search_term(
    term: str = typer.Argument(..., help="Search term to add"),
    category: str = typer.Option("brand", help="Category: brand, product, health"),
    tier: str = typer.Option("tier3", help="Priority tier: tier1, tier2, tier3"),
):
    """Add a new search term to configuration"""
    config_file = Path("configs/crawler/search_terms.yaml")

    # Load existing config
    with open(config_file, "r") as f:
        config = yaml.safe_load(f)

    # Add term based on category
    if category == "brand":
        if tier not in config["priority_brands"]:
            config["priority_brands"][tier] = []

        if term not in config["priority_brands"][tier]:
            config["priority_brands"][tier].append(term)
            console.print(f"✅ Added '{term}' to {tier} brands", style="green")
        else:
            console.print(f"⚠️  '{term}' already exists in {tier}", style="yellow")

    # Save updated config
    with open(config_file, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    # Reload config
    crawler_config.reload_configs()


@app.command()
def reload():
    """Reload all crawler configurations"""
    crawler_config.reload_configs()
    console.print("✅ Configurations reloaded successfully!", style="green")

    # Show summary
    terms = crawler_config.get_all_search_terms_with_priority()
    console.print(f"\n📊 Total search terms: {len(terms)}")

    # Count by category
    by_category = {}
    for term in terms:
        cat = term["category"]
        by_category[cat] = by_category.get(cat, 0) + 1

    for cat, count in by_category.items():
        console.print(f"  • {cat}: {count} terms")


@app.command()
def validate():
    """Validate configuration files"""
    errors = []
    warnings = []

    # Check search terms
    try:
        search_config = crawler_config.load_search_terms()
        if not search_config.get("priority_brands"):
            warnings.append("No priority brands configured")
    except Exception as e:
        errors.append(f"Error loading search_terms.yaml: {e}")

    # Check categories
    try:
        cat_config = crawler_config.load_categories()
        categories = cat_config.get("categories", {})

        # Check for missing retailer mappings
        for main_cat, sub_cats in categories.items():
            for sub_cat_key, sub_cat_data in sub_cats.items():
                retailers = sub_cat_data.get("retailers", {})
                if not retailers:
                    warnings.append(f"No retailer mappings for {main_cat}/{sub_cat_key}")

                # Check for inconsistent retailers
                expected_retailers = {"bigbasket", "blinkit", "zepto"}
                missing = expected_retailers - set(retailers.keys())
                if missing:
                    warnings.append(f"Missing retailers for {main_cat}/{sub_cat_key}: {missing}")

    except Exception as e:
        errors.append(f"Error loading categories.yaml: {e}")

    # Display results
    if errors:
        console.print("\n❌ Errors found:", style="red")
        for error in errors:
            console.print(f"  • {error}")

    if warnings:
        console.print("\n⚠️  Warnings:", style="yellow")
        for warning in warnings:
            console.print(f"  • {warning}")

    if not errors and not warnings:
        console.print("✅ All configurations are valid!", style="green")

    return len(errors) == 0  # Return True if no errors


if __name__ == "__main__":
    app()
