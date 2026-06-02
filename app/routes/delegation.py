from fastapi import APIRouter, HTTPException
from datetime import datetime
import uuid
from app.utils.json_db import read_json, write_json

router = APIRouter(prefix="/delegation", tags=["Delegations"])

@router.get("")
def get_delegations(
    page: int = 1,
    page_size: int = 50,
    status: str = None,
    search: str = None,
    sort_by: str = None
):
    """Get list of delegations with filters and pagination"""
    delegations = read_json("delegations.json")
    
    # Status filter
    if status:
        delegations = [d for d in delegations if d["status"] == status]
    
    # Search filter (by PO number or PS name)
    if search:
        search_lower = search.lower()
        delegations = [
            d for d in delegations
            if search_lower in d.get("po_number", "").lower()
            or search_lower in d.get("delegated_to_name", "").lower()
        ]
    
    # Sorting
    if sort_by == "date_asc":
        delegations = sorted(delegations, key=lambda x: x.get("start_date", ""))
    elif sort_by == "date_desc":
        delegations = sorted(delegations, key=lambda x: x.get("start_date", ""), reverse=True)
    else:
        # Default: latest first
        delegations = sorted(delegations, key=lambda x: x.get("created_date", ""), reverse=True)
    
    total = len(delegations)
    start = (page - 1) * page_size
    end = start + page_size
    
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "data": delegations[start:end]
    }

@router.get("/{delegation_id}")
def get_delegation(delegation_id: str):
    """Get a specific delegation by ID"""
    delegations = read_json("delegations.json")
    delegation = next((d for d in delegations if d["id"] == delegation_id), None)
    
    if not delegation:
        raise HTTPException(status_code=404, detail="Delegation not found")
    
    return delegation

@router.post("")
def create_delegation(delegation_data: dict):
    """Create a new delegation"""
    delegations = read_json("delegations.json")
    
    # Generate ID and set created_date
    delegation_data["id"] = f"DEL-{str(uuid.uuid4()).split('-')[0].upper()}"
    delegation_data["created_date"] = datetime.now().isoformat()
    delegation_data["status"] = "DRAFT"
    
    delegations.append(delegation_data)
    write_json("delegations.json", delegations)
    
    return delegation_data

@router.delete("/{delegation_id}")
def delete_delegation(delegation_id: str):
    """Delete a delegation"""
    delegations = read_json("delegations.json")
    
    delegation = next((d for d in delegations if d["id"] == delegation_id), None)
    if not delegation:
        raise HTTPException(status_code=404, detail="Delegation not found")
    
    delegations = [d for d in delegations if d["id"] != delegation_id]
    write_json("delegations.json", delegations)
    
    return {"message": "Delegation removed successfully"}

@router.put("/{delegation_id}")
def update_delegation(delegation_id: str, updated_data: dict):
    """Update a delegation"""
    delegations = read_json("delegations.json")
    
    for index, delegation in enumerate(delegations):
        if delegation["id"] == delegation_id:
            delegations[index].update(updated_data)
            write_json("delegations.json", delegations)
            return delegations[index]
    
    raise HTTPException(status_code=404, detail="Delegation not found")
