-- V2__categories.sql
-- Category taxonomy, synonyms, mapping, attribute schemas, policy overrides, versions.

create table if not exists category (
  category_id uuid primary key,
  parent_id uuid references category(category_id),
  slug text not null,
  name text not null,
  locale text default 'en',
  rank int default 0,
  is_active boolean default true,
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  unique(slug, locale)
);
create index if not exists ix_category_parent on category(parent_id);

create table if not exists category_synonym (
  category_synonym_id uuid primary key,
  category_id uuid not null references category(category_id),
  term text not null,
  locale text default 'en',
  source text,
  confidence numeric
);

create table if not exists product_category_map (
  product_id uuid not null references product(product_id),
  category_id uuid not null references category(category_id),
  is_primary boolean default false,
  confidence numeric,
  assigned_by text,
  created_at timestamptz default now(),
  primary key (product_id, category_id)
);
create unique index if not exists ux_pcm_primary on product_category_map(product_id) where is_primary;

create table if not exists category_attribute_schema (
  schema_id uuid primary key,
  category_id uuid not null references category(category_id),
  attribute_key text not null,
  type text not null,
  required boolean default false,
  validation_json jsonb,
  ui_facet boolean default false
);

create table if not exists category_policy_override (
  override_id uuid primary key,
  category_id uuid not null references category(category_id),
  scheme text not null,
  component_key text not null,
  weight_override numeric,
  params_override_json jsonb,
  effective_from timestamptz not null,
  effective_to timestamptz
);

create table if not exists category_version (
  category_version_id uuid primary key,
  category_id uuid not null references category(category_id),
  name text not null,
  parent_id uuid,
  valid_from timestamptz not null default now(),
  valid_to timestamptz,
  is_current boolean default true
);
