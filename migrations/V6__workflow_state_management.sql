-- V6__workflow_state_management.sql
-- Add workflow state management and transition tracking

-- Create workflow transitions audit table
CREATE TABLE IF NOT EXISTS workflow_transitions (
    transition_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID NOT NULL REFERENCES processing_queue(queue_id),
    from_state VARCHAR(50) NOT NULL,
    to_state VARCHAR(50) NOT NULL,
    stage VARCHAR(50),
    reason TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    actor VARCHAR(255),
    
    -- Indexes for queries
    INDEX idx_workflow_transitions_workflow_id (workflow_id),
    INDEX idx_workflow_transitions_created_at (created_at),
    INDEX idx_workflow_transitions_states (from_state, to_state)
);

-- Add workflow state tracking to processing_queue
ALTER TABLE processing_queue 
ADD COLUMN IF NOT EXISTS workflow_state VARCHAR(50) DEFAULT 'created',
ADD COLUMN IF NOT EXISTS workflow_version INT DEFAULT 1,
ADD COLUMN IF NOT EXISTS locked_by VARCHAR(255),
ADD COLUMN IF NOT EXISTS locked_at TIMESTAMPTZ;

-- Create index for workflow state queries
CREATE INDEX IF NOT EXISTS idx_processing_queue_workflow_state 
ON processing_queue(workflow_state, priority DESC, queued_at)
WHERE status = 'pending';

-- Create workflow metrics table
CREATE TABLE IF NOT EXISTS workflow_metrics (
    metric_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID REFERENCES processing_queue(queue_id),
    metric_type VARCHAR(50) NOT NULL, -- state_duration, stage_duration, error
    metric_name VARCHAR(100) NOT NULL,
    metric_value NUMERIC,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Indexes
    INDEX idx_workflow_metrics_workflow_id (workflow_id),
    INDEX idx_workflow_metrics_type_name (metric_type, metric_name),
    INDEX idx_workflow_metrics_created_at (created_at)
);

-- Create workflow events table for event sourcing
CREATE TABLE IF NOT EXISTS workflow_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    event_data JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    processed BOOLEAN DEFAULT FALSE,
    
    -- Indexes
    INDEX idx_workflow_events_workflow_id (workflow_id),
    INDEX idx_workflow_events_type (event_type),
    INDEX idx_workflow_events_created_at (created_at),
    INDEX idx_workflow_events_unprocessed (created_at) WHERE NOT processed
);

-- Create workflow deadletter table for failed items
CREATE TABLE IF NOT EXISTS workflow_deadletter (
    deadletter_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID NOT NULL,
    original_data JSONB NOT NULL,
    error_message TEXT,
    error_details JSONB,
    failure_count INT DEFAULT 1,
    last_failure_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    resolution_notes TEXT,
    
    -- Indexes
    INDEX idx_workflow_deadletter_workflow_id (workflow_id),
    INDEX idx_workflow_deadletter_unresolved (created_at) WHERE resolved_at IS NULL
);

-- Function to safely transition workflow state
CREATE OR REPLACE FUNCTION transition_workflow_state(
    p_workflow_id UUID,
    p_from_state VARCHAR(50),
    p_to_state VARCHAR(50),
    p_stage VARCHAR(50) DEFAULT NULL,
    p_reason TEXT DEFAULT NULL,
    p_metadata JSONB DEFAULT '{}',
    p_actor VARCHAR(255) DEFAULT NULL
) RETURNS BOOLEAN AS $$
DECLARE
    v_current_state VARCHAR(50);
    v_transition_id UUID;
