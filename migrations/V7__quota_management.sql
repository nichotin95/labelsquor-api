-- V7__quota_management.sql
-- Add quota tracking and management tables

-- Table for tracking quota usage over time
CREATE TABLE IF NOT EXISTS quota_usage_log (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID REFERENCES processing_queue(queue_id),
    service_name VARCHAR(50) NOT NULL DEFAULT 'gemini',
    usage_data JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Indexes
    INDEX idx_quota_usage_workflow (workflow_id),
    INDEX idx_quota_usage_service (service_name),
    INDEX idx_quota_usage_created (created_at DESC)
);

-- Add new workflow states to processing_queue
ALTER TABLE processing_queue 
ADD COLUMN IF NOT EXISTS partial_results JSONB DEFAULT '{}',
ADD COLUMN IF NOT EXISTS quota_exceeded_count INT DEFAULT 0,
ADD COLUMN IF NOT EXISTS last_quota_check TIMESTAMPTZ;

-- Update workflow state enum (if using enum, otherwise just document valid values)
-- Valid workflow_state values now include:
-- 'created', 'queued', 'processing', 'waiting', 'completed', 'failed', 
-- 'cancelled', 'retrying', 'suspended', 'quota_exceeded', 'partially_processed'

-- Table for quota limit configurations (override defaults)
CREATE TABLE IF NOT EXISTS quota_limits (
    limit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_name VARCHAR(50) NOT NULL,
    quota_type VARCHAR(50) NOT NULL,
    limit_value INT NOT NULL,
    window_seconds INT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Unique constraint
    UNIQUE(service_name, quota_type),
    
    -- Indexes
    INDEX idx_quota_limits_service (service_name) WHERE is_active
);

-- Insert default Gemini limits
INSERT INTO quota_limits (service_name, quota_type, limit_value, window_seconds) VALUES
('gemini', 'tokens_per_minute', 4000000, 60),
('gemini', 'tokens_per_day', 1000000000, 86400),
('gemini', 'requests_per_minute', 15, 60),
('gemini', 'requests_per_day', 1500, 86400)
ON CONFLICT (service_name, quota_type) DO NOTHING;

-- View for current quota usage
CREATE OR REPLACE VIEW vw_quota_usage_current AS
WITH latest_usage AS (
    SELECT 
        service_name,
        (usage_data->>'quotas')::jsonb as quotas,
        (usage_data->>'cost_tracking')::jsonb as cost_tracking,
        created_at,
        ROW_NUMBER() OVER (PARTITION BY service_name ORDER BY created_at DESC) as rn
    FROM quota_usage_log
    WHERE created_at >= NOW() - INTERVAL '24 hours'
)
SELECT 
    service_name,
    quotas,
    cost_tracking,
    created_at as last_updated
FROM latest_usage
WHERE rn = 1;

-- View for quota exceeded workflows
CREATE OR REPLACE VIEW vw_quota_exceeded_workflows AS
SELECT 
    pq.queue_id,
    pq.product_id,
    pq.workflow_state,
    pq.stage,
    pq.quota_exceeded_count,
    pq.next_retry_at,
    pq.stage_details->>'quota_exceeded_at' as quota_exceeded_at,
    pq.stage_details->>'estimated_wait_seconds' as wait_seconds,
    pq.partial_results->>'progress_percentage' as progress_percentage,
    p.name as product_name,
    b.name as brand_name
FROM processing_queue pq
LEFT JOIN product p ON pq.product_id = p.product_id
LEFT JOIN brand b ON p.brand_id = b.brand_id
WHERE pq.workflow_state IN ('quota_exceeded', 'partially_processed')
ORDER BY pq.priority DESC, pq.queued_at;

