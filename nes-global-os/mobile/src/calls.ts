// Voice & video calls: one WebSocket to the NES server for signalling, WebRTC directly between phones for media.
// On office Wi-Fi the media never leaves the building (no SIM, no internet). Outside, it travels through Tailscale.
import { api, wsUrl } from "./api";
import { notify } from "./native";

export type Participant = { user_id: string; name: string; state: string };
export type CallSummary = {
  id: string; kind: "direct" | "group"; media: "audio" | "video"; status: string; title: string | null;
  initiator: { user_id: string; name: string }; participants: Participant[]; started_at: string;
};
export type Peer = { user_id: string; name: string; stream: MediaStream | null; conn: string };
export type CallState = {
  phase: "idle" | "outgoing" | "incoming" | "connecting" | "active" | "ended";
  call: CallSummary | null;
  peers: Record<string, Peer>;
  local: MediaStream | null;
  muted: boolean;
  cameraOn: boolean;
  startedAt: number | null;
  info: string | null;
  online: boolean;
};

const IDLE: CallState = {
  phase: "idle", call: null, peers: {}, local: null, muted: false, cameraOn: false,
  startedAt: null, info: null, online: false,
};

class CallManager {
  state: CallState = { ...IDLE };
  me = "";
  private ws: WebSocket | null = null;
  private listeners = new Set<() => void>();
  private pcs = new Map<string, RTCPeerConnection>();
  private pendingIce = new Map<string, RTCIceCandidateInit[]>();
  private ice: RTCIceServer[] = [];
  private pingTimer: any = null;
  private retry = 0;
  private wanted = false;
  private tone: Tone | null = null;
  private endTimer: any = null;
  private facing: "user" | "environment" = "user";

  // ---------------------------------------------------------------- store
  subscribe = (fn: () => void) => { this.listeners.add(fn); return () => this.listeners.delete(fn); };
  getState = () => this.state;
  private set(p: Partial<CallState>) {
    this.state = { ...this.state, ...p };
    this.listeners.forEach((l) => l());
  }

