"""Voice/video call signalling over WebSocket."""
import time

import pytest
from starlette.websockets import WebSocketDisconnect

from app.routers.calls import _can_relay
from conftest import PW


def mlogin(client, code, install=None):
    r = client.post("/api/mobile/login", json={"email": f"{code.lower()}@t.test", "password": PW, "install_id": install or f"call-{code}"})
    return {"authorization": f"Bearer {r.json()['token']}"}


def connect(client, h):
    t = client.post("/api/mobile/calls/ticket", headers=h).json()
    assert t["max_group"] == 6 and t["ice_servers"] == []
    ws = client.websocket_connect(f"/api/ws?ticket={t['ticket']}")
    ws.__enter__()
    hello = ws.receive_json()
    assert hello["type"] == "hello"
    return ws, hello["user_id"]


def recv(ws, type_, where=None):
    for _ in range(12):
        msg = ws.receive_json()
        if msg["type"] == type_ and (where is None or where(msg)):
            return msg
    raise AssertionError(f"no {type_}")


def test_rejects_bad_tickets(client):
    with pytest.raises(WebSocketDisconnect) as e:
        with client.websocket_connect("/api/ws?ticket=forged") as ws:
            ws.receive_json()
    assert e.value.code == 4401
    h = mlogin(client, "EMP1")
    # a normal session token is not a WebSocket ticket
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/api/ws?ticket={h['authorization'][7:]}") as ws:
            ws.receive_json()


def test_direct_call_answer_relay_hangup_history(client):
    a_h, b_h = mlogin(client, "EMP1"), mlogin(client, "CONS1")
    a, a_id = connect(client, a_h)
    b, b_id = connect(client, b_h)
    try:
        online = client.get("/api/mobile/presence", headers=a_h).json()["online_user_ids"]
        assert a_id in online and b_id in online
        assert next(p for p in client.get("/api/mobile/directory", headers=a_h).json() if p["user_id"] == b_id)["online"]
        a.send_json({"type": "call.start", "to": [b_id], "media": "video", "ref": "r1"})
        created = recv(a, "call.created")
        call_id = created["call"]["id"]
        assert created["call"]["kind"] == "direct" and created["call"]["media"] == "video"
        inc = recv(b, "call.incoming")
        assert inc["call"]["id"] == call_id and inc["call"]["initiator"]["name"] == "DM Employee"
        b.send_json({"type": "call.accept", "call_id": call_id})
        joined = recv(b, "call.joined")
        assert joined["peers"] == [a_id] and joined["call"]["status"] == "active"
        assert recv(a, "call.update")["joined"] == b_id
        # newcomer offers, caller answers, ICE both ways
        b.send_json({"type": "rtc.offer", "call_id": call_id, "to": a_id, "data": {"sdp": "v=0 fake"}})
        off = recv(a, "rtc.offer")
        assert off["from"] == b_id and off["data"]["sdp"] == "v=0 fake"
        a.send_json({"type": "rtc.answer", "call_id": call_id, "to": b_id, "data": {"sdp": "answer"}})
        assert recv(b, "rtc.answer")["data"]["sdp"] == "answer"
        a.send_json({"type": "rtc.ice", "call_id": call_id, "to": b_id, "data": {"candidate": "x"}})
        assert recv(b, "rtc.ice")["from"] == a_id
        # outsiders can't inject media signalling
        from conftest import login
        import uuid
        from app.db import SessionLocal
        from app import models as m
        from sqlalchemy import select
        with SessionLocal() as db:
            beg = db.scalar(select(m.User).where(m.User.email == "beg1@t.test"))
            assert not _can_relay(beg.id, call_id, a_id)
            assert _can_relay(uuid.UUID(b_id), call_id, a_id)
        time.sleep(1.1)
        a.send_json({"type": "call.hangup", "call_id": call_id})
        assert recv(b, "call.ended")["call"]["status"] == "ended"
        assert recv(a, "call.ended")["call"]["status"] == "ended"
        ha = client.get("/api/mobile/calls", headers=a_h).json()[0]
        hb = client.get("/api/mobile/calls", headers=b_h).json()[0]
        assert ha["outgoing"] and ha["result"] == "answered" and ha["duration_s"] >= 1 and ha["title"] == "Consultancy Employee"
        assert not hb["outgoing"] and hb["result"] == "answered" and hb["other_user_id"] == a_id
        # relay after the call ended is refused
        assert not _can_relay(uuid.UUID(b_id), call_id, a_id)
    finally:
        a.__exit__(None, None, None)
        b.__exit__(None, None, None)


