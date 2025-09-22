"""Add workflow state management

Revision ID: 83e20b278cac
Revises: 
Create Date: 2025-09-16 10:55:49.303523

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '83e20b278cac'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add workflow state management tables and functions"""
    
    # Create workflow transitions audit table
    op.create_table('workflow_transitions',
        sa.Column('transition_id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('workflow_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('from_state', sa.String(50), nullable=False),
        sa.Column('to_state', sa.String(50), nullable=False),
        sa.Column('stage', sa.String(50), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(), server_default='{}', nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=True),
        sa.Column('actor', sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint('transition_id'),
        sa.ForeignKeyConstraint(['workflow_id'], ['processing_queue.queue_id'], )
    )
    op.create_index('idx_workflow_transitions_workflow_id', 'workflow_transitions', ['workflow_id'])
    op.create_index('idx_workflow_transitions_created_at', 'workflow_transitions', ['created_at'])
    op.create_index('idx_workflow_transitions_states', 'workflow_transitions', ['from_state', 'to_state'])

    # Add workflow state tracking columns to processing_queue
    op.add_column('processing_queue', sa.Column('workflow_state', sa.String(50), server_default='created', nullable=True))
    op.add_column('processing_queue', sa.Column('workflow_version', sa.Integer(), server_default='1', nullable=True))
    op.add_column('processing_queue', sa.Column('locked_by', sa.String(255), nullable=True))
    op.add_column('processing_queue', sa.Column('locked_at', sa.TIMESTAMP(timezone=True), nullable=True))
    
    # Create index for workflow state queries
    op.create_index(
        'idx_processing_queue_workflow_state', 
        'processing_queue', 
        ['workflow_state', 'priority', 'queued_at'],
        postgresql_where=sa.text("status = 'pending'")
    )
    
    # Create workflow metrics table
    op.create_table('workflow_metrics',
        sa.Column('metric_id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('workflow_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('metric_type', sa.String(50), nullable=False),
        sa.Column('metric_name', sa.String(100), nullable=False),
        sa.Column('metric_value', sa.Numeric(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(), server_default='{}', nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=True),
        sa.PrimaryKeyConstraint('metric_id'),
        sa.ForeignKeyConstraint(['workflow_id'], ['processing_queue.queue_id'], )
    )
    op.create_index('idx_workflow_metrics_workflow_id', 'workflow_metrics', ['workflow_id'])
    op.create_index('idx_workflow_metrics_type_name', 'workflow_metrics', ['metric_type', 'metric_name'])
    op.create_index('idx_workflow_metrics_created_at', 'workflow_metrics', ['created_at'])
    
    # Create workflow events table for event sourcing
    op.create_table('workflow_events',
        sa.Column('event_id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('workflow_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('event_data', postgresql.JSONB(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=True),
        sa.Column('processed', sa.Boolean(), server_default='FALSE', nullable=True),
        sa.PrimaryKeyConstraint('event_id')
    )
    op.create_index('idx_workflow_events_workflow_id', 'workflow_events', ['workflow_id'])
    op.create_index('idx_workflow_events_type', 'workflow_events', ['event_type'])
    op.create_index('idx_workflow_events_created_at', 'workflow_events', ['created_at'])
    op.create_index('idx_workflow_events_unprocessed', 'workflow_events', ['created_at'], postgresql_where=sa.text('NOT processed'))
    
    # Create workflow deadletter table for failed items
    op.create_table('workflow_deadletter',
        sa.Column('deadletter_id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('workflow_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('original_data', postgresql.JSONB(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_details', postgresql.JSONB(), nullable=True),
        sa.Column('failure_count', sa.Integer(), server_default='1', nullable=True),
        sa.Column('last_failure_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=True),
        sa.Column('resolved_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('deadletter_id')
    )
    op.create_index('idx_workflow_deadletter_workflow_id', 'workflow_deadletter', ['workflow_id'])
    op.create_index('idx_workflow_deadletter_unresolved', 'workflow_deadletter', ['created_at'], postgresql_where=sa.text('resolved_at IS NULL'))
    
    # Create indexes for performance
    op.create_index('idx_processing_queue_locked', 'processing_queue', ['locked_by', 'locked_at'], postgresql_where=sa.text('locked_by IS NOT NULL'))
    op.create_index('idx_workflow_transitions_lookup', 'workflow_transitions', ['workflow_id', 'created_at'])
    
    # Create function to safely transition workflow state
    op.execute("""
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
    """)
    
    # Function to acquire workflow lock
    op.execute("""
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
    """)
    
    # Function to release workflow lock
    op.execute("""
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
    """)
    
    # View for workflow monitoring
    op.execute("""
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
    """)
    
    # View for workflow performance metrics
    op.execute("""
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
    """)
    
    # Grant permissions (adjust as needed)
    # Note: These might fail if users don't exist, so we wrap in try/except equivalent
    op.execute("DO $$ BEGIN GRANT SELECT ON workflow_transitions TO readonly_user; EXCEPTION WHEN undefined_object THEN NULL; END $$;")
    op.execute("DO $$ BEGIN GRANT SELECT ON workflow_metrics TO readonly_user; EXCEPTION WHEN undefined_object THEN NULL; END $$;")
    op.execute("DO $$ BEGIN GRANT SELECT ON workflow_events TO readonly_user; EXCEPTION WHEN undefined_object THEN NULL; END $$;")
    op.execute("DO $$ BEGIN GRANT SELECT ON vw_workflow_status TO readonly_user; EXCEPTION WHEN undefined_object THEN NULL; END $$;")
    op.execute("DO $$ BEGIN GRANT SELECT ON vw_workflow_performance TO readonly_user; EXCEPTION WHEN undefined_object THEN NULL; END $$;")


def downgrade() -> None:
    """Remove workflow state management"""
    
    # Drop views
    op.execute("DROP VIEW IF EXISTS vw_workflow_performance")
    op.execute("DROP VIEW IF EXISTS vw_workflow_status")
    
    # Drop functions
    op.execute("DROP FUNCTION IF EXISTS release_workflow_lock")
    op.execute("DROP FUNCTION IF EXISTS acquire_workflow_lock")
    op.execute("DROP FUNCTION IF EXISTS transition_workflow_state")
    
    # Drop indexes
    op.drop_index('idx_workflow_transitions_lookup', table_name='workflow_transitions')
    op.drop_index('idx_processing_queue_locked', table_name='processing_queue')
    
    # Drop tables
    op.drop_table('workflow_deadletter')
    op.drop_table('workflow_events')
    op.drop_table('workflow_metrics')
    op.drop_table('workflow_transitions')
    
    # Drop columns from processing_queue
    op.drop_index('idx_processing_queue_workflow_state', table_name='processing_queue')
    op.drop_column('processing_queue', 'locked_at')
    op.drop_column('processing_queue', 'locked_by')
    op.drop_column('processing_queue', 'workflow_version')
    op.drop_column('processing_queue', 'workflow_state')