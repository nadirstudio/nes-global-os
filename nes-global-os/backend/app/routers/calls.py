"""Voice & video calls for the NES Team app.

Signalling runs over one WebSocket per phone (/api/ws). Media (voice/video) flows directly between phones with
WebRTC: on office Wi-Fi that needs no SIM and no internet; outside the office it travels through Tailscale.
Group calls are a full mesh, capped at MAX_GROUP participants.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy import func, or_, select

from .. import models as m
from ..config import settings
from ..db import SessionLocal
from ..deps import Ctx, current_ctx
from ..realtime import hub, online_ids_sync
from ..security import decode_token
from .mobile import _user_name, can_access_channel

router = APIRouter(tags=["calls"])

MAX_GROUP = int(os.getenv("NES_CALL_MAX_GROUP", "6"))
RING_SECONDS = int(os.getenv("NES_CALL_RING_SECONDS", "40"))
MAX_MSGS_PER_10S = 400


def _now() -> datetime:
    return datetime.now(timezone.utc)


def ice_servers() -> list:
    """Default: none. Phones on the same Wi-Fi or tailnet connect directly. A TURN server can be added later."""
    try:
        return json.loads(os.getenv("NES_ICE_SERVERS", "[]"))
    except json.JSONDecodeError:
        return []


# ================================================================ REST
@router.post("/mobile/calls/ticket")
def ticket(ctx: Ctx = Depends(current_ctx)):
    """Short-lived ticket for opening the WebSocket (keeps the long-lived token out of URLs and logs)."""
    exp = _now() + timedelta(seconds=60)
    t = jwt.encode({"sub": str(ctx.user.id), "tv": ctx.user.token_version, "typ": "ws",
                    "did": str(ctx.device.id) if ctx.device else None, "exp": int(exp.timestamp())},
                   settings.jwt_secret, algorithm="HS256")
    return {"ticket": t, "ice_servers": ice_servers(), "max_group": MAX_GROUP, "ring_seconds": RING_SECONDS}


@router.get("/mobile/presence")
def presence(ctx: Ctx = Depends(current_ctx)):
    return {"online_user_ids": sorted(online_ids_sync())}


def _summary(db, call: m.Call, me: uuid.UUID | None = None) -> dict:
    parts = list(db.scalars(select(m.CallParticipant).where(m.CallParticipant.call_id == call.id)))
    title = None
    if call.channel_id:
        ch = db.get(m.ChatChannel, call.channel_id)
        title = ch.name if ch else None
    return {"id": str(call.id), "kind": call.kind, "media": call.media, "status": call.status,
            "title": title, "initiator": {"user_id": str(call.initiator_user_id), "name": _user_name(db, call.initiator_user_id)},
            "started_at": call.started_at.isoformat(),
            "participants": [{"user_id": str(p.user_id), "name": _user_name(db, p.user_id), "state": p.state} for p in parts]}


@router.get("/mobile/calls")
def history(ctx: Ctx = Depends(current_ctx)):
    db = ctx.db
    q = (select(m.Call, m.CallParticipant).join(m.CallParticipant, m.CallParticipant.call_id == m.Call.id)
         .where(m.CallParticipant.user_id == ctx.user.id).order_by(m.Call.started_at.desc()).limit(60))
    out = []
    for call, me in db.execute(q):
        others = [p for p in db.scalars(select(m.CallParticipant).where(m.CallParticipant.call_id == call.id,
                                                                         m.CallParticipant.user_id != ctx.user.id))]
        outgoing = call.initiator_user_id == ctx.user.id
        if me.state == "missed":
            result = "missed"
        elif me.state == "declined":
            result = "declined"
        elif outgoing and not call.answered_at:
            result = "no answer" if call.status in {"missed", "cancelled", "ended"} else call.status
        else:
            result = "answered" if me.joined_at else call.status
        dur = None
        if me.joined_at and (me.left_at or call.ended_at):
            dur = int(((me.left_at or call.ended_at) - me.joined_at).total_seconds())
        ch = db.get(m.ChatChannel, call.channel_id) if call.channel_id else None
        out.append({"id": str(call.id), "kind": call.kind, "media": call.media, "outgoing": outgoing, "result": result,
                    "started_at": call.started_at.isoformat(), "duration_s": dur,
                    "title": ch.name if ch else ", ".join(_user_name(db, p.user_id) for p in others) or "Call",
                    "other_user_id": str(others[0].user_id) if call.kind == "direct" and others else None})
    return out


@router.post("/mobile/calls/seen")
def mark_seen(ctx: Ctx = Depends(current_ctx)):
    for p in ctx.db.scalars(select(m.CallParticipant).where(m.CallParticipant.user_id == ctx.user.id,
                                                            m.CallParticipant.seen.is_(False))):
        p.seen = True
    ctx.db.commit()
    return {"ok": True}


def missed_unseen(db, user_id) -> int:
    return db.scalar(select(func.count()).where(m.CallParticipant.user_id == user_id,
                                                m.CallParticipant.state == "missed",
                                                m.CallParticipant.seen.is_(False))) or 0


# ================================================================ call state (sync, run in a thread)
class CallError(Exception):
    pass


def _auth_ticket(token: str | None):
    p = decode_token(token) if token else None
    if not p or p.get("typ") != "ws":
        return None
    with SessionLocal() as db:
        u = db.get(m.User, uuid.UUID(p["sub"]))
        if not u or not u.is_active or u.token_version != p.get("tv"):
            return None
        if p.get("did"):
            d = db.get(m.Device, uuid.UUID(p["did"]))
            if not d or d.revoked_at:
                return None
        return u.id, _user_name(db, u.id)


def _start(user_id, to: list[str], channel_id: str | None, media: str) -> tuple[dict, list[str]]:
    if media not in {"audio", "video"}:
        raise CallError("media must be audio or video")
    with SessionLocal() as db:
        me = db.get(m.User, user_id)
        targets: list[uuid.UUID] = []
        ch = None
        if channel_id:
            ch = db.get(m.ChatChannel, uuid.UUID(channel_id))
            from ..permissions import scope_for
            from ..deps import Ctx as _Ctx
            if not ch or not can_access_channel(_Ctx(user=me, scope=scope_for(db, me), db=db, ip=""), ch):
                raise CallError("You are not in this group")
            targets = _channel_user_ids(db, ch)
        else:
            targets = [uuid.UUID(t) for t in to]
        targets = [t for t in dict.fromkeys(targets) if t != user_id]
        users = [db.get(m.User, t) for t in targets]
        targets = [u.id for u in users if u and u.is_active]
        if not targets:
            raise CallError("Nobody to call")
        kind = "group" if (ch is not None and ch.kind != "direct") or len(targets) > 1 else "direct"
        if kind == "group" and media == "video" and len(targets) + 1 > 4:
            media = "audio"  # video mesh beyond 4 phones is too heavy; groups fall back to voice
        call = m.Call(kind=kind, media=media, channel_id=ch.id if ch else None, initiator_user_id=user_id)
        db.add(call)
        db.flush()
        db.add(m.CallParticipant(call_id=call.id, user_id=user_id, state="joined", joined_at=_now()))
        for t in targets:
            db.add(m.CallParticipant(call_id=call.id, user_id=t, state="ringing"))
        db.commit()
        return _summary(db, call), [str(t) for t in targets]


def _channel_user_ids(db, ch: m.ChatChannel) -> list[uuid.UUID]:
    if ch.kind in {"direct", "group"}:
        return list(db.scalars(select(m.ChatMember.user_id).where(m.ChatMember.channel_id == ch.id)))
    q = select(m.User.id).join(m.Person, m.Person.id == m.User.person_id).where(m.User.is_active.is_(True),
                                                                                 m.Person.status != "inactive")
    if ch.kind == "department":
        q = q.where(m.Person.department_id == ch.department_id)
    elif ch.kind == "company":
        q = q.where(m.Person.company_id == ch.company_id)
    return list(db.scalars(q))


def _get(db, call_id: str):
    try:
        call = db.get(m.Call, uuid.UUID(call_id))
    except ValueError:
        call = None
    if not call:
        raise CallError("Call not found")
    return call


def _part(db, call, user_id):
    p = db.get(m.CallParticipant, (call.id, user_id))
    if not p:
        raise CallError("You are not in this call")
    return p


def _accept(user_id, call_id: str) -> tuple[dict, list[str], list[str]]:
    with SessionLocal() as db:
        call = _get(db, call_id)
        if call.status not in {"ringing", "active"}:
            raise CallError("This call has ended")
        p = _part(db, call, user_id)
        if p.state == "joined":
            raise CallError("Already in the call")
        joined = list(db.scalars(select(m.CallParticipant).where(m.CallParticipant.call_id == call.id,
                                                                 m.CallParticipant.state == "joined")))
        if len(joined) >= MAX_GROUP:
            raise CallError(f"This group call is full ({MAX_GROUP} people)")
        p.state, p.joined_at, p.left_at, p.seen = "joined", _now(), None, True
        if call.status == "ringing":
            call.status, call.answered_at = "active", _now()
        db.commit()
        everyone = [str(x.user_id) for x in db.scalars(select(m.CallParticipant).where(m.CallParticipant.call_id == call.id))]
        return _summary(db, call), [str(x.user_id) for x in joined], everyone


def _finish(db, call, status: str, reason: str):
    call.status, call.ended_at, call.end_reason = status, _now(), reason
    for x in db.scalars(select(m.CallParticipant).where(m.CallParticipant.call_id == call.id)):
        if x.state == "ringing":
            x.state, x.seen = "missed", False
        elif x.state == "joined":
            x.state, x.left_at = "left", _now()


def _decline(user_id, call_id: str) -> tuple[dict, list[str], bool]:
    with SessionLocal() as db:
        call = _get(db, call_id)
        p = _part(db, call, user_id)
        if p.state != "ringing":
            raise CallError("Nothing to decline")
        p.state = "declined"
        db.flush()
        parts = list(db.scalars(select(m.CallParticipant).where(m.CallParticipant.call_id == call.id)))
        ended = False
        if not any(x.state == "ringing" for x in parts) and sum(x.state == "joined" for x in parts) <= 1:
            _finish(db, call, "declined", "declined")
            ended = True
        db.commit()
        return _summary(db, call), [str(x.user_id) for x in parts if x.user_id != user_id], ended


def _hangup(user_id, call_id: str) -> tuple[dict, list[str], bool]:
    with SessionLocal() as db:
        call = _get(db, call_id)
        p = _part(db, call, user_id)
        if call.status not in {"ringing", "active"}:
            return _summary(db, call), [], True
        if p.state == "ringing":  # an invitee hanging up before answering = decline
            db.rollback()
            s, others, ended = _decline(user_id, call_id)
            return s, others, ended
        p.state, p.left_at = "left", _now()
        db.flush()
        parts = list(db.scalars(select(m.CallParticipant).where(m.CallParticipant.call_id == call.id)))
        still = [x for x in parts if x.state == "joined"]
        ringing = [x for x in parts if x.state == "ringing"]
        ended = False
        if call.status == "ringing" and user_id == call.initiator_user_id:
            _finish(db, call, "cancelled", "caller hung up")
            ended = True
        elif len(still) <= 1 and (call.kind == "direct" or not ringing or len(still) == 0):
            _finish(db, call, "ended", "hung up")
            ended = True
        db.commit()
        return _summary(db, call), [str(x.user_id) for x in parts if x.user_id != user_id], ended


def _ring_timeout(call_id: str) -> tuple[dict | None, list[str]]:
    with SessionLocal() as db:
        call = _get(db, call_id)
        parts = list(db.scalars(select(m.CallParticipant).where(m.CallParticipant.call_id == call.id)))
        if call.status == "ringing":
            _finish(db, call, "missed", "no answer")
            db.commit()
            return _summary(db, call), [str(x.user_id) for x in parts]
        if call.status == "active":  # group call: stop ringing the people who never answered
            changed = [x for x in parts if x.state == "ringing"]
            for x in changed:
                x.state, x.seen = "missed", False
            db.commit()
            return (_summary(db, call), [str(x.user_id) for x in parts]) if changed else (None, [])
        return None, []


def _can_relay(user_id, call_id: str, to: str) -> bool:
    with SessionLocal() as db:
        try:
            call = db.get(m.Call, uuid.UUID(call_id))
            a = db.get(m.CallParticipant, (uuid.UUID(call_id), user_id))
            b = db.get(m.CallParticipant, (uuid.UUID(call_id), uuid.UUID(to)))
        except ValueError:
            return False
        return bool(call and call.status in {"ringing", "active"} and a and b
                    and a.state == "joined" and b.state in {"joined", "ringing"})


def cleanup_stale_calls() -> int:
    """On start-up: calls left ringing/active by a restart are closed."""
    with SessionLocal() as db:
        n = 0
        stale = _now() - timedelta(seconds=RING_SECONDS * 3)
        for c in db.scalars(select(m.Call).where(m.Call.status == "ringing", m.Call.started_at < stale)):
            _finish(db, c, "missed", "server restart")
            n += 1
        # active calls with no signal for 6 hours are certainly over
        for c in db.scalars(select(m.Call).where(m.Call.status == "active", m.Call.started_at < _now() - timedelta(hours=6))):
            _finish(db, c, "ended", "stale")
            n += 1
        db.commit()
        return n


# ================================================================ WebSocket
async def _ring_watch(call_id: str) -> None:
    await asyncio.sleep(RING_SECONDS)
    try:
        summary, recipients = await asyncio.to_thread(_ring_timeout, call_id)
    except CallError:
        return
    if summary:
        await hub.send(recipients, {"type": "call.update" if summary["status"] == "active" else "call.ended",
                                    "call": summary, "reason": "no answer"})


@router.websocket("/ws")
async def ws(websocket: WebSocket, ticket: str | None = Query(default=None)):
    who = await asyncio.to_thread(_auth_ticket, ticket)
    if not who:
        await websocket.close(code=4401)
        return
    user_id, name = who
    await websocket.accept()
    hub.add(user_id, websocket)
    await hub.touch(user_id)
    await websocket.send_json({"type": "hello", "user_id": str(user_id), "name": name, "server_time": _now().isoformat()})
    window, count = time.time(), 0
    try:
        while True:
            msg = await websocket.receive_json()
            count += 1
            if time.time() - window > 10:
                window, count = time.time(), 0
            if count > MAX_MSGS_PER_10S:
                await websocket.send_json({"type": "error", "message": "Too many messages"})
                continue
            t = msg.get("type")
            try:
                if t == "ping":
                    await hub.touch(user_id)
                    await websocket.send_json({"type": "pong"})
                elif t == "call.start":
                    summary, targets = await asyncio.to_thread(_start, user_id, msg.get("to") or [], msg.get("channel_id"),
                                                               msg.get("media", "audio"))
                    await websocket.send_json({"type": "call.created", "call": summary, "ref": msg.get("ref")})
                    await hub.send(targets, {"type": "call.incoming", "call": summary})
                    asyncio.create_task(_ring_watch(summary["id"]))
                elif t == "call.accept":
                    summary, joined, everyone = await asyncio.to_thread(_accept, user_id, msg["call_id"])
                    # the newcomer will send offers to everyone already in the call
                    await websocket.send_json({"type": "call.joined", "call": summary, "peers": joined})
                    await hub.send([u for u in everyone if u != str(user_id)],
                                   {"type": "call.update", "call": summary, "joined": str(user_id)})
                    await hub.send([str(user_id)], {"type": "call.answered_elsewhere", "call_id": summary["id"]})
                elif t == "call.decline":
                    summary, others, ended = await asyncio.to_thread(_decline, user_id, msg["call_id"])
                    await hub.send(others + [str(user_id)], {"type": "call.ended" if ended else "call.update",
                                                             "call": summary, "reason": "declined"})
                elif t == "call.hangup":
                    summary, others, ended = await asyncio.to_thread(_hangup, user_id, msg["call_id"])
                    await hub.send(others + [str(user_id)], {"type": "call.ended" if ended else "call.update",
                                                             "call": summary, "left": str(user_id)})
                elif t in {"rtc.offer", "rtc.answer", "rtc.ice"}:
                    to = str(msg.get("to", ""))
                    if await asyncio.to_thread(_can_relay, user_id, msg.get("call_id", ""), to):
                        await hub.send([to], {"type": t, "call_id": msg["call_id"], "from": str(user_id),
                                              "data": msg.get("data")})
                else:
                    await websocket.send_json({"type": "error", "message": f"Unknown message {t}"})
            except CallError as e:
                await websocket.send_json({"type": "error", "message": str(e), "ref": msg.get("ref")})
            except (KeyError, ValueError):
                await websocket.send_json({"type": "error", "message": "Bad message", "ref": msg.get("ref")})
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        hub.remove(user_id, websocket)
        await hub.offline(user_id)