def test_decline_and_missed(client):
    a_h, b_h, c_h = mlogin(client, "EMP1"), mlogin(client, "CONS1"), mlogin(client, "BEG1")
    a, a_id = connect(client, a_h)
    b, b_id = connect(client, b_h)
    beg_id = next(p["user_id"] for p in client.get("/api/mobile/directory", headers=a_h).json() if p["name"] == "DM Beginner")
    try:
        a.send_json({"type": "call.start", "to": [b_id], "media": "audio"})
        cid = recv(a, "call.created")["call"]["id"]
        recv(b, "call.incoming")
        b.send_json({"type": "call.decline", "call_id": cid})
        ended = recv(a, "call.ended")
        assert ended["call"]["status"] == "declined" and ended["reason"] == "declined"
        # BEG1 is offline → rings out → missed
        a.send_json({"type": "call.start", "to": [beg_id], "media": "audio"})
        cid2 = recv(a, "call.created")["call"]["id"]
        ended = recv(a, "call.ended")  # after NES_CALL_RING_SECONDS=2
        assert ended["call"]["id"] == cid2 and ended["call"]["status"] == "missed"
        hist = client.get("/api/mobile/calls", headers=c_h).json()
        assert hist[0]["result"] == "missed" and not hist[0]["outgoing"]
        assert client.get("/api/mobile/home", headers=c_h).json()["missed_calls"] == 1
        assert client.get("/api/mobile/sync", headers=c_h).json()["missed_calls"] == 1
        client.post("/api/mobile/calls/seen", headers=c_h)
        assert client.get("/api/mobile/home", headers=c_h).json()["missed_calls"] == 0
        assert client.get("/api/mobile/calls", headers=a_h).json()[0]["result"] == "no answer"
        # caller cancels while ringing
        a.send_json({"type": "call.start", "to": [b_id], "media": "audio"})
        cid3 = recv(a, "call.created")["call"]["id"]
        recv(b, "call.incoming")
        a.send_json({"type": "call.hangup", "call_id": cid3})
        assert recv(b, "call.ended")["call"]["status"] == "cancelled"
        assert client.get("/api/mobile/calls", headers=b_h).json()[0]["result"] == "missed"
    finally:
        a.__exit__(None, None, None)
        b.__exit__(None, None, None)


def test_group_call_from_department_channel(client):
    a_h, b_h, c_h = mlogin(client, "EMP1"), mlogin(client, "BEG1"), mlogin(client, "HEADSALES")
    a, a_id = connect(client, a_h)
    b, b_id = connect(client, b_h)
    c, c_id = connect(client, c_h)
    try:
        dept = next(ch for ch in client.get("/api/mobile/chat/channels", headers=a_h).json() if ch["kind"] == "department")
        a.send_json({"type": "call.start", "channel_id": dept["id"], "media": "audio"})
        call = recv(a, "call.created")["call"]
        assert call["kind"] == "group" and call["title"] == "Sales"
        assert {p["user_id"] for p in call["participants"]} >= {a_id, b_id, c_id}
        recv(b, "call.incoming"); recv(c, "call.incoming")
        b.send_json({"type": "call.accept", "call_id": call["id"]})
        assert recv(b, "call.joined")["peers"] == [a_id]
        c.send_json({"type": "call.accept", "call_id": call["id"]})
        assert set(recv(c, "call.joined")["peers"]) == {a_id, b_id}   # third person offers to both
        b.send_json({"type": "call.hangup", "call_id": call["id"]})     # one leaves, call continues
        upd = recv(a, "call.update", lambda x: "left" in x)
        assert upd["left"] == b_id and upd["call"]["status"] == "active"
        c.send_json({"type": "call.hangup", "call_id": call["id"]})
        assert recv(a, "call.ended")["call"]["status"] == "ended"
        # consultancy staff can't start a call in the DM sales group
        x_h = mlogin(client, "CONS1")
        x, _ = connect(client, x_h)
        x.send_json({"type": "call.start", "channel_id": dept["id"], "media": "audio", "ref": "q"})
        err = recv(x, "error")
        assert "not in this group" in err["message"]
        x.__exit__(None, None, None)
    finally:
        for w in (a, b, c):
            w.__exit__(None, None, None)
