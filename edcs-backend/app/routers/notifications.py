from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=List[schemas.NotificationOut])
def list_notifications(db: Session = Depends(get_db)):
    return db.query(models.Notification).order_by(models.Notification.created_at.desc()).all()


@router.patch("/{notification_id}/read", response_model=schemas.NotificationOut)
def mark_read(notification_id: str, db: Session = Depends(get_db)):
    n = db.get(models.Notification, notification_id)
    if not n:
        raise HTTPException(404, "Notification not found")
    n.read = True
    db.commit()
    db.refresh(n)
    return n


@router.post("/read-all", response_model=List[schemas.NotificationOut])
def mark_all_read(db: Session = Depends(get_db)):
    notifications = db.query(models.Notification).all()
    for n in notifications:
        n.read = True
    db.commit()
    return notifications