  // ---------------------------------------------------------------- connection
  async connect() {
    this.wanted = true;
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) return;
    let t: any;
    try {
      t = await api<any>("/mobile/calls/ticket", { method: "POST" });
    } catch {
      return this.scheduleReconnect();
    }
    this.ice = t.ice_servers || [];
    const ws = new WebSocket(wsUrl(`/api/ws?ticket=${encodeURIComponent(t.ticket)}`));
    this.ws = ws;
    ws.onopen = () => {
      this.retry = 0;
      this.set({ online: true });
      clearInterval(this.pingTimer);
      this.pingTimer = setInterval(() => this.send({ type: "ping" }), 25000);
    };
    ws.onmessage = (e) => { try { this.onMessage(JSON.parse(e.data)); } catch { /* ignore */ } };
    ws.onclose = () => {
      clearInterval(this.pingTimer);
      if (this.ws === ws) this.ws = null;
      this.set({ online: false });
      if (this.wanted) this.scheduleReconnect();
    };
  }

  private scheduleReconnect() {
    if (!this.wanted) return;
    const delay = Math.min(30000, 1000 * 2 ** this.retry++);
    setTimeout(() => this.connect(), delay);
  }

  disconnect() {
    this.wanted = false;
    if (this.state.call) this.hangup();
    this.ws?.close();
    this.ws = null;
  }

  private send(msg: any) {
    if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(msg));
    else throw new Error("Not connected to the NES server. Check Wi-Fi / Tailscale and try again.");
  }

  // ---------------------------------------------------------------- public actions
  async callUser(userId: string, name: string, media: "audio" | "video") {
    return this.begin({ to: [userId] }, media, name);
  }

  async callGroup(channelId: string, title: string, media: "audio" | "video" = "audio") {
    return this.begin({ channel_id: channelId }, media, title);
  }

  private async begin(target: any, media: "audio" | "video", label: string) {
    if (this.state.phase !== "idle" && this.state.phase !== "ended") throw new Error("You're already in a call.");
    clearTimeout(this.endTimer);
    const local = await this.getMedia(media);
    this.set({ ...IDLE, online: this.state.online, phase: "outgoing", local, cameraOn: media === "video", info: `Calling ${label}…` });
    try {
      this.send({ type: "call.start", media, ...target });
    } catch (e) {
      this.cleanup();
      throw e;
    }
    this.tone = new Tone("ringback");
  }

  async accept(withVideo?: boolean) {
    const c = this.state.call;
    if (!c || this.state.phase !== "incoming") return;
    this.stopTone();
    const media = withVideo === false ? "audio" : c.media;
    try {
      const local = await this.getMedia(media);
      this.set({ local, cameraOn: media === "video", phase: "connecting", info: "Connecting…" });
      this.send({ type: "call.accept", call_id: c.id });
    } catch (e) {
      this.set({ info: (e as Error).message });
      this.decline();
    }
  }

  decline() {
    const c = this.state.call;
    this.stopTone();
    if (c) { try { this.send({ type: "call.decline", call_id: c.id }); } catch { /* offline */ } }
    this.finish("Declined");
  }

  hangup() {
    const c = this.state.call;
    if (c) { try { this.send({ type: "call.hangup", call_id: c.id }); } catch { /* offline */ } }
    this.finish("Call ended");
  }

  toggleMute() {
    const muted = !this.state.muted;
    this.state.local?.getAudioTracks().forEach((t) => (t.enabled = !muted));
    this.set({ muted });
  }

  toggleCamera() {
    const on = !this.state.cameraOn;
    this.state.local?.getVideoTracks().forEach((t) => (t.enabled = on));
    this.set({ cameraOn: on });
  }

  async flipCamera() {
    const local = this.state.local;
    if (!local || !local.getVideoTracks().length) return;
    this.facing = this.facing === "user" ? "environment" : "user";
    try {
      const s = await navigator.mediaDevices.getUserMedia({ video: { facingMode: this.facing, width: 640, height: 480 } });
      const track = s.getVideoTracks()[0];
      for (const pc of this.pcs.values()) {
        const sender = pc.getSenders().find((x) => x.track?.kind === "video");
        await sender?.replaceTrack(track);
      }
      local.getVideoTracks().forEach((t) => { t.stop(); local.removeTrack(t); });
      local.addTrack(track);
      this.set({ local });
    } catch { /* keep current camera */ }
  }

  // ---------------------------------------------------------------- signalling
  private onMessage(msg: any) {
    switch (msg.type) {
      case "hello":
        this.me = msg.user_id;
        break;
      case "call.created":
        if (this.state.phase === "outgoing") this.set({ call: msg.call, info: "Ringing…" });
        break;
      case "call.incoming": {
        if (this.state.phase !== "idle" && this.state.phase !== "ended") {
          try { this.send({ type: "call.decline", call_id: msg.call.id }); } catch { /* ignore */ }
          return;
        }
        clearTimeout(this.endTimer);
        const c: CallSummary = msg.call;
        this.set({ ...IDLE, online: this.state.online, phase: "incoming", call: c, info: null });
        this.tone = new Tone("ring");
        if (document.hidden) notify(`📞 ${c.kind === "group" ? c.title || "Group call" : c.initiator.name}`, c.media === "video" ? "Incoming video call" : "Incoming voice call");
        break;
      }
      case "call.answered_elsewhere":
        if (this.state.phase === "incoming" && this.state.call?.id === msg.call_id) this.finish(null, true);
        break;
      case "call.joined":
        this.set({ call: msg.call });
        for (const uid of msg.peers as string[]) this.offerTo(uid);
        break;
      case "call.update": {
        if (!this.state.call || msg.call.id !== this.state.call.id) return;
        this.set({ call: msg.call });
        if (msg.joined && this.state.phase === "outgoing") { this.stopTone(); this.set({ phase: "connecting", info: "Connecting…" }); }
        if (msg.left) this.dropPeer(msg.left);
        if (msg.reason === "no answer" && this.state.phase === "outgoing") this.set({ info: "No answer yet…" });
        break;
      }
      case "call.ended":
        if (this.state.call && msg.call.id === this.state.call.id) {
          const r = msg.call.status === "declined" ? "Call declined" : msg.call.status === "missed"
            ? (this.state.phase === "incoming" ? "Missed call" : "No answer") : msg.call.status === "cancelled" ? "Call cancelled" : "Call ended";
          this.finish(r);
        }
        break;
      case "rtc.offer": this.onOffer(msg.from, msg.data); break;
      case "rtc.answer": this.pcs.get(msg.from)?.setRemoteDescription(msg.data).then(() => this.flushIce(msg.from)).catch(() => {}); break;
      case "rtc.ice": this.onIce(msg.from, msg.data); break;
      case "error":
        if (this.state.phase === "outgoing" || this.state.phase === "connecting") this.finish(msg.message);
        break;
    }
  }

  // ---------------------------------------------------------------- WebRTC
  private nameOf(uid: string) {
    return this.state.call?.participants.find((p) => p.user_id === uid)?.name || "Colleague";
  }

  private makePc(uid: string) {
    this.pcs.get(uid)?.close();
    const pc = new RTCPeerConnection({ iceServers: this.ice, bundlePolicy: "max-bundle" });
    this.pcs.set(uid, pc);
    this.state.local?.getTracks().forEach((t) => pc.addTrack(t, this.state.local!));
    // receive video even on voice calls so the other side can turn the camera on later
    this.setPeer(uid, { user_id: uid, name: this.nameOf(uid), stream: null, conn: "connecting" });
    pc.ontrack = (e) => this.setPeer(uid, { stream: e.streams[0] || new MediaStream([e.track]) });
    pc.onicecandidate = (e) => {
      if (e.candidate && this.state.call) {
        try { this.send({ type: "rtc.ice", call_id: this.state.call.id, to: uid, data: e.candidate.toJSON() }); } catch { /* ignore */ }
      }
    };
    pc.onconnectionstatechange = () => {
      const st = pc.connectionState;
      this.setPeer(uid, { conn: st });
      if (st === "connected" && this.state.phase !== "active") {
        this.stopTone();
        this.set({ phase: "active", startedAt: this.state.startedAt || Date.now(), info: null });
      }
      if (st === "failed") {
        pc.restartIce?.();
        this.set({ info: "Connection problem — trying again…" });
      }
    };
    return pc;
  }

  private async offerTo(uid: string) {
    const pc = this.makePc(uid);
    const offer = await pc.createOffer({ offerToReceiveAudio: true, offerToReceiveVideo: true });
    await pc.setLocalDescription(offer);
    this.send({ type: "rtc.offer", call_id: this.state.call!.id, to: uid, data: pc.localDescription!.toJSON() });
  }

  private async onOffer(from: string, data: RTCSessionDescriptionInit) {
    if (!this.state.call) return;
    const pc = this.makePc(from);
    await pc.setRemoteDescription(data);
    await this.flushIce(from);
    const ans = await pc.createAnswer();
    await pc.setLocalDescription(ans);
    this.send({ type: "rtc.answer", call_id: this.state.call.id, to: from, data: pc.localDescription!.toJSON() });
  }

  private async onIce(from: string, cand: RTCIceCandidateInit) {
    const pc = this.pcs.get(from);
    if (pc && pc.remoteDescription) {
      try { await pc.addIceCandidate(cand); } catch { /* ignore stale candidate */ }
    } else {
      const q = this.pendingIce.get(from) || [];
      q.push(cand);
      this.pendingIce.set(from, q);
    }
  }

  private async flushIce(uid: string) {
    const pc = this.pcs.get(uid);
    for (const c of this.pendingIce.get(uid) || []) { try { await pc?.addIceCandidate(c); } catch { /* ignore */ } }
    this.pendingIce.delete(uid);
  }

  private setPeer(uid: string, p: Partial<Peer>) {
    const prev = this.state.peers[uid] || { user_id: uid, name: this.nameOf(uid), stream: null, conn: "new" };
    this.set({ peers: { ...this.state.peers, [uid]: { ...prev, ...p } } });
  }

  private dropPeer(uid: string) {
    this.pcs.get(uid)?.close();
    this.pcs.delete(uid);
    const peers = { ...this.state.peers };
    delete peers[uid];
    this.set({ peers });
  }

  private async getMedia(media: "audio" | "video"): Promise<MediaStream> {
    if (!navigator.mediaDevices?.getUserMedia) throw new Error("This phone doesn't support calls in the app.");
    try {
      return await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
        video: media === "video" ? { facingMode: this.facing, width: 640, height: 480 } : false,
      });
    } catch (e) {
      const n = (e as DOMException).name;
      if (n === "NotAllowedError") throw new Error("Allow Microphone" + (media === "video" ? " and Camera" : "") + " for NES Team in Settings → Apps → NES Team → Permissions.");
      throw new Error("Couldn't start the microphone" + (media === "video" ? "/camera" : "") + ".");
    }
  }

  // ---------------------------------------------------------------- teardown
  private stopTone() { this.tone?.stop(); this.tone = null; }

  private cleanup() {
    this.stopTone();
    for (const pc of this.pcs.values()) pc.close();
    this.pcs.clear();
    this.pendingIce.clear();
    this.state.local?.getTracks().forEach((t) => t.stop());
  }

  private finish(reason: string | null, silent = false) {
    const dur = this.state.startedAt ? Math.round((Date.now() - this.state.startedAt) / 1000) : 0;
    this.cleanup();
    if (silent || this.state.phase === "idle") { this.set({ ...IDLE, online: this.state.online }); return; }
    this.set({ phase: "ended", peers: {}, local: null, info: reason ? `${reason}${dur ? ` · ${fmtDur(dur)}` : ""}` : null });
    clearTimeout(this.endTimer);
    this.endTimer = setTimeout(() => this.set({ ...IDLE, online: this.state.online }), 1800);
  }
}

