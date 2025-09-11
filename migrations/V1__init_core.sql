-- V1__init_core.sql
-- Core entities, sources, versions, facts (ingredients example), scores (Squor), ops, embeddings.

-- 1) Brand
create table if not exists brand (
  brand_id uuid primary key,
  name text not null,
  normalized_name text not null,
  owner_company text,
  country text,
  www text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);
create unique index if not exists ux_brand_norm on brand(normalized_name, coalesce(country,''));

-- 2) Product
create table if not exists product (
  product_id uuid primary key,
  brand_id uuid references brand(brand_id),
  canonical_key text not null,
  name text not null,
  normalized_name text not null,
  category text,
  subcategory text,
  pack_size numeric,
  unit text,
  gtin_primary text,
  status text default 'active',
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);
create unique index if not exists ux_product_canon on product(canonical_key) where status='active';
create index if not exists ix_product_brand on product(brand_id);

-- 3) Identifiers
create table if not exists product_identifier (
  product_identifier_id uuid primary key,
  product_id uuid not null references product(product_id),
  type text not null,
  value text not null,
  confidence numeric,
  source text,
  created_at timestamptz default now(),
  unique(product_id, type, value)
);

-- 4) Source pages
create table if not exists source_page (
  source_page_id uuid primary key,
  product_id uuid references product(product_id),
  retailer text not null,
  url text not null,
  crawl_batch_id text,
  html_object_key text,
  status_code int,
  fingerprint_sha256 text,
  first_seen_at timestamptz,
  last_seen_at timestamptz,
  unique(retailer, url)
);

-- 5) Product images
create table if not exists product_image (
  product_image_id uuid primary key,
  product_id uuid references product(product_id),
  source_page_id uuid references source_page(source_page_id),
  role text,
  object_key text,
  width int,
  height int,
  hash_sha256 text,
  ocr_status text,
  created_at timestamptz default now(),
  unique(product_id, hash_sha256)
);

-- 6) Artifacts
create table if not exists artifact (
  artifact_id uuid primary key,
  kind text not null,
  object_key text not null,
  content_hash text not null,
  mime text,
  bytes bigint,
  created_at timestamptz default now()
);

-- 7) Product version (immutable snapshot)
create table if not exists product_version (
  product_version_id uuid primary key,
  product_id uuid not null references product(product_id),
  derived_from_job_run_id uuid,
  version_seq bigint not null,
  created_at timestamptz default now(),
  unique(product_id, version_seq)
);

-- 8) Ingredients_v (SCD2 example)
create table if not exists ingredients_v (
  ingredients_id uuid primary key,
  product_version_id uuid not null references product_version(product_version_id),
  raw_text text,
  normalized_list_json jsonb,
  tree_json jsonb,
  confidence numeric,
  valid_from timestamptz not null default now(),
  valid_to timestamptz,
  is_current boolean not null default true
);
create index if not exists ix_ing_cur on ingredients_v(product_version_id) where is_current;

-- 9) Nutrition_v (SCD2)
create table if not exists nutrition_v (
  nutrition_id uuid primary key,
  product_version_id uuid not null references product_version(product_version_id),
  panel_raw_text text,
  per_100g_json jsonb,
  per_serving_json jsonb,
  serving_size text,
  confidence numeric,
  valid_from timestamptz not null default now(),
  valid_to timestamptz,
  is_current boolean not null default true
);
create index if not exists ix_nut_cur on nutrition_v(product_version_id) where is_current;

-- 10) Allergens_v (SCD2)
create table if not exists allergens_v (
  allergens_id uuid primary key,
  product_version_id uuid not null references product_version(product_version_id),
  declared_list jsonb,
  may_contain_list jsonb,
  contains_list jsonb,
  confidence numeric,
  valid_from timestamptz not null default now(),
  valid_to timestamptz,
  is_current boolean not null default true
);
create index if not exists ix_all_cur on allergens_v(product_version_id) where is_current;

-- 11) Claims_v (SCD2)
create table if not exists claims_v (
  claims_id uuid primary key,
  product_version_id uuid not null references product_version(product_version_id),
  claims_json jsonb,
  source text,
  confidence numeric,
  valid_from timestamptz not null default now(),
  valid_to timestamptz,
  is_current boolean not null default true
);
create index if not exists ix_clm_cur on claims_v(product_version_id) where is_current;

-- 12) Certifications_v (SCD2)
create table if not exists certifications_v (
  cert_id uuid primary key,
  product_version_id uuid not null references product_version(product_version_id),
  scheme text,
  id_code text,
  issuer text,
  valid_from_label text,
  valid_to_label text,
  evidence_artifact_id uuid references artifact(artifact_id),
  valid_from timestamptz not null default now(),
  valid_to timestamptz,
  is_current boolean not null default true
);
create index if not exists ix_cert_cur on certifications_v(product_version_id) where is_current;

-- 13) Squor
create table if not exists squor_score (
  squor_id uuid primary key,
  product_version_id uuid not null references product_version(product_version_id),
  scheme text not null,
  score numeric not null,
  grade text,
  score_json jsonb,
  computed_at timestamptz default now(),
  unique(product_version_id, scheme)
);
create table if not exists squor_component (
  squor_component_id uuid primary key,
  squor_id uuid not null references squor_score(squor_id),
  component_key text not null,
  weight numeric,
  value numeric,
  contribution numeric,
  explain_md text
);

create table if not exists policy_catalog (
  policy_id uuid primary key,
  scheme text not null,
  version text not null,
  component_key text not null,
  weight_default numeric,
  params_json jsonb,
  effective_from timestamptz,
  effective_to timestamptz
);

-- 14) Ops
create table if not exists job (
  job_id uuid primary key,
  name text not null,
  is_active boolean default true
);
create table if not exists job_run (
  job_run_id uuid primary key,
  job_id uuid references job(job_id),
  product_id uuid references product(product_id),
  source_page_id uuid references source_page(source_page_id),
  status text,
  attempt int default 1,
  started_at timestamptz default now(),
  finished_at timestamptz,
  logs_object_key text,
  metrics_json jsonb
);

create table if not exists refresh_request (
  refresh_request_id uuid primary key,
  product_id uuid not null references product(product_id),
  reason text,
  requested_by text,
  priority text,
  status text,
  created_at timestamptz default now(),
  completed_at timestamptz,
  job_run_id uuid references job_run(job_run_id)
);

create table if not exists issue (
  issue_id uuid primary key,
  entity_type text not null,
  entity_id uuid not null,
  severity text,
  code text,
  details_json jsonb,
  opened_at timestamptz default now(),
  resolved_at timestamptz
);

-- 15) Embeddings
create table if not exists embedding (
  embedding_id uuid primary key,
  entity_type text not null,
  entity_id uuid not null,
  model text not null,
  dim int not null,
  vector vector(1536),
  created_at timestamptz default now()
);
