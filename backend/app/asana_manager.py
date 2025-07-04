"""
Asana Integration for Scout

Handles Asana API integration for task management, stories, and webhooks.
Supports both Personal Access Token and OAuth authentication.
"""

import asyncio
import aiohttp
import logging
import json
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import os

logger = logging.getLogger(__name__)

@dataclass
class AsanaTask:
    """Asana task representation."""
    gid: str
    name: str
    notes: str
    completed: bool
    assignee: Optional[Dict[str, Any]]
    projects: List[Dict[str, Any]]
    created_at: datetime
    modified_at: datetime
    completed_at: Optional[datetime]
    due_on: Optional[str]
    tags: List[Dict[str, Any]]
    custom_fields: List[Dict[str, Any]]

@dataclass
class AsanaStory:
    """Asana story (activity log) representation."""
    gid: str
    type: str
    text: str
    created_at: datetime
    created_by: Dict[str, Any]
    target: Dict[str, Any]

class AsanaManager:
    """
    Manages Asana API integration for Scout.
    
    Features:
    - Personal Access Token and OAuth support
    - Task and project management
    - Story/activity retrieval
    - Webhook registration and handling
    - Sandbox environment support
    """
    
    def __init__(
        self,
        access_token: Optional[str] = None,
        base_url: str = "https://app.asana.com/api/1.0",
        sandbox: bool = False
    ):
        self.access_token = access_token or os.getenv("ASANA_ACCESS_TOKEN")
        self.base_url = "https://app.asana.com/api/1.0" if not sandbox else "https://app.asana.com/api/1.0"
        self.sandbox = sandbox
        self._session: Optional[aiohttp.ClientSession] = None
        
        if not self.access_token:
            logger.warning("⚠️  No Asana access token configured")
    
    async def __aenter__(self):
        """Async context manager entry."""
        self._session = aiohttp.ClientSession(
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._session:
            await self._session.close()
    
    async def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        params: Optional[Dict] = None,
        data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make authenticated request to Asana API."""
        if not self._session:
            raise RuntimeError("AsanaManager must be used as async context manager")
        
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        try:
            async with self._session.request(
                method, 
                url, 
                params=params, 
                json=data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get("data", result)
                elif response.status == 401:
                    raise Exception("Asana authentication failed - check access token")
                else:
                    error_text = await response.text()
                    raise Exception(f"Asana API error {response.status}: {error_text}")
        
        except aiohttp.ClientError as e:
            raise Exception(f"Asana API request failed: {e}")
    
    async def test_connection(self) -> bool:
        """Test Asana API connection."""
        try:
            await self._make_request("GET", "/users/me")
            return True
        except Exception as e:
            logger.error(f"Asana connection test failed: {e}")
            return False
    
    async def get_workspaces(self) -> List[Dict[str, Any]]:
        """Get user's Asana workspaces."""
        return await self._make_request("GET", "/workspaces")
    
    async def get_projects(self, workspace_gid: str) -> List[Dict[str, Any]]:
        """Get projects in a workspace."""
        params = {"workspace": workspace_gid}
        return await self._make_request("GET", "/projects", params=params)
    
    async def get_task(self, task_gid: str) -> AsanaTask:
        """Get detailed task information."""
        params = {
            "opt_fields": (
                "gid,name,notes,completed,assignee,projects,"
                "created_at,modified_at,completed_at,due_on,tags,custom_fields"
            )
        }
        task_data = await self._make_request("GET", f"/tasks/{task_gid}", params=params)
        
        return AsanaTask(
            gid=task_data["gid"],
            name=task_data["name"],
            notes=task_data.get("notes", ""),
            completed=task_data["completed"],
            assignee=task_data.get("assignee"),
            projects=task_data.get("projects", []),
            created_at=self._parse_datetime(task_data["created_at"]),
            modified_at=self._parse_datetime(task_data["modified_at"]),
            completed_at=self._parse_datetime(task_data.get("completed_at")) if task_data.get("completed_at") else None,
            due_on=task_data.get("due_on"),
            tags=task_data.get("tags", []),
            custom_fields=task_data.get("custom_fields", [])
        )
    
    async def get_tasks_in_project(
        self, 
        project_gid: str, 
        completed_since: Optional[datetime] = None
    ) -> List[AsanaTask]:
        """Get tasks from a project."""
        params = {
            "project": project_gid,
            "opt_fields": (
                "gid,name,notes,completed,assignee,projects,"
                "created_at,modified_at,completed_at,due_on"
            )
        }
        
        if completed_since:
            params["completed_since"] = completed_since.isoformat()
        
        tasks_data = await self._make_request("GET", "/tasks", params=params)
        
        tasks = []
        for task_data in tasks_data:
            task = AsanaTask(
                gid=task_data["gid"],
                name=task_data["name"],
                notes=task_data.get("notes", ""),
                completed=task_data["completed"],
                assignee=task_data.get("assignee"),
                projects=task_data.get("projects", []),
                created_at=self._parse_datetime(task_data["created_at"]),
                modified_at=self._parse_datetime(task_data["modified_at"]),
                completed_at=self._parse_datetime(task_data.get("completed_at")) if task_data.get("completed_at") else None,
                due_on=task_data.get("due_on"),
                tags=task_data.get("tags", []),
                custom_fields=task_data.get("custom_fields", [])
            )
            tasks.append(task)
        
        return tasks
    
    async def get_task_stories(self, task_gid: str) -> List[AsanaStory]:
        """Get all stories (activity log) for a task."""
        params = {
            "opt_fields": "gid,type,text,created_at,created_by,target"
        }
        stories_data = await self._make_request("GET", f"/tasks/{task_gid}/stories", params=params)
        
        stories = []
        for story_data in stories_data:
            story = AsanaStory(
                gid=story_data["gid"],
                type=story_data["type"],
                text=story_data.get("text", ""),
                created_at=self._parse_datetime(story_data["created_at"]),
                created_by=story_data.get("created_by", {}),
                target=story_data.get("target", {})
            )
            stories.append(story)
        
        return stories
    
    async def search_tasks(
        self, 
        workspace_gid: str, 
        assignee: Optional[str] = None,
        project: Optional[str] = None,
        completed: Optional[bool] = None,
        modified_since: Optional[datetime] = None
    ) -> List[AsanaTask]:
        """Search tasks with various filters."""
        params = {
            "workspace": workspace_gid,
            "opt_fields": (
                "gid,name,notes,completed,assignee,projects,"
                "created_at,modified_at,completed_at,due_on"
            )
        }
        
        if assignee:
            params["assignee"] = assignee
        if project:
            params["projects.any"] = project
        if completed is not None:
            params["completed"] = str(completed).lower()
        if modified_since:
            params["modified_since"] = modified_since.isoformat()
        
        tasks_data = await self._make_request("GET", "/tasks/search", params=params)
        
        tasks = []
        for task_data in tasks_data:
            task = AsanaTask(
                gid=task_data["gid"],
                name=task_data["name"],
                notes=task_data.get("notes", ""),
                completed=task_data["completed"],
                assignee=task_data.get("assignee"),
                projects=task_data.get("projects", []),
                created_at=self._parse_datetime(task_data["created_at"]),
                modified_at=self._parse_datetime(task_data["modified_at"]),
                completed_at=self._parse_datetime(task_data.get("completed_at")) if task_data.get("completed_at") else None,
                due_on=task_data.get("due_on"),
                tags=task_data.get("tags", []),
                custom_fields=task_data.get("custom_fields", [])
            )
            tasks.append(task)
        
        return tasks
    
    async def create_webhook(
        self, 
        resource: str, 
        target_url: str, 
        filters: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """Create webhook for Asana resource."""
        data = {
            "data": {
                "resource": resource,
                "target": target_url
            }
        }
        
        if filters:
            data["data"]["filters"] = filters
        
        return await self._make_request("POST", "/webhooks", data=data)
    
    async def get_webhooks(self, workspace_gid: str) -> List[Dict[str, Any]]:
        """Get all webhooks for a workspace."""
        params = {"workspace": workspace_gid}
        return await self._make_request("GET", "/webhooks", params=params)
    
    async def delete_webhook(self, webhook_gid: str) -> bool:
        """Delete a webhook."""
        try:
            await self._make_request("DELETE", f"/webhooks/{webhook_gid}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete webhook {webhook_gid}: {e}")
            return False
    
    def _parse_datetime(self, dt_string: Optional[str]) -> Optional[datetime]:
        """Parse Asana datetime string."""
        if not dt_string:
            return None
        
        try:
            # Asana returns ISO format: 2024-01-15T10:30:00.000Z
            return datetime.fromisoformat(dt_string.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            logger.warning(f"Failed to parse datetime: {dt_string}")
            return None
    
    # Webhook payload processing
    
    def process_webhook_payload(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Process incoming Asana webhook payload.
        Returns list of normalized events.
        """
        events = []
        
        for event in payload.get("events", []):
            normalized_event = {
                "action": event.get("action"),
                "resource": event.get("resource"),
                "user": event.get("user"),
                "created_at": event.get("created_at"),
                "parent": event.get("parent")
            }
            events.append(normalized_event)
        
        return events
    
    # Task linking utilities
    
    async def find_task_by_name_similarity(
        self, 
        workspace_gid: str, 
        name_query: str, 
        threshold: float = 0.75
    ) -> List[AsanaTask]:
        """
        Find tasks with names similar to the query using fuzzy matching.
        Used for linking PRs to tasks based on title similarity.
        """
        # Get recent tasks (last 30 days)
        from datetime import timedelta
        since = datetime.now(timezone.utc) - timedelta(days=30)
        
        all_tasks = await self.search_tasks(
            workspace_gid=workspace_gid,
            modified_since=since
        )
        
        # Simple fuzzy matching (could be enhanced with proper fuzzy libraries)
        matched_tasks = []
        query_lower = name_query.lower()
        
        for task in all_tasks:
            task_name_lower = task.name.lower()
            
            # Simple word overlap calculation
            query_words = set(query_lower.split())
            task_words = set(task_name_lower.split())
            
            if query_words and task_words:
                overlap = len(query_words.intersection(task_words))
                similarity = overlap / max(len(query_words), len(task_words))
                
                if similarity >= threshold:
                    matched_tasks.append(task)
        
        return matched_tasks
    
    async def get_user_info(self) -> Dict[str, Any]:
        """Get current user information."""
        return await self._make_request("GET", "/users/me")
    
    async def get_workspace_members(self, workspace_gid: str) -> List[Dict[str, Any]]:
        """Get members of a workspace."""
        params = {"workspace": workspace_gid}
        return await self._make_request("GET", "/users", params=params) 