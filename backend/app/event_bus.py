"""
Event Bus System for Scout

Handles all webhook data (GitHub and Asana) flowing into a unified timeline DB.
Normalizes events into: who, what, when, linked_to, metadata.
Supports enrichment and feeds downstream systems.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Union
from enum import Enum
from dataclasses import dataclass, asdict
from pathlib import Path
import sqlite3
import aiosqlite

logger = logging.getLogger(__name__)

class EventType(Enum):
    # GitHub Events
    GITHUB_PUSH = "github.push"
    GITHUB_PR_OPENED = "github.pr.opened"
    GITHUB_PR_UPDATED = "github.pr.updated"
    GITHUB_PR_MERGED = "github.pr.merged"
    GITHUB_PR_CLOSED = "github.pr.closed"
    GITHUB_REVIEW_SUBMITTED = "github.review.submitted"
    GITHUB_COMMIT = "github.commit"
    
    # Asana Events
    ASANA_TASK_CREATED = "asana.task.created"
    ASANA_TASK_UPDATED = "asana.task.updated"
    ASANA_TASK_COMPLETED = "asana.task.completed"
    ASANA_TASK_MOVED = "asana.task.moved"
    ASANA_COMMENT_ADDED = "asana.comment.added"
    
    # System Events
    SYSTEM_ANALYSIS_COMPLETED = "system.analysis.completed"
    SYSTEM_ALERT_TRIGGERED = "system.alert.triggered"

class EventSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class NormalizedEvent:
    """Normalized event structure for the Scout event timeline."""
    event_id: str
    event_type: EventType
    timestamp: datetime
    who: str  # Author/actor
    what: str  # Human-readable description
    linked_to: Optional[str] = None  # Related task/PR/commit
    metadata: Dict[str, Any] = None
    severity: EventSeverity = EventSeverity.LOW
    repository: Optional[str] = None
    project: Optional[str] = None
    enrichments: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.enrichments is None:
            self.enrichments = {}

class EventBus:
    """
    Central event bus for Scout operational intelligence.
    
    Responsibilities:
    - Receive webhook events from GitHub and Asana
    - Normalize events into unified timeline format
    - Store events in timeline database
    - Enrich events with additional context
    - Feed events to downstream systems (rule engine, weekly reports)
    """
    
    def __init__(self, db_path: str = "/tmp/scout_events.db"):
        self.db_path = db_path
        self.subscribers: List = []
        self._initialized = False
    
    async def initialize(self):
        """Initialize the event bus and database."""
        if self._initialized:
            return
            
        await self._create_database()
        self._initialized = True
        logger.info(f"🚌 Event Bus initialized with database at {self.db_path}")
    
    async def _create_database(self):
        """Create the events timeline database."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    who TEXT NOT NULL,
                    what TEXT NOT NULL,
                    linked_to TEXT,
                    metadata TEXT,
                    severity TEXT,
                    repository TEXT,
                    project TEXT,
                    enrichments TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp ON events(timestamp);
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_event_type ON events(event_type);
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_repository ON events(repository);
            """)
            
            await db.commit()
    
    async def emit_event(self, event: NormalizedEvent) -> bool:
        """
        Emit a normalized event to the bus.
        Stores in database and notifies subscribers.
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            # Store event in database
            await self._store_event(event)
            
            # Notify subscribers (rule engine, etc.)
            await self._notify_subscribers(event)
            
            logger.info(f"📡 Event emitted: {event.event_type.value} by {event.who}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to emit event {event.event_id}: {e}")
            return False
    
    async def _store_event(self, event: NormalizedEvent):
        """Store event in the timeline database."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO events 
                (event_id, event_type, timestamp, who, what, linked_to, 
                 metadata, severity, repository, project, enrichments)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.event_id,
                event.event_type.value,
                event.timestamp.isoformat(),
                event.who,
                event.what,
                event.linked_to,
                json.dumps(event.metadata),
                event.severity.value,
                event.repository,
                event.project,
                json.dumps(event.enrichments)
            ))
            await db.commit()
    
    async def _notify_subscribers(self, event: NormalizedEvent):
        """Notify all subscribers about the new event."""
        for subscriber in self.subscribers:
            try:
                if asyncio.iscoroutinefunction(subscriber):
                    await subscriber(event)
                else:
                    subscriber(event)
            except Exception as e:
                logger.error(f"Subscriber notification failed: {e}")
    
    def subscribe(self, callback):
        """Subscribe to event notifications."""
        self.subscribers.append(callback)
        logger.info(f"New subscriber registered: {callback.__name__}")
    
    async def get_events(
        self, 
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        event_types: Optional[List[EventType]] = None,
        repository: Optional[str] = None,
        limit: int = 100
    ) -> List[NormalizedEvent]:
        """Retrieve events from the timeline with filters."""
        if not self._initialized:
            await self.initialize()
        
        query = "SELECT * FROM events WHERE 1=1"
        params = []
        
        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time.isoformat())
        
        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time.isoformat())
        
        if event_types:
            type_placeholders = ",".join("?" * len(event_types))
            query += f" AND event_type IN ({type_placeholders})"
            params.extend([et.value for et in event_types])
        
        if repository:
            query += " AND repository = ?"
            params.append(repository)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
        
        events = []
        for row in rows:
            event = NormalizedEvent(
                event_id=row[0],
                event_type=EventType(row[1]),
                timestamp=datetime.fromisoformat(row[2]),
                who=row[3],
                what=row[4],
                linked_to=row[5],
                metadata=json.loads(row[6]) if row[6] else {},
                severity=EventSeverity(row[7]),
                repository=row[8],
                project=row[9],
                enrichments=json.loads(row[10]) if row[10] else {}
            )
            events.append(event)
        
        return events
    
    # Event Normalization Methods
    
    def normalize_github_push(self, payload: Dict[str, Any]) -> NormalizedEvent:
        """Normalize GitHub push webhook payload."""
        commits = payload.get("commits", [])
        commit_count = len(commits)
        
        return NormalizedEvent(
            event_id=f"github_push_{payload['after']}",
            event_type=EventType.GITHUB_PUSH,
            timestamp=datetime.now(timezone.utc),
            who=payload["pusher"]["name"],
            what=f"Pushed {commit_count} commit(s) to {payload['ref']}",
            repository=payload["repository"]["full_name"],
            metadata={
                "before": payload["before"],
                "after": payload["after"], 
                "ref": payload["ref"],
                "commits": commits,
                "commit_count": commit_count
            }
        )
    
    def normalize_github_pr(self, payload: Dict[str, Any], action: str) -> NormalizedEvent:
        """Normalize GitHub PR webhook payload."""
        pr = payload["pull_request"]
        
        action_map = {
            "opened": EventType.GITHUB_PR_OPENED,
            "closed": EventType.GITHUB_PR_MERGED if pr.get("merged") else EventType.GITHUB_PR_CLOSED,
            "edited": EventType.GITHUB_PR_UPDATED,
            "synchronize": EventType.GITHUB_PR_UPDATED
        }
        
        event_type = action_map.get(action, EventType.GITHUB_PR_UPDATED)
        
        return NormalizedEvent(
            event_id=f"github_pr_{pr['id']}_{action}",
            event_type=event_type,
            timestamp=datetime.fromisoformat(pr["updated_at"].replace("Z", "+00:00")),
            who=pr["user"]["login"],
            what=f"PR #{pr['number']}: {pr['title']} ({action})",
            linked_to=self._extract_asana_task_from_pr(pr),
            repository=payload["repository"]["full_name"],
            metadata={
                "pr_number": pr["number"],
                "title": pr["title"],
                "body": pr["body"],
                "state": pr["state"],
                "merged": pr.get("merged", False),
                "files_changed": pr.get("changed_files", 0),
                "additions": pr.get("additions", 0),
                "deletions": pr.get("deletions", 0)
            }
        )
    
    def normalize_asana_task(self, payload: Dict[str, Any]) -> NormalizedEvent:
        """Normalize Asana task webhook payload."""
        task = payload["task"]
        
        return NormalizedEvent(
            event_id=f"asana_task_{task['gid']}_{payload['action']}",
            event_type=EventType.ASANA_TASK_UPDATED,
            timestamp=datetime.now(timezone.utc),
            who=payload.get("user", {}).get("name", "Unknown"),
            what=f"Task updated: {task['name']}",
            linked_to=task["gid"],
            project=task.get("projects", [{}])[0].get("name") if task.get("projects") else None,
            metadata={
                "task_gid": task["gid"],
                "task_name": task["name"],
                "completed": task.get("completed", False),
                "assignee": task.get("assignee", {}).get("name"),
                "action": payload["action"]
            }
        )
    
    def _extract_asana_task_from_pr(self, pr: Dict[str, Any]) -> Optional[str]:
        """Extract Asana task GID from PR body or branch name."""
        import re
        
        # Look for Asana URLs in PR body
        body = pr.get("body") or ""
        asana_url_pattern = r"app\.asana\.com/0/(\d+)/(\d+)"
        match = re.search(asana_url_pattern, body)
        if match:
            return match.group(2)  # Task GID
        
        # Look for asana- prefix in branch name
        branch = pr.get("head", {}).get("ref", "")
        asana_branch_pattern = r"asana-(\d+)"
        match = re.search(asana_branch_pattern, branch)
        if match:
            return match.group(1)
        
        return None

# Event enrichment utilities

async def enrich_with_file_churn(event: NormalizedEvent, analyzer) -> NormalizedEvent:
    """Enrich commit events with file churn statistics."""
    if event.event_type not in [EventType.GITHUB_PUSH, EventType.GITHUB_COMMIT]:
        return event
    
    # Add file churn analysis logic here
    # This would analyze which files changed and their complexity
    event.enrichments["file_churn"] = {"analyzed": True}
    return event

async def enrich_with_task_links(event: NormalizedEvent) -> NormalizedEvent:
    """Enrich events with inferred task links using heuristics."""
    # Implement fuzzy matching logic for PR titles to task names
    # Author matching, temporal proximity analysis
    event.enrichments["task_linking"] = {"attempted": True}
    return event 