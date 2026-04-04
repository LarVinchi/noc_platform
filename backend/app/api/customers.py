from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.core.db import get_db
from app.models.crm import Customer
from app.schemas.crm import CustomerResponse

router = APIRouter()

@router.get("/", response_model=List[CustomerResponse])
def get_customers(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Retrieve all customers from the database.
    """
    # This uses SQLAlchemy to run: SELECT * FROM customers OFFSET skip LIMIT limit;
    customers = db.query(Customer).offset(skip).limit(limit).all()
    
    if not customers:
        raise HTTPException(status_code=404, detail="No customers found")
    
    return customers