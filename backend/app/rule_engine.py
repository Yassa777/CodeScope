"""
Rule Engine for Scout

Lightweight CPU-bound system that evaluates all new events to decide
whether to call the LLM for real-time alerts.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional, Callable, Union
from dataclasses import dataclass
from enum import Enum

from .event_bus import NormalizedEvent, EventType, EventSeverity

logger = logging.getLogger(__name__)

class RuleCategory(Enum):
    PR_HEALTH = "pr_health"
    CI_QUALITY = "ci_quality"
    SECURITY = "security"
    TASK_TRACKING = "task_tracking"
    CUSTOM = "custom"

@dataclass
class RuleDefinition:
    """Definition of a rule that can trigger alerts."""
    rule_id: str
    name: str
    description: str
    category: RuleCategory
    severity: EventSeverity
    condition: Callable[[NormalizedEvent, Dict[str, Any]], bool]
    threshold_config: Dict[str, Any] = None
    enabled: bool = True
    
    def __post_init__(self):
        if self.threshold_config is None:
            self.threshold_config = {}

@dataclass
class AlertContext:
    """Context information for an alert that needs LLM analysis."""
    rule_id: str
    triggering_event: NormalizedEvent
    related_events: List[NormalizedEvent]
    severity: EventSeverity
    summary: str
    metadata: Dict[str, Any]

class RuleEngine:
    """
    CPU-bound rule evaluation system for real-time alerts.
    
    Evaluates events against predefined rules to determine if
    situations warrant LLM analysis and alerting.
    """
    
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.rules: Dict[str, RuleDefinition] = {}
        self.alert_callbacks: List[Callable] = []
        self._event_cache: List[NormalizedEvent] = []
        self._cache_size = 1000
        
        # Initialize default rules
        self._register_default_rules()
    
    def _register_default_rules(self):
        """Register the default Scout alert rules."""
        
        # PR Health Rules
        self.register_rule(RuleDefinition(
            rule_id="stale_pr",
            name="Stale Pull Request",
            description="PR open for more than configured days without review",
            category=RuleCategory.PR_HEALTH,
            severity=EventSeverity.MEDIUM,
            condition=self._check_stale_pr,
            threshold_config={"days": 7}
        ))
        
        self.register_rule(RuleDefinition(
            rule_id="hotfix_to_main",
            name="Hotfix to Main",
            description="Commits made directly to main branch",
            category=RuleCategory.SECURITY,
            severity=EventSeverity.HIGH,
            condition=self._check_hotfix_to_main
        ))
        
        # CI Quality Rules
        self.register_rule(RuleDefinition(
            rule_id="high_ci_failure_rate",
            name="High CI Failure Rate",
            description="CI failure rate exceeds threshold on recent PRs",
            category=RuleCategory.CI_QUALITY,
            severity=EventSeverity.HIGH,
            condition=self._check_ci_failure_rate,
            threshold_config={"failure_rate": 0.1, "window_hours": 24}
        ))
        
        # Task Tracking Rules
        self.register_rule(RuleDefinition(
            rule_id="task_completed_no_pr",
            name="Task Completed Without PR",
            description="Task moved to Done with no corresponding PR",
            category=RuleCategory.TASK_TRACKING,
            severity=EventSeverity.MEDIUM,
            condition=self._check_task_completed_no_pr
        ))
        
        logger.info(f"📏 Registered {len(self.rules)} default rules")
    
    def register_rule(self, rule: RuleDefinition):
        """Register a new rule with the engine."""
        self.rules[rule.rule_id] = rule
        logger.info(f"📋 Registered rule: {rule.name} ({rule.rule_id})")
    
    def subscribe_to_alerts(self, callback: Callable[[AlertContext], None]):
        """Subscribe to alert notifications."""
        self.alert_callbacks.append(callback)
    
    async def evaluate_event(self, event: NormalizedEvent) -> List[AlertContext]:
        """
        Evaluate an event against all rules and return triggered alerts.
        """
        # Add event to cache for rule evaluation
        self._event_cache.append(event)
        if len(self._event_cache) > self._cache_size:
            self._event_cache.pop(0)
        
        triggered_alerts = []
        
        for rule in self.rules.values():
            if not rule.enabled:
                continue
                
            try:
                # Build context for rule evaluation
                context = self._build_rule_context(event, rule)
                
                # Evaluate rule condition
                if rule.condition(event, context):
                    alert = await self._create_alert_context(rule, event, context)
                    triggered_alerts.append(alert)
                    
                    # Notify alert subscribers
                    await self._notify_alert_subscribers(alert)
                    
                    logger.info(f"🚨 Rule triggered: {rule.name} for event {event.event_id}")
            
            except Exception as e:
                logger.error(f"Rule evaluation failed for {rule.rule_id}: {e}")
        
        return triggered_alerts
    
    def _build_rule_context(self, event: NormalizedEvent, rule: RuleDefinition) -> Dict[str, Any]:
        """Build context for rule evaluation."""
        context = {
            "recent_events": self._get_recent_events(hours=24),
            "related_events": self._get_related_events(event),
            "threshold_config": rule.threshold_config,
            "event_cache": self._event_cache
        }
        return context
    
    def _get_recent_events(self, hours: int = 24) -> List[NormalizedEvent]:
        """Get events from the last N hours."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        return [e for e in self._event_cache if e.timestamp >= cutoff]
    
    def _get_related_events(self, event: NormalizedEvent) -> List[NormalizedEvent]:
        """Get events related to the current event."""
        related = []
        for cached_event in self._event_cache:
            if cached_event.event_id == event.event_id:
                continue
            
            # Same repository
            if cached_event.repository == event.repository:
                related.append(cached_event)
            
            # Same linked task/PR
            if event.linked_to and cached_event.linked_to == event.linked_to:
                related.append(cached_event)
        
        return related
    
    async def _create_alert_context(
        self, 
        rule: RuleDefinition, 
        event: NormalizedEvent, 
        context: Dict[str, Any]
    ) -> AlertContext:
        """Create alert context for LLM analysis."""
        return AlertContext(
            rule_id=rule.rule_id,
            triggering_event=event,
            related_events=context["related_events"],
            severity=rule.severity,
            summary=f"{rule.name}: {rule.description}",
            metadata={
                "rule_name": rule.name,
                "rule_category": rule.category.value,
                "threshold_config": rule.threshold_config,
                "context_size": len(context["related_events"])
            }
        )
    
    async def _notify_alert_subscribers(self, alert: AlertContext):
        """Notify all alert subscribers."""
        for callback in self.alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(alert)
                else:
                    callback(alert)
            except Exception as e:
                logger.error(f"Alert callback failed: {e}")
    
    # Default Rule Implementations
    
    def _check_stale_pr(self, event: NormalizedEvent, context: Dict[str, Any]) -> bool:
        """Check if a PR has been open too long without review."""
        if event.event_type != EventType.GITHUB_PR_OPENED:
            return False
        
        threshold_days = context["threshold_config"].get("days", 7)
        threshold_time = datetime.now(timezone.utc) - timedelta(days=threshold_days)
        
        # Check if PR was opened before threshold and has no review activity
        if event.timestamp < threshold_time:
            # Look for review events for this PR
            pr_number = event.metadata.get("pr_number")
            if pr_number:
                review_events = [
                    e for e in context["recent_events"]
                    if e.event_type == EventType.GITHUB_REVIEW_SUBMITTED
                    and e.metadata.get("pr_number") == pr_number
                ]
                return len(review_events) == 0
        
        return False
    
    def _check_hotfix_to_main(self, event: NormalizedEvent, context: Dict[str, Any]) -> bool:
        """Check if commits were made directly to main branch."""
        if event.event_type != EventType.GITHUB_PUSH:
            return False
        
        ref = event.metadata.get("ref", "")
        return ref in ["refs/heads/main", "refs/heads/master"]
    
    def _check_ci_failure_rate(self, event: NormalizedEvent, context: Dict[str, Any]) -> bool:
        """Check if CI failure rate exceeds threshold."""
        # This would need CI status events to work properly
        # For now, return False as placeholder
        return False
    
    def _check_task_completed_no_pr(self, event: NormalizedEvent, context: Dict[str, Any]) -> bool:
        """Check if task was completed without corresponding PR."""
        if event.event_type != EventType.ASANA_TASK_COMPLETED:
            return False
        
        task_gid = event.metadata.get("task_gid")
        if not task_gid:
            return False
        
        # Look for PRs linked to this task
        linked_prs = [
            e for e in context["related_events"]
            if e.linked_to == task_gid
            and e.event_type in [EventType.GITHUB_PR_OPENED, EventType.GITHUB_PR_MERGED]
        ]
        
        return len(linked_prs) == 0
    
    # Configuration methods
    
    def update_rule_threshold(self, rule_id: str, threshold_config: Dict[str, Any]):
        """Update threshold configuration for a rule."""
        if rule_id in self.rules:
            self.rules[rule_id].threshold_config.update(threshold_config)
            logger.info(f"Updated threshold for rule {rule_id}: {threshold_config}")
    
    def enable_rule(self, rule_id: str):
        """Enable a rule."""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = True
            logger.info(f"Enabled rule: {rule_id}")
    
    def disable_rule(self, rule_id: str):
        """Disable a rule."""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = False
            logger.info(f"Disabled rule: {rule_id}")
    
    def get_rule_stats(self) -> Dict[str, Any]:
        """Get statistics about rules and their evaluations."""
        return {
            "total_rules": len(self.rules),
            "enabled_rules": len([r for r in self.rules.values() if r.enabled]),
            "rules_by_category": {
                cat.value: len([r for r in self.rules.values() if r.category == cat])
                for cat in RuleCategory
            },
            "rules_by_severity": {
                sev.value: len([r for r in self.rules.values() if r.severity == sev])
                for sev in EventSeverity
            }
        } 