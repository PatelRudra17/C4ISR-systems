from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import joinedload
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from app.core.database import get_db
from app.core.security import encrypt_message, decrypt_message
from app.core.redis_client import publish_event
from app.models.models import Channel, Message, User, ClearanceLevel
from app.routers.auth import get_current_user, require_permission

router = APIRouter(prefix="/api/v1/comms", tags=["Communications"])


class MessageCreate(BaseModel):
    channel_id: str
    plaintext: str
    classification: ClearanceLevel = ClearanceLevel.UNCLASSIFIED


class MessageResponse(BaseModel):
    id: str
    channel_id: str
    sender_callsign: str
    plaintext: str
    classification: str
    sent_at: datetime


class ChannelResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    channel_type: str
    classification: str
    min_role: str
    is_active: bool


@router.get("/channels", response_model=List[ChannelResponse])
async def list_channels(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("comms:r"))
):
    """List all communication channels"""
    result = await db.execute(select(Channel).where(Channel.is_active == True))
    channels = result.scalars().all()

    return [
        ChannelResponse(
            id=str(c.id),
            name=c.name,
            description=c.description,
            channel_type=c.channel_type.value,
            classification=c.classification.value,
            min_role=c.min_role.value,
            is_active=c.is_active
        )
        for c in channels
    ]


@router.post("/send", response_model=MessageResponse)
async def send_message(
    message: MessageCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("comms:rw"))
):
    """Send encrypted message to channel"""
    # Verify channel exists
    result = await db.execute(select(Channel).where(Channel.id == message.channel_id))
    channel = result.scalar_one_or_none()

    if not channel or not channel.is_active:
        raise HTTPException(status_code=404, detail="Channel not found or inactive")

    # Encrypt message with AES-256-CBC
    encrypted = encrypt_message(message.plaintext)

    # Save message to database
    new_message = Message(
        channel_id=message.channel_id,
        sender_id=user.id,
        ciphertext=encrypted["ciphertext"],
        iv=encrypted["iv"],
        classification=message.classification
    )

    db.add(new_message)
    await db.commit()
    await db.refresh(new_message)

    # Publish preview to Redis channel (for real-time updates)
    await publish_event(f"comms.{message.channel_id}", {
        "message_id": str(new_message.id),
        "sender_callsign": user.callsign,
        "preview": message.plaintext[:100],
        "classification": message.classification.value,
        "sent_at": new_message.sent_at.isoformat()
    })

    return MessageResponse(
        id=str(new_message.id),
        channel_id=message.channel_id,
        sender_callsign=user.callsign,
        plaintext=message.plaintext,
        classification=message.classification.value,
        sent_at=new_message.sent_at
    )


@router.get("/{channel_id}/messages", response_model=List[MessageResponse])
async def get_messages(
    channel_id: str,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("comms:r"))
):
    """Get decrypted messages from channel"""
    # Verify channel access
    result = await db.execute(select(Channel).where(Channel.id == channel_id))
    channel = result.scalar_one_or_none()

    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    # Get messages with sender info
    result = await db.execute(
        select(Message)
        .options(joinedload(Message.sender))
        .where(Message.channel_id == channel_id)
        .where(Message.is_deleted == False)
        .order_by(desc(Message.sent_at))
        .limit(limit)
    )
    messages = result.scalars().all()

    # Decrypt each message
    decrypted_messages = []
    for msg in messages:
        try:
            plaintext = decrypt_message(msg.ciphertext, msg.iv)
            decrypted_messages.append(MessageResponse(
                id=str(msg.id),
                channel_id=channel_id,
                sender_callsign=msg.sender.callsign,
                plaintext=plaintext,
                classification=msg.classification.value,
                sent_at=msg.sent_at
            ))
        except Exception as e:
            # Skip messages that fail to decrypt
            continue

    return decrypted_messages
