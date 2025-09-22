"""
Enhanced product workflow with quota management and partial state handling
"""

from typing import Any, Dict, Optional
from datetime import datetime
from uuid import UUID

from app.core.workflow import WorkflowState, ProcessingStage
from app.core.quota_manager import QuotaAwareWorkflowMixin, GlobalQuotaTracker
from app.core.exceptions import QuotaExceededException
from app.core.logging import log
from app.models import ProcessingQueue
from app.services.product_workflow import ProductWorkflowEngine
from app.core.database import AsyncSessionLocal


class EnhancedProductWorkflowEngine(QuotaAwareWorkflowMixin, ProductWorkflowEngine):
    """Product workflow engine with quota management"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Get global quota tracker for shared quota management
        self.global_quota_tracker = GlobalQuotaTracker()
    
    async def process_stage(self, workflow_id: str, stage: ProcessingStage):
        """Process stage with quota awareness"""
        try:
            # For AI-intensive stages, check quota first
            if stage in [ProcessingStage.ENRICHMENT, ProcessingStage.SCORING]:
                # Get global quota manager
                quota_manager = await self.global_quota_tracker.get_manager("gemini")
                
                # Estimate tokens based on stage
                estimated_tokens = 1000 if stage == ProcessingStage.ENRICHMENT else 200
                
                # Check quota
                can_proceed, error_msg, status = await quota_manager.check_quota(estimated_tokens)
                
                if not can_proceed:
                    # Save progress and transition to quota exceeded state
                    await self._handle_quota_exceeded(workflow_id, stage, error_msg, status)
                    return
            
            # Process normally
            await super().process_stage(workflow_id, stage)
            
        except QuotaExceededException as e:
            await self._handle_quota_exceeded(workflow_id, stage, str(e), e.quota_status)
        except Exception as e:
            # For other errors, use default handling
            raise
    
    async def _handle_quota_exceeded(
        self,
        workflow_id: str,
        stage: ProcessingStage,
        error_msg: str,
        quota_status: Dict[str, Any]
    ):
        """Handle quota exceeded by saving partial state"""
        # Get wait time from quota status
        wait_seconds = None
        for quota_type, info in quota_status.get("quotas", {}).items():
            if info["remaining"] == 0:
                # Calculate wait time based on window
                if "per_minute" in quota_type:
                    wait_seconds = 60
                elif "per_day" in quota_type:
                    wait_seconds = 86400  # 24 hours
                break
        
        # Save current progress
        async with AsyncSessionLocal() as session:
            queue_item = await session.get(ProcessingQueue, UUID(workflow_id))
            if queue_item:
                # Mark which stages were completed
                completed_stages = queue_item.stage_details.get("completed_stages", [])
                
                # Add all stages before the current one as completed
                for s in ProcessingStage:
                    if s == stage:
                        break
                    if s.value not in completed_stages:
                        completed_stages.append(s.value)
                
                # Update stage details
                queue_item.stage_details.update({
                    "completed_stages": completed_stages,
                    "last_stage_attempted": stage.value,
                    "quota_exceeded_at": datetime.utcnow().isoformat(),
                    "quota_status": quota_status,
                    "estimated_wait_seconds": wait_seconds,
                    "partial_results": self._extract_partial_results(queue_item)
                })
                
                await session.commit()
        
        # Transition to quota exceeded state
        await self.transition_state(
            workflow_id,
            WorkflowState.QUOTA_EXCEEDED,
            reason=f"Quota exceeded at stage {stage.value}: {error_msg}",
            metadata={
                "stage": stage.value,
                "wait_seconds": wait_seconds,
                "quota_status": quota_status,
                "can_resume": True
            }
        )
        
        # Schedule retry after wait time
        if wait_seconds:
            retry_at = datetime.utcnow().timestamp() + wait_seconds
            await self.schedule_retry(workflow_id, datetime.fromtimestamp(retry_at))
    
    def _extract_partial_results(self, queue_item: ProcessingQueue) -> Dict[str, Any]:
        """Extract any partial results that were processed"""
        partial = {}
        
        # Check what we have so far
        if queue_item.product_id:
            partial["product_id"] = str(queue_item.product_id)
        
        if "ai_result" in queue_item.stage_details:
            # We have AI analysis results
            ai_result = queue_item.stage_details["ai_result"]
            partial["ai_analysis_complete"] = True
            partial["consumer_data"] = ai_result.get("consumer_data")
            partial["brand_data"] = ai_result.get("brand_data")
        
        if "version_id" in queue_item.stage_details:
            partial["version_id"] = queue_item.stage_details["version_id"]
        
        completed_stages = queue_item.stage_details.get("completed_stages", [])
        partial["completed_stages"] = completed_stages
        partial["progress_percentage"] = (len(completed_stages) / len(ProcessingStage)) * 100
        
        return partial
    
    async def resume_from_partial_state(self, workflow_id: str) -> bool:
        """Resume processing from where it left off"""
        async with AsyncSessionLocal() as session:
            queue_item = await session.get(ProcessingQueue, UUID(workflow_id))
            if not queue_item:
                return False
            
            # Check if we can resume
            if not queue_item.stage_details.get("can_resume", False):
                log.warning(f"Workflow {workflow_id} cannot be resumed")
                return False
            
            # Get completed stages
            completed_stages = queue_item.stage_details.get("completed_stages", [])
            last_stage = queue_item.stage_details.get("last_stage_attempted")
            
            # Find where to resume from
            resume_from_stage = None
            for stage in ProcessingStage:
                if stage.value == last_stage:
                    resume_from_stage = stage
                    break
            
            if not resume_from_stage:
                # Start from beginning if we can't determine
                resume_from_stage = ProcessingStage.DISCOVERY
            
            # Update state to processing
            await self.transition_state(
                workflow_id,
                WorkflowState.PROCESSING,
                reason="Resuming from partial state after quota reset",
                metadata={
                    "resumed_from_stage": resume_from_stage.value,
                    "previously_completed": completed_stages
                }
            )
            
            # Continue processing from the stage that failed
            stage_index = list(ProcessingStage).index(resume_from_stage)
            for stage in list(ProcessingStage)[stage_index:]:
                try:
                    await self.process_stage(workflow_id, stage)
                except Exception as e:
                    log.error(f"Error resuming workflow at stage {stage}", error=str(e))
                    await self.handle_error(workflow_id, stage, e)
                    return False
            
            # Mark as completed
            await self.transition_state(workflow_id, WorkflowState.COMPLETED)
            return True
    
    async def _process_enrichment(self, queue_item: ProcessingQueue):
        """Process enrichment with token tracking"""
        # Get workflow ID
        workflow_id = str(queue_item.queue_id)
        
        try:
            # Call parent enrichment
            result = await self.ai_pipeline._process_enrichment(queue_item)
            
            # Track token usage
            if result:
                quota_manager = await self.global_quota_tracker.get_manager("gemini")
                
                # Record actual usage
                await quota_manager.record_usage(
                    tokens_used=result.get("tokens_used", 0),
                    input_tokens=result.get("input_tokens", 0),
                    output_tokens=result.get("output_tokens", 0),
                    images=len(queue_item.stage_details.get("crawler_data", {}).get("images", []))
                )
                
                # Save quota usage to database
                await quota_manager.save_to_database(workflow_id)
                
                # Log token usage
                log.info(
                    f"AI enrichment completed",
                    workflow_id=workflow_id,
                    tokens_used=result.get("tokens_used", 0),
                    cost=result.get("cost_estimate", 0),
                    quota_status=await quota_manager.get_status()
                )
            
            # Update queue item with results
            async with AsyncSessionLocal() as session:
                queue_item = await session.get(ProcessingQueue, queue_item.queue_id)
                queue_item.stage_details["ai_result"] = result
                await session.commit()
                
        except QuotaExceededException:
            # Re-raise to be handled by process_stage
            raise
        except Exception as e:
            log.error(f"Enrichment failed", workflow_id=workflow_id, error=str(e))
            raise
    
    async def get_quota_status(self) -> Dict[str, Any]:
        """Get current quota status across all services"""
        return await self.global_quota_tracker.get_all_status()
    
    async def get_workflows_by_state(self, state: WorkflowState, limit: int = 100) -> list[str]:
        """Get workflows in a specific state"""
        async with AsyncSessionLocal() as session:
            # Map workflow state to status
            state_mapping = {
                WorkflowState.QUOTA_EXCEEDED: "quota_exceeded",
                WorkflowState.PARTIALLY_PROCESSED: "partially_processed",
            }
            
            status = state_mapping.get(state, state.value)
            
            result = await session.execute(
                """
                SELECT queue_id 
                FROM processing_queue 
                WHERE workflow_state = :state 
                ORDER BY priority DESC, queued_at 
                LIMIT :limit
                """,
                {"state": status, "limit": limit}
            )
            
            return [str(row[0]) for row in result]
    
    async def resume_quota_exceeded_workflows(self) -> int:
        """Resume all workflows that were stopped due to quota issues"""
        # Get all quota exceeded workflows
        workflow_ids = await self.get_workflows_by_state(WorkflowState.QUOTA_EXCEEDED)
        
        resumed_count = 0
        for workflow_id in workflow_ids:
            try:
                # Check if quota is now available
                quota_manager = await self.global_quota_tracker.get_manager("gemini")
                can_proceed, _, _ = await quota_manager.check_quota(1000)
                
                if can_proceed:
                    # Resume the workflow
                    success = await self.resume_from_partial_state(workflow_id)
                    if success:
                        resumed_count += 1
                else:
                    # Still quota limited, stop checking others
                    break
                    
            except Exception as e:
                log.error(f"Error resuming workflow {workflow_id}", error=str(e))
                continue
        
        log.info(f"Resumed {resumed_count} workflows after quota reset")
        return resumed_count
