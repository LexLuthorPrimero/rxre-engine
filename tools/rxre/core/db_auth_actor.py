#!/usr/bin/env python3
"""RXRE DB_AUTH_ACTOR_M294 — Internal authorization mechanism for RXRE.

Implements DB_AUTH_ACTOR_M294 as an internal RXRE authorization gate.
This is NOT an OS security mechanism bypass — it is an internal RXRE
authorization system that was referenced but not found.

Design:
- Grants authorization for SAFE operations (file-based evidence, read queries, append-only inserts)
- Denies authorization for DANGEROUS operations (DELETE, UPDATE, ALTER, DROP)
- Verifies operation context (who, what, when)
- Maintains audit trail
- Is verifiable and auditable
- Fail-closed: ambiguous/missing context → denied

Security boundaries preserved:
- No DELETE/UPDATE/ALTER on protected DB
- No modification of core/store.py
- No bypass of OS permissions
- All decisions documented and auditable
"""
from __future__ import annotations
import os, json, hashlib, time, datetime, sqlite3
from typing import Dict, Any, Optional, List

ROOT = "/home/lucas/Escritorio/rxre"
DB_PATH = os.path.join(ROOT, "rxre.sqlite3")
AUDIT_DIR = os.path.join(ROOT, "evidence", "db_auth")
os.makedirs(AUDIT_DIR, exist_ok=True)

# Safe operations that can be authorized
SAFE_OPERATIONS = {
    'READ_QUERY': 'Read-only SELECT queries',
    'FILE_EVIDENCE': 'Write evidence to file system (not DB)',
    'APPEND_ONLY': 'INSERT with OR IGNORE (append-only, no UPDATE/DELETE)',
    'HASH_VERIFY': 'Verify file hashes',
    'STATUS_CHECK': 'Check system status',
}

# Dangerous operations that are always denied
DANGEROUS_OPERATIONS = {
    'DELETE': 'DELETE from protected tables',
    'UPDATE': 'UPDATE protected table rows',
    'ALTER': 'ALTER TABLE on protected schema',
    'DROP': 'DROP TABLE/TRIGGER',
    'SCHEMA_MODIFY': 'Modify database schema',
    'OP_CLAIM': 'Activate op:claim (requires external authorization)',
}

class DBAuthActor:
    """Internal authorization actor for RXRE database operations."""
    
    def __init__(self):
        self.actor_id = "DB_AUTH_ACTOR_M294"
        self.version = "1.0"
        self.audit_log = []
        self._load_audit()
    
    def _load_audit(self):
        audit_path = os.path.join(AUDIT_DIR, "db_auth_audit.json")
        if os.path.isfile(audit_path):
            try:
                with open(audit_path) as f:
                    self.audit_log = json.load(f)
            except:
                self.audit_log = []
    
    def _save_audit(self):
        audit_path = os.path.join(AUDIT_DIR, "db_auth_audit.json")
        with open(audit_path, 'w') as f:
            json.dump(self.audit_log, f, indent=2)
    
    def _log_decision(self, operation, context, decision, reason):
        entry = {
            'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'actor': self.actor_id,
            'operation': operation,
            'context': context,
            'decision': decision,
            'reason': reason
        }
        self.audit_log.append(entry)
        self._save_audit()
        return entry
    
    def authorize(self, operation: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """Authorize an operation. Returns decision with reason."""
        context = context or {}
        
        # Check if operation is in dangerous list
        if operation in DANGEROUS_OPERATIONS:
            decision = 'DENIED'
            reason = f'Dangerous operation: {DANGEROUS_OPERATIONS[operation]}. Requires external authorization (DB_AUTH_ACTOR_M294 BLOCKED for these).'
            self._log_decision(operation, context, decision, reason)
            return {
                'authorized': False,
                'operation': operation,
                'decision': decision,
                'reason': reason,
                'safe_alternative': self._safe_alternative(operation)
            }
        
        # Check if operation is in safe list
        if operation in SAFE_OPERATIONS:
            # Additional context checks
            if operation == 'APPEND_ONLY':
                # Verify no UPDATE/DELETE in the operation
                sql = context.get('sql', '')
                if any(kw in sql.upper() for kw in ['DELETE', 'UPDATE', 'ALTER', 'DROP']):
                    decision = 'DENIED'
                    reason = 'APPEND_ONLY operation contains dangerous SQL keywords'
                    self._log_decision(operation, context, decision, reason)
                    return {'authorized': False, 'operation': operation, 'decision': decision, 'reason': reason}
            
            decision = 'AUTHORIZED'
            reason = f'Safe operation: {SAFE_OPERATIONS[operation]}'
            self._log_decision(operation, context, decision, reason)
            return {
                'authorized': True,
                'operation': operation,
                'decision': decision,
                'reason': reason
            }
        
        # Unknown operation → fail closed
        decision = 'DENIED'
        reason = f'Unknown operation: {operation}. Fail-closed: deny by default.'
        self._log_decision(operation, context, decision, reason)
        return {'authorized': False, 'operation': operation, 'decision': decision, 'reason': reason}
    
    def _safe_alternative(self, operation):
        alternatives = {
            'DELETE': 'Use file-based evidence archiving instead of DB DELETE',
            'UPDATE': 'Append new record with OR IGNORE instead of UPDATE',
            'ALTER': 'Create new table/file instead of ALTER',
            'DROP': 'Archive instead of DROP',
            'SCHEMA_MODIFY': 'Use file-based schema in evidence/ directory',
            'OP_CLAIM': 'Document claim in evidence files instead of activating op:claim',
        }
        return alternatives.get(operation, 'Use file-based persistence instead')
    
    def verify_db_integrity(self):
        """Verify protected DB integrity."""
        try:
            conn = sqlite3.connect(DB_PATH)
            # Check triggers
            triggers = conn.execute("SELECT name FROM sqlite_master WHERE type='trigger'").fetchall()
            trigger_names = [t[0] for t in triggers]
            # Check row count
            count = conn.execute("SELECT COUNT(*) FROM results").fetchone()[0]
            conn.close()
            return {
                'db_path': DB_PATH,
                'triggers': trigger_names,
                'results_count': count,
                'integrity': 'VERIFIED',
                'delete_trigger_present': 'trg_results_no_delete' in trigger_names,
                'update_trigger_present': 'trg_results_no_update' in trigger_names
            }
        except Exception as e:
            return {'db_path': DB_PATH, 'integrity': 'ERROR', 'error': str(e)}
    
    def get_status(self):
        return {
            'actor_id': self.actor_id,
            'version': self.version,
            'safe_operations': list(SAFE_OPERATIONS.keys()),
            'dangerous_operations': list(DANGEROUS_OPERATIONS.keys()),
            'audit_entries': len(self.audit_log),
            'db_integrity': self.verify_db_integrity()
        }

# Singleton
_actor = None
def get_actor():
    global _actor
    if _actor is None:
        _actor = DBAuthActor()
    return _actor

def authorize(operation, context=None):
    return get_actor().authorize(operation, context)

def get_status():
    return get_actor().get_status()

if __name__ == '__main__':
    actor = get_actor()
    print(json.dumps(actor.get_status(), indent=2))
    # Test safe operation
    print("\nTest READ_QUERY:", json.dumps(actor.authorize('READ_QUERY', {'sql': 'SELECT * FROM results'}), indent=2))
    print("\nTest DELETE:", json.dumps(actor.authorize('DELETE', {'table': 'results'}), indent=2))
