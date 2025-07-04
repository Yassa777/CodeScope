#!/usr/bin/env python3
"""
Scout Operational Intelligence Demo

This script demonstrates Scout's key features:
1. Event Bus - Processing GitHub and Asana webhooks
2. Rule Engine - Real-time alerts for development issues
3. Timeline API - Unified view of development activity
"""

import requests
import json
import time
from datetime import datetime

BASE_URL = "http://localhost:8000"

def demo_scout():
    print("🧠 Scout Operational Intelligence Demo")
    print("=" * 50)
    
    # Check system health
    print("\n1. Checking Scout System Health...")
    health = requests.get(f"{BASE_URL}/health").json()
    print(f"✅ Status: {health['status']}")
    print(f"📊 Services: {health['services']}")
    print(f"🚀 Scout Ready: {health['scout_ready']}")
    
    # Show rule engine configuration
    print("\n2. Rule Engine Configuration...")
    rules = requests.get(f"{BASE_URL}/rules").json()
    print(f"📏 Total Rules: {rules['rule_stats']['total_rules']}")
    print("Rules by Category:")
    for category, count in rules['rule_stats']['rules_by_category'].items():
        if count > 0:
            print(f"  - {category}: {count}")
    
    # Simulate development activity
    print("\n3. Simulating Development Activity...")
    
    # Simulate PR opened
    print("📝 Developer opens a PR...")
    pr_payload = {
        "action": "opened",
        "pull_request": {
            "id": 42,
            "number": 123,
            "title": "Implement user authentication system",
            "body": "Adds JWT-based authentication with proper session management",
            "user": {"login": "alice_dev"},
            "updated_at": datetime.now().isoformat() + "Z",
            "head": {"ref": "feature/auth-system"},
            "state": "open",
            "merged": False
        },
        "repository": {"full_name": "acme-corp/web-app"}
    }
    
    response = requests.post(f"{BASE_URL}/webhooks/github", json=pr_payload)
    print(f"   Event processed: {response.json()}")
    
    # Simulate push to feature branch
    print("💻 Developer pushes code changes...")
    push_payload = {
        "pusher": {"name": "alice_dev"},
        "commits": [
            {"message": "Add JWT token validation"},
            {"message": "Implement login endpoint"}
        ],
        "before": "abc123",
        "after": "def456", 
        "ref": "refs/heads/feature/auth-system",
        "repository": {"full_name": "acme-corp/web-app"}
    }
    
    response = requests.post(f"{BASE_URL}/webhooks/github", json=push_payload)
    print(f"   Event processed: {response.json()}")
    
    # Simulate hotfix push (triggers rule)
    print("🚨 Emergency hotfix pushed directly to main...")
    hotfix_payload = {
        "pusher": {"name": "bob_admin"},
        "commits": [{"message": "HOTFIX: Fix critical security vulnerability"}],
        "before": "def456",
        "after": "xyz789",
        "ref": "refs/heads/main",  # Direct push to main!
        "repository": {"full_name": "acme-corp/web-app"}
    }
    
    response = requests.post(f"{BASE_URL}/webhooks/github", json=hotfix_payload)
    print(f"   Event processed: {response.json()}")
    print("   ⚠️  This should trigger the 'Hotfix to Main' rule!")
    
    # Simulate Asana task completion
    print("✅ Task marked as completed in Asana...")
    asana_payload = {
        "events": [{
            "action": "completed",
            "resource": {
                "gid": "task_789",
                "name": "Implement user authentication system",
                "completed": True,
                "assignee": {"name": "alice_dev"}
            }
        }]
    }
    
    response = requests.post(f"{BASE_URL}/webhooks/asana", json=asana_payload)
    print(f"   Event processed: {response.json()}")
    
    # Show timeline
    print("\n4. Current Development Timeline...")
    events = requests.get(f"{BASE_URL}/events?limit=10").json()
    print(f"📡 Total Events: {events['total_events']}")
    
    for i, event in enumerate(events['events'][:5], 1):
        timestamp = datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00'))
        print(f"{i}. [{event['event_type']}] {event['what']}")
        print(f"   👤 {event['who']} | 📅 {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        if event['repository']:
            print(f"   📁 {event['repository']}")
        print()
    
    # Show API endpoints
    print("5. Available Scout API Endpoints...")
    print("📚 Documentation: http://localhost:8000/docs")
    print("🔍 Key Endpoints:")
    print("   - GET  /events           - Timeline of all activity")
    print("   - GET  /rules            - Rule engine status")
    print("   - POST /webhooks/github  - GitHub webhook handler")
    print("   - POST /webhooks/asana   - Asana webhook handler")
    print("   - GET  /health           - System health check")
    
    print("\n🎉 Scout Demo Complete!")
    print("Visit the frontend at http://localhost:5173 to see the UI")

if __name__ == "__main__":
    try:
        demo_scout()
    except requests.ConnectionError:
        print("❌ Error: Scout backend not running at http://localhost:8000")
        print("Start it with: cd backend && python -m app.main")
    except Exception as e:
        print(f"❌ Error: {e}") 