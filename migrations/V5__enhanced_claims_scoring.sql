-- V5: Enhanced claims and scoring explanations
-- Add structured claims analysis and SQUOR component explanations

-- 1) Enhanced claims structure with classification
CREATE TABLE IF NOT EXISTS claim_analysis (
    claim_analysis_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_version_id UUID NOT NULL REFERENCES product_version(product_version_id),
    
    -- Claims categorization
    good_claims JSONB DEFAULT '[]',  -- Array of {claim: text, evidence: text, confidence: 0-1}
    bad_claims JSONB DEFAULT '[]',   -- Array of {claim: text, issue: text, severity: low/medium/high}
    misleading_claims JSONB DEFAULT '[]', -- Array of {claim: text, truth: text, explanation: text}
    
    -- Overall assessment
    claims_summary TEXT,
    red_flags TEXT[],  -- Major concerns
    green_flags TEXT[], -- Positive highlights
    
    -- Metadata
    analyzed_at TIMESTAMPTZ DEFAULT NOW(),
    analyzer_version TEXT DEFAULT 'v1',
    confidence_score NUMERIC(3,2), -- 0.00-1.00
    
    UNIQUE(product_version_id)
);

-- 2) Enhanced SQUOR component explanations  
-- Modify squor_component to ensure we capture reasoning
ALTER TABLE squor_component 
ADD COLUMN IF NOT EXISTS factors JSONB DEFAULT '{}',  -- Detailed factors that influenced the score
ADD COLUMN IF NOT EXISTS reasoning TEXT, -- One-liner explanation for the score
ADD COLUMN IF NOT EXISTS evidence JSONB DEFAULT '{}'; -- Supporting evidence/data points

-- 3) Create a view for easy access to complete product analysis
CREATE OR REPLACE VIEW product_analysis_complete AS
SELECT 
    p.product_id,
    p.name AS product_name,
    b.name AS brand_name,
    pv.product_version_id,
    pv.version_seq,
    
    -- SQUOR scores with explanations
    ss.score AS overall_squor,
    ss.grade AS squor_grade,
    
    -- Individual SQUOR components with reasoning
    (SELECT jsonb_object_agg(
        sc.component_key, 
        jsonb_build_object(
            'score', sc.value,
            'weight', sc.weight,
            'reasoning', sc.reasoning,
            'factors', sc.factors,
            'explanation', sc.explain_md
        )
    ) FROM squor_component sc WHERE sc.squor_id = ss.squor_id) AS squor_breakdown,
    
    -- Claims analysis
    ca.good_claims,
    ca.bad_claims,
    ca.misleading_claims,
    ca.red_flags,
    ca.green_flags,
    ca.claims_summary,
    
    -- Nutrition info (extracted from JSONB)
    (nv.per_100g_json->>'energy_kcal')::numeric AS energy_kcal,
    (nv.per_100g_json->>'protein_g')::numeric AS protein_g,
    (nv.per_100g_json->>'carbohydrate_g')::numeric AS carbohydrate_g,
    (nv.per_100g_json->>'fat_g')::numeric AS fat_g,
    (nv.per_100g_json->>'sodium_mg')::numeric AS sodium_mg,
    
    -- Ingredients (from JSONB)
    iv.normalized_list_json AS ingredients,
    
    -- Timestamps
    pv.created_at AS version_created,
    ss.computed_at AS score_computed,
    ca.analyzed_at AS claims_analyzed
    
FROM product p
JOIN brand b ON p.brand_id = b.brand_id
JOIN product_version pv ON p.product_id = pv.product_id
LEFT JOIN squor_score ss ON pv.product_version_id = ss.product_version_id AND ss.scheme = 'SQUOR_V2'
LEFT JOIN claim_analysis ca ON pv.product_version_id = ca.product_version_id
LEFT JOIN nutrition_v nv ON pv.product_version_id = nv.product_version_id AND nv.is_current = true
LEFT JOIN ingredients_v iv ON pv.product_version_id = iv.product_version_id AND iv.is_current = true;

-- 4) Index for performance
CREATE INDEX idx_claim_analysis_product_version ON claim_analysis(product_version_id);
CREATE INDEX idx_claim_analysis_analyzed_at ON claim_analysis(analyzed_at DESC);

-- 5) Update existing claims_v table structure to be compatible
-- Store raw claims separately from analyzed claims
COMMENT ON TABLE claims_v IS 'Raw claims extracted from product labels/descriptions';
COMMENT ON TABLE claim_analysis IS 'AI-analyzed and categorized claims with validation';

-- 6) Helper function to get claim summary
CREATE OR REPLACE FUNCTION get_claim_summary(p_product_version_id UUID)
RETURNS JSONB AS $$
DECLARE
    result JSONB;
BEGIN
    SELECT jsonb_build_object(
        'total_claims', 
            COALESCE(jsonb_array_length(good_claims), 0) + 
            COALESCE(jsonb_array_length(bad_claims), 0) + 
            COALESCE(jsonb_array_length(misleading_claims), 0),
        'good_count', COALESCE(jsonb_array_length(good_claims), 0),
        'bad_count', COALESCE(jsonb_array_length(bad_claims), 0),
        'misleading_count', COALESCE(jsonb_array_length(misleading_claims), 0),
        'has_red_flags', COALESCE(array_length(red_flags, 1), 0) > 0,
        'red_flag_count', COALESCE(array_length(red_flags, 1), 0),
        'green_flag_count', COALESCE(array_length(green_flags, 1), 0)
    ) INTO result
    FROM claim_analysis
    WHERE product_version_id = p_product_version_id;
    
    RETURN COALESCE(result, '{}'::jsonb);
END;
$$ LANGUAGE plpgsql;