BEGIN
    -- Lock the workflow row
    SELECT workflow_state INTO v_current_state
    FROM processing_queue
    WHERE queue_id = p_workflow_id
    FOR UPDATE;
    
    -- Check if current state matches expected
    IF v_current_state != p_from_state THEN
        RETURN FALSE;
    END IF;
    
    -- Update workflow state
    UPDATE processing_queue
    SET workflow_state = p_to_state,
        workflow_version = workflow_version + 1,
        stage_details = stage_details || p_metadata
    WHERE queue_id = p_workflow_id;
    
    -- Record transition
    INSERT INTO workflow_transitions (
        workflow_id, from_state, to_state, stage, reason, metadata, actor
    ) VALUES (
        p_workflow_id, p_from_state, p_to_state, p_stage, p_reason, p_metadata, p_actor
    ) RETURNING transition_id INTO v_transition_id;
    
    -- Emit event
    INSERT INTO workflow_events (workflow_id, event_type, event_data)
    VALUES (
        p_workflow_id, 
        'state_changed',
        jsonb_build_object(
            'transition_id', v_transition_id,
            'from_state', p_from_state,
            'to_state', p_to_state,
            'stage', p_stage,
            'reason', p_reason
        )
    );
    
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- Function to acquire workflow lock
CREATE OR REPLACE FUNCTION acquire_workflow_lock(
    p_workflow_id UUID,
    p_worker_id VARCHAR(255),
    p_timeout_seconds INT DEFAULT 300
) RETURNS BOOLEAN AS $$
DECLARE
    v_locked BOOLEAN;
BEGIN
    UPDATE processing_queue
    SET locked_by = p_worker_id,
        locked_at = NOW()
    WHERE queue_id = p_workflow_id
    AND (
        locked_by IS NULL 
        OR locked_at < NOW() - INTERVAL '1 second' * p_timeout_seconds
    );
    
    GET DIAGNOSTICS v_locked = ROW_COUNT;
    RETURN v_locked > 0;
END;
$$ LANGUAGE plpgsql;

-- Function to release workflow lock
CREATE OR REPLACE FUNCTION release_workflow_lock(
    p_workflow_id UUID,
    p_worker_id VARCHAR(255)
) RETURNS BOOLEAN AS $$
DECLARE
    v_released BOOLEAN;
BEGIN
    UPDATE processing_queue
    SET locked_by = NULL,
        locked_at = NULL
    WHERE queue_id = p_workflow_id
    AND locked_by = p_worker_id;
    
    GET DIAGNOSTICS v_released = ROW_COUNT;
    RETURN v_released > 0;
END;
$$ LANGUAGE plpgsql;

-- View for workflow monitoring
CREATE OR REPLACE VIEW vw_workflow_status AS
SELECT 
    pq.queue_id AS workflow_id,
    pq.product_id,
    pq.workflow_state,
    pq.status AS legacy_status,
    pq.stage,
    pq.priority,
    pq.retry_count,
    pq.queued_at,
    pq.processing_started_at,
    pq.completed_at,
    pq.locked_by,
    pq.locked_at,
    CASE 
        WHEN pq.locked_at IS NOT NULL 
        THEN EXTRACT(EPOCH FROM (NOW() - pq.locked_at))
        ELSE NULL 
    END AS lock_duration_seconds,
    pq.last_error,
    p.name AS product_name,
    b.name AS brand_name
FROM processing_queue pq
LEFT JOIN product p ON pq.product_id = p.product_id
LEFT JOIN brand b ON p.brand_id = b.brand_id;

-- View for workflow performance metrics
CREATE OR REPLACE VIEW vw_workflow_performance AS
SELECT 
    DATE_TRUNC('hour', created_at) AS hour,
    workflow_state,
    COUNT(*) AS count,
    AVG(EXTRACT(EPOCH FROM (completed_at - queued_at))) AS avg_duration_seconds,
    MIN(EXTRACT(EPOCH FROM (completed_at - queued_at))) AS min_duration_seconds,
    MAX(EXTRACT(EPOCH FROM (completed_at - queued_at))) AS max_duration_seconds,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (completed_at - queued_at))) AS median_duration_seconds,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (completed_at - queued_at))) AS p95_duration_seconds
FROM processing_queue
WHERE completed_at IS NOT NULL
GROUP BY DATE_TRUNC('hour', created_at), workflow_state;

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_processing_queue_locked 
ON processing_queue(locked_by, locked_at) 
WHERE locked_by IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_workflow_transitions_lookup
ON workflow_transitions(workflow_id, created_at DESC);

-- Grant permissions (adjust as needed)
GRANT SELECT ON workflow_transitions TO readonly_user;
GRANT SELECT ON workflow_metrics TO readonly_user;
GRANT SELECT ON workflow_events TO readonly_user;
GRANT SELECT ON vw_workflow_status TO readonly_user;
GRANT SELECT ON vw_workflow_performance TO readonly_user;
