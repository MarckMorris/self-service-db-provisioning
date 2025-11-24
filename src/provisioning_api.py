#!/usr/bin/env python3
"""
Self-Service Database Provisioning Platform
REST API for on-demand database provisioning
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import psycopg2
import uuid
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Self-Service DB Provisioning API", version="1.0.0")


class DatabaseRequest(BaseModel):
    team_name: str
    db_type: str  # postgres, mysql, redis
    environment: str  # dev, staging, prod
    size: str  # small, medium, large
    purpose: str


class ApprovalAction(BaseModel):
    request_id: str
    action: str  # approve, reject
    approver: str
    notes: Optional[str] = None


class ProvisioningService:
    
    def __init__(self):
        self.conn = None
        self.connect()
        self.setup_tables()
    
    def connect(self):
        try:
            self.conn = psycopg2.connect(
                host='localhost',
                port=5445,
                dbname='provisioning_db',
                user='postgres',
                password='postgres'
            )
            self.conn.autocommit = True
            logger.info("Connected to provisioning database")
        except Exception as e:
            logger.error(f"Connection failed: {e}")
    
    def setup_tables(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS db_requests (
                request_id VARCHAR(36) PRIMARY KEY,
                team_name VARCHAR(100),
                db_type VARCHAR(20),
                environment VARCHAR(20),
                size VARCHAR(20),
                purpose TEXT,
                status VARCHAR(20) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT NOW(),
                approved_at TIMESTAMP,
                provisioned_at TIMESTAMP,
                approver VARCHAR(100),
                approval_notes TEXT
            );
            
            CREATE TABLE IF NOT EXISTS provisioned_databases (
                db_id SERIAL PRIMARY KEY,
                request_id VARCHAR(36) REFERENCES db_requests(request_id),
                db_name VARCHAR(100),
                db_type VARCHAR(20),
                environment VARCHAR(20),
                host VARCHAR(100),
                port INT,
                estimated_cost DECIMAL(10,2),
                status VARCHAR(20) DEFAULT 'active',
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)
        cursor.close()
        logger.info("Tables initialized")
    
    def create_request(self, request: DatabaseRequest) -> dict:
        request_id = str(uuid.uuid4())
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO db_requests 
            (request_id, team_name, db_type, environment, size, purpose, status)
            VALUES (%s, %s, %s, %s, %s, %s, 'pending')
        """, (request_id, request.team_name, request.db_type, 
              request.environment, request.size, request.purpose))
        cursor.close()
        
        logger.info(f"Created request {request_id}")
        
        return {
            'request_id': request_id,
            'status': 'pending',
            'message': 'Request submitted for approval'
        }
    
    def get_requests(self, status: Optional[str] = None) -> List[dict]:
        cursor = self.conn.cursor()
        
        if status:
            cursor.execute("""
                SELECT request_id, team_name, db_type, environment, size, 
                       status, created_at, purpose
                FROM db_requests
                WHERE status = %s
                ORDER BY created_at DESC
            """, (status,))
        else:
            cursor.execute("""
                SELECT request_id, team_name, db_type, environment, size, 
                       status, created_at, purpose
                FROM db_requests
                ORDER BY created_at DESC
                LIMIT 50
            """)
        
        requests = []
        for row in cursor.fetchall():
            requests.append({
                'request_id': row[0],
                'team_name': row[1],
                'db_type': row[2],
                'environment': row[3],
                'size': row[4],
                'status': row[5],
                'created_at': row[6].isoformat() if row[6] else None,
                'purpose': row[7]
            })
        
        cursor.close()
        return requests
    
    def process_approval(self, approval: ApprovalAction) -> dict:
        cursor = self.conn.cursor()
        
        # Check if request exists
        cursor.execute(
            "SELECT status FROM db_requests WHERE request_id = %s",
            (approval.request_id,)
        )
        result = cursor.fetchone()
        
        if not result:
            cursor.close()
            raise HTTPException(status_code=404, detail="Request not found")
        
        if result[0] != 'pending':
            cursor.close()
            raise HTTPException(
                status_code=400, 
                detail=f"Request already {result[0]}"
            )
        
        new_status = 'approved' if approval.action == 'approve' else 'rejected'
        
        cursor.execute("""
            UPDATE db_requests
            SET status = %s, approver = %s, approval_notes = %s, 
                approved_at = NOW()
            WHERE request_id = %s
        """, (new_status, approval.approver, approval.notes, approval.request_id))
        
        # If approved, provision the database
        if approval.action == 'approve':
            self._provision_database(approval.request_id, cursor)
        
        cursor.close()
        
        logger.info(f"Request {approval.request_id} {new_status}")
        
        return {
            'request_id': approval.request_id,
            'status': new_status,
            'message': f'Request {new_status} successfully'
        }
    
    def _provision_database(self, request_id: str, cursor):
        # Get request details
        cursor.execute("""
            SELECT team_name, db_type, environment, size
            FROM db_requests
            WHERE request_id = %s
        """, (request_id,))
        
        team, db_type, env, size = cursor.fetchone()
        
        # Generate database details
        db_name = f"{team}_{env}_{db_type}_{uuid.uuid4().hex[:8]}"
        
        # Size to cost mapping
        cost_map = {
            'small': 50.00,
            'medium': 150.00,
            'large': 500.00
        }
        
        # Port mapping
        port_map = {
            'postgres': 5432,
            'mysql': 3306,
            'redis': 6379
        }
        
        estimated_cost = cost_map.get(size, 100.00)
        port = port_map.get(db_type, 5432)
        
        # Insert provisioned database
        cursor.execute("""
            INSERT INTO provisioned_databases
            (request_id, db_name, db_type, environment, host, port, 
             estimated_cost, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'active')
        """, (request_id, db_name, db_type, env, 'db-cluster.example.com', 
              port, estimated_cost))
        
        # Update request status
        cursor.execute("""
            UPDATE db_requests
            SET status = 'provisioned', provisioned_at = NOW()
            WHERE request_id = %s
        """, (request_id,))
        
        logger.info(f"Provisioned database: {db_name}")
    
    def get_databases(self) -> List[dict]:
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT d.db_id, d.db_name, d.db_type, d.environment, d.host, 
                   d.port, d.estimated_cost, d.status, d.created_at,
                   r.team_name
            FROM provisioned_databases d
            JOIN db_requests r ON d.request_id = r.request_id
            WHERE d.status = 'active'
            ORDER BY d.created_at DESC
        """)
        
        databases = []
        for row in cursor.fetchall():
            databases.append({
                'db_id': row[0],
                'db_name': row[1],
                'db_type': row[2],
                'environment': row[3],
                'host': row[4],
                'port': row[5],
                'estimated_monthly_cost': float(row[6]),
                'status': row[7],
                'created_at': row[8].isoformat() if row[8] else None,
                'team_name': row[9]
            })
        
        cursor.close()
        return databases


# Initialize service
service = ProvisioningService()


# API Endpoints
@app.get("/")
def root():
    return {
        "service": "Self-Service Database Provisioning",
        "version": "1.0.0",
        "endpoints": {
            "POST /requests": "Submit new database request",
            "GET /requests": "List all requests",
            "POST /approve": "Approve/reject request",
            "GET /databases": "List provisioned databases"
        }
    }


@app.post("/requests")
def create_request(request: DatabaseRequest):
    """Submit a new database provisioning request"""
    return service.create_request(request)


@app.get("/requests")
def list_requests(status: Optional[str] = None):
    """List database requests, optionally filtered by status"""
    return {"requests": service.get_requests(status)}


@app.post("/approve")
def approve_request(approval: ApprovalAction):
    """Approve or reject a database request"""
    return service.process_approval(approval)


@app.get("/databases")
def list_databases():
    """List all provisioned databases"""
    databases = service.get_databases()
    total_cost = sum(db['estimated_monthly_cost'] for db in databases)
    
    return {
        "databases": databases,
        "total_count": len(databases),
        "total_monthly_cost": round(total_cost, 2)
    }


if __name__ == "__main__":
    import uvicorn
    print("\nStarting Self-Service DB Provisioning API...")
    print("API Docs: http://localhost:8000/docs")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8000)
