# LabelSquor • Data Store Design (v1.0 – canonical)

> Purpose: A maintainable + scalable canonical store for products, brands, sources, extracted facts, and Squor—
with refresh/versioning, search, and analytics.

---

## 0) High-level Architecture

**OLTP (System of Record)**
- PostgreSQL (Supabase-ready) with strict constraints and unique indexes for dedupe.
- SCD Type-2 versioned facts for point-in-time views.

**Blob & Artifact Storage**
- Object storage for images, raw HTML, OCR/LLM artifacts. Content-addressed keys (SHA-256).

**Search & Discovery**
- OpenSearch/Elasticsearch for keyword facets + pgvector for semantic search (ingredients/claims).

**Streaming & Jobs**
- Kafka (or Cloud Pub/Sub) for ingestion, OCR, LLM-enrichment, scoring, and refresh.

**Warehouse/BI**
- BigQuery/Redshift/Snowflake via CDC (Debezium). dbt for modeling; Metabase/Looker for dashboards.

**Feature Store (optional)**
- Redis/Feast for low-latency features (freshness signals, rolling metrics).

---

## 1) ER Overview (key relationships)

```
Brand 1—* Product (*variants) 1—* SourcePage (PDPs)
                      |\ 
                      | \* ProductImage
                      |                        |   * ExtractedFact (ingredients, nutrition, allergens, claims)
                      |   * Certification / Label
                      |   * Identifier (GTIN/ASIN/SKU)
                      |   * ProductVersion (canonical snapshot)
                      |   * SquorScore 1—* SquorComponent
                      |   * Issue / DataQualityFinding
                      * RefreshRequest 1—* ProcessingJob (*JobRun)
```

---

## 2) IDs & Versioning
- `brand_id`, `product_id`: UUIDv7/ULID (stable).
- `product_version_id`: immutable snapshot per pipeline run; all facts tie to a version.
- Dedup: `canonical_key` (normalized brand + product + pack + GTIN) unique for active products.
- SCD2: facts carry `valid_from`, `valid_to`, `is_current`.

---

## 3) Logical Schema (selected tables)

### 3.1 Identity
- `brand` (PK `brand_id`) — normalized name, owner_company, country.
- `product` (PK `product_id`) — `brand_id`, `canonical_key` (unique), normalized name, pack/unit, `gtin_primary`, status.
- `product_identifier` — type (GTIN/ASIN/SKU/MPN), value, confidence.

### 3.2 Sources & Artifacts
- `source_page` — retailer URL, crawls, HTML object key, fingerprints.
- `product_image` — role (front/back/ingredients/nutrition), object key, hash, OCR status.
- `artifact` — OCR/LLM input-output blobs with hashes.

### 3.3 Versioned Canonical Snapshot
- `product_version` — immutable, references `job_run`.
- `ingredients_v`, `nutrition_v`, `allergens_v`, `claims_v`, `certifications_v` — SCD2 tables with confidence + raw/canonical JSON.

### 3.4 Scoring (Squor)
- `squor_score` — `scheme`, `score`, `grade`, `score_json`, `computed_at`.
- `squor_component` — per component weight/value/contribution + explainability.
- `policy_catalog` — rules/weights per scheme version (so we can re-score without re-OCR).

### 3.5 Ops & Refresh
- `refresh_request` — reason/priority/status, links to `job_run`.
- `job`, `job_run` — pipeline stages, metrics, logs.
- `issue` — data quality & exception handling.

### 3.6 Search & Embeddings
- `embedding` — pgvector on products/claims/ingredient spans.

---

## 4) Ingestion → Canonicalization Flow
1. Scrape PDPs → `source_page` (store HTML; hash & fingerprint).
2. Link or create `product` + `brand` with normalization & dedupe.
3. Pull images; OCR → `artifact` (ocr_text/json).
4. LLM extract (Google AI Studio) → structured facts (provisional).
5. Normalize + conflict resolution → freeze `product_version`; write SCD2 facts.
6. Compute Squor using `policy_catalog`; write `squor_score` + `squor_component`.
7. Publish to search; emit CDC to warehouse.

---

## 5) Refresh Semantics
- Triggers: manual, SLA freshness, PDP diff, or policy update.
- Idempotency: stage keyed by (`product_id`, `source_page_id`, `content_hash`). Skip if unchanged.
- Minimal recompute: policy changes re-score from latest version only.
- Traceability: each version references `job_run_id`; artifacts carry content hashes.

---

## 6) Data Quality & Governance
- Normalization rules: name/brand casing, unit normalization; GTIN checksum; allergen vocab.
- Conflict resolution: confidence × recency × retailer reliability.
- Retention: keep all `product_version` rows; move old OCR artifacts to cold storage (keep hashes).

---

## 7) Scalability & Maintainability
- Partition heavy append tables (job_run, source_page, artifacts by month).
- Partial indexes on `is_current` for SCD2 tables.
- Flyway migrations; stable views `vw_product_current`, `vw_product_history`, `vw_squor_public`.
- Observability: job_run.metrics, Prometheus; data tests via dbt/Great Expectations.

---

## 8) Public/Partner Views
- `vw_product_current` — latest canonical facts.
- `vw_product_history` — version timeline & deltas.
- `vw_squor_public` — score/grade/top drivers only.

---

## 9) Product Category System (Taxonomy)

**Goals**
- Global hierarchical taxonomy with regional overlays (IN/EU/US) and synonyms.
- Drives browse, attribute expectations, Squor policy nuances, and analytics rollups.

**Tables**
- `category` (hierarchical; optional `ltree path`)
- `category_synonym` (aka labels, retailer terms)
- `category_region` (regional display/availability)
- `product_category_map` (many-to-many; one primary via `is_primary`)
- `category_attribute_schema` (expected attributes per category)
- `category_policy_override` (Squor weight/params by category)
- `category_version` (SCD2 for taxonomy changes)

**Classification Flow**
- Heuristics (title, breadcrumbs, retailer taxonomy) → candidate set
- Embedding classifier ranking → `product_category_map` with confidence
- Human-in-the-loop for low-confidence
- Taxonomy edits trigger reclassification (emit `refresh_request` with reason `taxonomy_update`).

---

## 10) API Contracts (selected)

**Products**
- `GET /products/{id}` (current view)
- `GET /products/{id}/versions` (history)
- `POST /products/{id}/refresh` (enqueue refresh)

**Search**
- `GET /search?q=&category_id=&include_descendants=true&allergens=!peanut`

**Categories**
- `GET /categories?parent_id=` (children)
- `GET /categories/{id}/tree` (subtree)
- `PUT /products/{id}/categories` (mapping; enforce single primary)

**Scores**
- `GET /products/{id}/squor` (current score/components)
- `POST /scores/recompute?scheme=LabelSquor_v1` (policy-only recompute)

---

## 11) Definition of Done (v1)
- Migrations applied (core + categories).
- Pipelines writing `product_version` + SCD2 facts.
- Squor v1 (policy_catalog-backed) + recompute path.
- Refresh endpoint idempotent + audited.
- Two dashboards: ingest health; score distribution.

---

## 12) Brand Notes (UI/Docs)
- Fonts: Outfit (H1/logos), DM Sans (UI subheads), Inter (body), Space Grotesk (numbers).