export function fmtDur(s: number) {
  const m = Math.floor(s / 60);
  return `${String(m).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

// Ringtone / ringback generated with Web Audio (no sound files needed)
class Tone {
  private ctx: AudioContext | null = null;
  private timer: any = null;
  constructor(kind: "ring" | "ringback") {
    try {
      const AC = (window as any).AudioContext || (window as any).webkitAudioContext;
      this.ctx = new AC();
      this.ctx!.resume?.();
      const play = () => {
        if (!this.ctx) return;
        const t0 = this.ctx.currentTime;
        const freqs = kind === "ring" ? [880, 660] : [425];
        freqs.forEach((f, i) => {
          const o = this.ctx!.createOscillator();
          const g = this.ctx!.createGain();
          o.frequency.value = f;
          g.gain.setValueAtTime(0, t0 + i * 0.4);
          g.gain.linearRampToValueAtTime(kind === "ring" ? 0.25 : 0.08, t0 + i * 0.4 + 0.02);
          g.gain.linearRampToValueAtTime(0, t0 + i * 0.4 + (kind === "ring" ? 0.35 : 1.0));
          o.connect(g).connect(this.ctx!.destination);
          o.start(t0 + i * 0.4);
          o.stop(t0 + i * 0.4 + 1.1);
        });
        if (kind === "ring") try { navigator.vibrate?.([400, 200, 400]); } catch { /* ignore */ }
      };
      play();
      this.timer = setInterval(play, kind === "ring" ? 2000 : 3000);
    } catch { /* no audio */ }
  }
  stop() {
    clearInterval(this.timer);
    try { navigator.vibrate?.(0); } catch { /* ignore */ }
    this.ctx?.close().catch(() => {});
    this.ctx = null;
  }
}

export const calls = new CallManager();
