#!/usr/bin/env python3
"""Demo client to test the provisioning API"""

import requests
import time

API_URL = "http://localhost:8000"

def demo():
    print("\n" + "=" * 80)
    print("SELF-SERVICE DB PROVISIONING - DEMO")
    print("=" * 80)
    
    # Request 1
    print("\nPHASE 1: Submit Database Requests")
    print("-" * 80)
    
    requests_data = [
        {
            "team_name": "data-engineering",
            "db_type": "postgres",
            "environment": "prod",
            "size": "large",
            "purpose": "Analytics warehouse"
        },
        {
            "team_name": "backend-team",
            "db_type": "mysql",
            "environment": "dev",
            "size": "small",
            "purpose": "Development testing"
        },
        {
            "team_name": "cache-team",
            "db_type": "redis",
            "environment": "staging",
            "size": "medium",
            "purpose": "Session caching"
        }
    ]
    
    request_ids = []
    for req in requests_data:
        response = requests.post(f"{API_URL}/requests", json=req)
        result = response.json()
        request_ids.append(result['request_id'])
        print(f"  Created: {req['team_name']} - {req['db_type']} ({req['size']})")
        print(f"    Request ID: {result['request_id']}")
    
    time.sleep(2)
    
    # List pending
    print("\nPHASE 2: View Pending Requests")
    print("-" * 80)
    response = requests.get(f"{API_URL}/requests?status=pending")
    pending = response.json()['requests']
    print(f"  Pending requests: {len(pending)}")
    for req in pending:
        print(f"    {req['team_name']}: {req['db_type']} ({req['environment']})")
    
    time.sleep(2)
    
    # Approve
    print("\nPHASE 3: Approve Requests")
    print("-" * 80)
    for req_id in request_ids[:2]:  # Approve first 2
        approval = {
            "request_id": req_id,
            "action": "approve",
            "approver": "john.doe@company.com",
            "notes": "Approved - meets requirements"
        }
        response = requests.post(f"{API_URL}/approve", json=approval)
        result = response.json()
        print(f"  Approved: {req_id[:8]}... - {result['status']}")
    
    # Reject one
    rejection = {
        "request_id": request_ids[2],
        "action": "reject",
        "approver": "jane.smith@company.com",
        "notes": "Insufficient justification"
    }
    response = requests.post(f"{API_URL}/approve", json=rejection)
    print(f"  Rejected: {request_ids[2][:8]}...")
    
    time.sleep(2)
    
    # List databases
    print("\nPHASE 4: View Provisioned Databases")
    print("-" * 80)
    response = requests.get(f"{API_URL}/databases")
    data = response.json()
    databases = data['databases']
    
    print(f"  Total databases: {data['total_count']}")
    print(f"  Total monthly cost: ${data['total_monthly_cost']}")
    print("\n  Databases:")
    for db in databases:
        print(f"    {db['db_name']}")
        print(f"      Type: {db['db_type']} | Env: {db['environment']}")
        print(f"      Cost: ${db['estimated_monthly_cost']}/month")
        print(f"      Connection: {db['host']}:{db['port']}")
    
    print("\n" + "=" * 80)
    print("DEMO COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    time.sleep(3)  # Wait for API to start
    demo()
