"""Add quota management

Revision ID: 3abc3b73b4a9
Revises: 83e20b278cac
Create Date: 2025-09-16 10:57:32.445467

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '3abc3b73b4a9'
down_revision = '83e20b278cac'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add quota tracking and management tables"""
    
    # Table for tracking quota usage over time
    op.create_table('quota_usage_log',
        sa.Column('log_id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('workflow_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('service_name', sa.String(50), server_default='gemini', nullable=False),
        sa.Column('usage_data', postgresql.JSONB(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=True),
        sa.PrimaryKeyConstraint('log_id'),
        sa.ForeignKeyConstraint(['workflow_id'], ['processing_queue.queue_id'], )
    )
    op.create_index('idx_quota_usage_workflow', 'quota_usage_log', ['workflow_id'])
    op.create_index('idx_quota_usage_service', 'quota_usage_log', ['service_name'])
    op.create_index('idx_quota_usage_created', 'quota_usage_log', [sa.text('created_at DESC')])
    
    # Add new columns to processing_queue
    op.add_column('processing_queue', sa.Column('partial_results', postgresql.JSONB(), server_default='{}', nullable=True))
    op.add_column('processing_queue', sa.Column('quota_exceeded_count', sa.Integer(), server_default='0', nullable=True))
    op.add_column('processing_queue', sa.Column('last_quota_check', sa.TIMESTAMP(timezone=True), nullable=True))
    
    # Table for quota limit configurations
    op.create_table('quota_limits',
        sa.Column('limit_id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('service_name', sa.String(50), nullable=False),
        sa.Column('quota_type', sa.String(50), nullable=False),
        sa.Column('limit_value', sa.Integer(), nullable=False),
        sa.Column('window_seconds', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='TRUE', nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=True),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=True),
        sa.PrimaryKeyConstraint('limit_id'),
        sa.UniqueConstraint('service_name', 'quota_type')
    )
    op.create_index('idx_quota_limits_service', 'quota_limits', ['service_name'], postgresql_where=sa.text('is_active'))
    
    # Insert default Gemini limits
    op.execute("""
        INSERT INTO quota_limits (service_name, quota_type, limit_value, window_seconds) VALUES
        ('gemini', 'tokens_per_minute', 4000000, 60),
        ('gemini', 'tokens_per_day', 1000000000, 86400),
        ('gemini', 'requests_per_minute', 15, 60),
        ('gemini', 'requests_per_day', 1500, 86400)
        ON CONFLICT (service_name, quota_type) DO NOTHING;
    """)
    
    # View for current quota usage
    op.execute("""
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
    """)
    
    # View for quota exceeded workflows
    op.execute("""
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
    """)
    
    # Function to get quota usage summary
    op.execute("""
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
    """)
    
    # Function to estimate when quota will reset
    op.execute("""
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
    """)
    
    # Trigger to increment quota_exceeded_count
    op.execute("""
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
    """)
    
    op.execute("""
        CREATE TRIGGER trg_quota_exceeded_count
        BEFORE UPDATE ON processing_queue
        FOR EACH ROW
        EXECUTE FUNCTION update_quota_exceeded_count();
    """)
    
    # Index for finding quota exceeded items efficiently
    op.create_index(
        'idx_processing_queue_quota_exceeded',
        'processing_queue',
        ['next_retry_at', 'priority'],
        postgresql_where=sa.text("workflow_state = 'quota_exceeded'")
    )
    
    # Grant permissions (with error handling)
    op.execute("DO $$ BEGIN GRANT SELECT ON quota_usage_log TO readonly_user; EXCEPTION WHEN undefined_object THEN NULL; END $$;")
    op.execute("DO $$ BEGIN GRANT SELECT ON quota_limits TO readonly_user; EXCEPTION WHEN undefined_object THEN NULL; END $$;")
    op.execute("DO $$ BEGIN GRANT SELECT ON vw_quota_usage_current TO readonly_user; EXCEPTION WHEN undefined_object THEN NULL; END $$;")
    op.execute("DO $$ BEGIN GRANT SELECT ON vw_quota_exceeded_workflows TO readonly_user; EXCEPTION WHEN undefined_object THEN NULL; END $$;")


def downgrade() -> None:
    """Remove quota management"""
    
    # Drop trigger
    op.execute("DROP TRIGGER IF EXISTS trg_quota_exceeded_count ON processing_queue")
    op.execute("DROP FUNCTION IF EXISTS update_quota_exceeded_count")
    
    # Drop functions
    op.execute("DROP FUNCTION IF EXISTS estimate_quota_reset_time")
    op.execute("DROP FUNCTION IF EXISTS get_quota_usage_summary")
    
    # Drop views
    op.execute("DROP VIEW IF EXISTS vw_quota_exceeded_workflows")
    op.execute("DROP VIEW IF EXISTS vw_quota_usage_current")
    
    # Drop index
    op.drop_index('idx_processing_queue_quota_exceeded', table_name='processing_queue')
    
    # Drop tables
    op.drop_table('quota_limits')
    op.drop_table('quota_usage_log')
    
    # Drop columns from processing_queue
    op.drop_column('processing_queue', 'last_quota_check')
    op.drop_column('processing_queue', 'quota_exceeded_count')
    op.drop_column('processing_queue', 'partial_results')