-- Function to get quota usage summary
CREATE OR REPLACE FUNCTION get_quota_usage_summary(
    p_service_name VARCHAR(50) DEFAULT 'gemini',
    p_time_range INTERVAL DEFAULT '24 hours'
) RETURNS TABLE (
    hour TIMESTAMPTZ,
    requests INT,
    total_tokens BIGINT,
    total_cost NUMERIC,
    avg_tokens_per_request NUMERIC,
    quota_exceeded_count INT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        DATE_TRUNC('hour', created_at) as hour,
        COUNT(*)::INT as requests,
        SUM((usage_data->'cost_tracking'->>'total_tokens')::BIGINT) as total_tokens,
        SUM((usage_data->'cost_tracking'->>'total_cost_usd')::NUMERIC) as total_cost,
        AVG((usage_data->'cost_tracking'->>'total_tokens')::NUMERIC) as avg_tokens_per_request,
        COUNT(*) FILTER (WHERE workflow_id IN (
            SELECT queue_id FROM processing_queue WHERE workflow_state = 'quota_exceeded'
        ))::INT as quota_exceeded_count
    FROM quota_usage_log
    WHERE service_name = p_service_name
    AND created_at >= NOW() - p_time_range
    GROUP BY DATE_TRUNC('hour', created_at)
    ORDER BY hour DESC;
END;
$$ LANGUAGE plpgsql;

-- Function to estimate when quota will reset
CREATE OR REPLACE FUNCTION estimate_quota_reset_time(
    p_service_name VARCHAR(50) DEFAULT 'gemini'
) RETURNS TABLE (
    quota_type VARCHAR(50),
    reset_at TIMESTAMPTZ,
    seconds_until_reset INT
) AS $$
BEGIN
    RETURN QUERY
    WITH current_usage AS (
        SELECT 
            service_name,
            (usage_data->'quotas')::jsonb as quotas
        FROM quota_usage_log
        WHERE service_name = p_service_name
        ORDER BY created_at DESC
        LIMIT 1
    )
    SELECT 
        key as quota_type,
        CASE 
            WHEN key LIKE '%_minute' THEN 
                DATE_TRUNC('minute', NOW()) + INTERVAL '1 minute'
            WHEN key LIKE '%_day' THEN 
                DATE_TRUNC('day', NOW()) + INTERVAL '1 day'
            ELSE NOW()
        END as reset_at,
        CASE 
            WHEN key LIKE '%_minute' THEN 
                EXTRACT(EPOCH FROM (DATE_TRUNC('minute', NOW()) + INTERVAL '1 minute' - NOW()))::INT
            WHEN key LIKE '%_day' THEN 
                EXTRACT(EPOCH FROM (DATE_TRUNC('day', NOW()) + INTERVAL '1 day' - NOW()))::INT
            ELSE 0
        END as seconds_until_reset
    FROM current_usage, jsonb_each(quotas)
    WHERE (value->>'remaining')::INT = 0;
END;
$$ LANGUAGE plpgsql;

-- Trigger to increment quota_exceeded_count
CREATE OR REPLACE FUNCTION update_quota_exceeded_count()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.workflow_state = 'quota_exceeded' AND 
       (OLD.workflow_state IS NULL OR OLD.workflow_state != 'quota_exceeded') THEN
        NEW.quota_exceeded_count = COALESCE(OLD.quota_exceeded_count, 0) + 1;
        NEW.last_quota_check = NOW();
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_quota_exceeded_count
BEFORE UPDATE ON processing_queue
FOR EACH ROW
EXECUTE FUNCTION update_quota_exceeded_count();

-- Index for finding quota exceeded items efficiently
CREATE INDEX IF NOT EXISTS idx_processing_queue_quota_exceeded
ON processing_queue(next_retry_at, priority DESC)
WHERE workflow_state = 'quota_exceeded';

-- Grant permissions
GRANT SELECT ON quota_usage_log TO readonly_user;
GRANT SELECT ON quota_limits TO readonly_user;
GRANT SELECT ON vw_quota_usage_current TO readonly_user;
GRANT SELECT ON vw_quota_exceeded_workflows TO readonly_user;
