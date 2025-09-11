# API Contracts (v1)

## Products
- `GET /products/{id}` → current canonical view
- `GET /products/{id}/versions` → list versions
- `POST /products/{id}/refresh` → enqueue refresh `{ reason, priority }`

## Search
- `GET /search?q=&category_id=&include_descendants=true` → keyword + category filter
- Optional params: `allergens`, `claims`, `min_score`, `max_score`

## Categories
- `GET /categories?parent_id=` → children
- `GET /categories/{id}/tree` → subtree
- `PUT /products/{id}/categories` → upsert mapping `{ category_id, is_primary }`

## Scores
- `GET /products/{id}/squor` → latest score + components
- `POST /scores/recompute?scheme=LabelSquor_v1` → policy-only recompute across products
