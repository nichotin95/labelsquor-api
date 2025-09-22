-- V4__squor_metrics_update.sql
-- Update SQUOR scoring system to new 5-component model

-- Clear existing policies
DELETE FROM policy_catalog WHERE scheme = 'squor_v1';

-- Insert new SQUOR v2 policies
INSERT INTO policy_catalog (policy_id, scheme, version, component_key, weight_default, params_json, effective_from) VALUES
-- S - SafetySquor: Ingredient & product safety (0-100)
(gen_random_uuid(), 'squor_v2', '2.0', 'safety', 20, 
 '{"description": "Ingredient & product safety", 
   "sub_metrics": ["toxicology_checks", "banned_ingredients", "allergen_thresholds", "usage_warnings"],
   "evidence_sources": ["FSSAI", "FDA", "BIS", "PubChem", "INCI"],
   "score_range": [0, 100]}'::jsonb, 
 NOW()),

-- Q - QualitySquor: Product & ingredient quality (0-100)
(gen_random_uuid(), 'squor_v2', '2.0', 'quality', 20,
 '{"description": "Product & ingredient quality",
   "sub_metrics": ["purity", "adulteration_risk", "freshness_indicators", "processing_levels"],
   "evidence_sources": ["Lab reports", "certifications", "Codex"],
   "score_range": [0, 100]}'::jsonb,
 NOW()),

-- U - UsabilitySquor: Consumer-friendliness (0-100)
(gen_random_uuid(), 'squor_v2', '2.0', 'usability', 20,
 '{"description": "Consumer-friendliness",
   "sub_metrics": ["label_readability", "allergen_visibility", "instructions_clarity", "serving_info"],
   "evidence_sources": ["FOPL norms", "WCAG for readability"],
   "score_range": [0, 100]}'::jsonb,
 NOW()),

-- O - OriginSquor: Provenance & traceability (0-100)
(gen_random_uuid(), 'squor_v2', '2.0', 'origin', 20,
 '{"description": "Provenance & traceability",
   "sub_metrics": ["country_of_origin", "organic_fairtrade_claims", "supplier_transparency"],
   "evidence_sources": ["GS1", "Fairtrade", "Organic India", "Brand docs"],
   "score_range": [0, 100]}'::jsonb,
 NOW()),

-- R - ResponsibilitySquor: Sustainability & ethics (0-100)
(gen_random_uuid(), 'squor_v2', '2.0', 'responsibility', 20,
 '{"description": "Sustainability & ethics",
   "sub_metrics": ["packaging_recyclability", "carbon_footprint", "ethical_sourcing", "compliance"],
   "evidence_sources": ["EPR norms", "sustainability frameworks"],
   "score_range": [0, 100]}'::jsonb,
 NOW());

-- Create view for current SQUOR policies
CREATE OR REPLACE VIEW vw_squor_current_policies AS
SELECT 
    component_key,
    weight_default as weight,
    params_json->>'description' as description,
    params_json->'sub_metrics' as sub_metrics,
    params_json->'evidence_sources' as evidence_sources,
    params_json->'score_range' as score_range
FROM policy_catalog
WHERE scheme = 'squor_v2'
AND effective_to IS NULL
ORDER BY component_key;

-- Comment on the new system
COMMENT ON VIEW vw_squor_current_policies IS 'Current SQUOR v2 scoring components: Safety, Quality, Usability, Origin, Responsibility';
