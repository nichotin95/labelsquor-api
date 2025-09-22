# Crawler Configuration Guide

This directory contains easy-to-edit configuration files for the LabelSquor crawler system.

## 📝 Configuration Files

### 1. `search_terms.yaml`
Contains all the search terms organized by priority and category.

**How to edit:**
- Simply add or remove items from the lists
- Higher priority numbers mean more frequent crawling
- No code changes needed!

**Example:**
```yaml
priority_brands:
  tier1:  # Crawled daily (Priority 9)
    - maggi
    - lays
    - your_new_brand_here  # Just add it!
```

### 2. `categories.yaml`
Maps our internal categories to retailer-specific URLs.

**Example:**
```yaml
categories:
  snacks:
    chips_crisps:
      display_name: "Chips & Crisps"
      retailers:
        bigbasket: "/pc/snacks/chips/"
        blinkit: "/c/chips/"
```

## 🚀 Quick Start

### View Current Configuration
```bash
# Show all search terms
python -m app.cli.crawler_commands show-search-terms

# Show category mappings
python -m app.cli.crawler_commands show-categories

# Show only BigBasket categories
python -m app.cli.crawler_commands show-categories --retailer bigbasket
```

### Add New Search Terms
```bash
# Add a new brand (will be added to tier3 by default)
python -m app.cli.crawler_commands add-search-term "new_brand"

# Add to specific tier
python -m app.cli.crawler_commands add-search-term "important_brand" --tier tier1
```

### Validate Configuration
```bash
# Check for errors or warnings
python -m app.cli.crawler_commands validate
```

### Reload Configuration
```bash
# Reload after making manual edits
python -m app.cli.crawler_commands reload
```

## 📊 Priority Levels

- **Priority 9** (Tier 1): Daily crawling - Top brands like Maggi, Lays
- **Priority 8** (Tier 2): Every 2 days - Important brands
- **Priority 7** (Tier 3): Twice weekly - Regular brands
- **Priority 6**: Weekly - Product categories
- **Priority 5**: Monthly - Low priority items

## ✏️ Manual Editing

You can directly edit the YAML files with any text editor:

1. Open `search_terms.yaml` or `categories.yaml`
2. Add/remove/modify entries
3. Save the file
4. Run `python -m app.cli.crawler_commands reload`

## 🎯 Best Practices

1. **Keep it organized**: Group similar items together
2. **Use lowercase**: For consistency in search terms
3. **Test after changes**: Run validate command
4. **Document additions**: Add comments for special cases

## 📈 Examples

### Adding a Festival Season
```yaml
trending_searches:
  current_month:
    - diwali special    # Added for Diwali
    - festive pack
    - gift hampers
```

### Adding Regional Products
```yaml
regional_products:
  your_region:
    - local_specialty_1
    - local_specialty_2
```

### Adding New Retailer
```yaml
categories:
  snacks:
    chips_crisps:
      retailers:
        bigbasket: "/existing/path/"
        new_retailer: "/new/path/"  # Just add this line!
```

## 🔄 How It Works

1. **On startup**: System reads these YAML files
2. **Creates tasks**: Based on priorities and schedules
3. **Crawls products**: Using the search terms and categories
4. **Updates database**: With discovered products

No code changes needed - just edit the YAML files!
