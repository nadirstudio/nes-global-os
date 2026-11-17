import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { calls, fmtDur, Peer } from "../calls";
import { Avatar } from "../ui";

export function useCall() {
  return useSyncExternalStore(calls.subscribe, calls.getState);
}

function Media({ stream, video, muted, mirror, className }: { stream: MediaStream | null; video: boolean; muted?: boolean; mirror?: boolean; className?: string }) {
  const ref = useRef<HTMLVideoElement & HTMLAudioElement>(null);
  useEffect(() => {
    if (ref.current && ref.current.srcObject !== stream) {
      ref.current.srcObject = stream;
      ref.current.play?.().catch(() => {});
    }
  }, [stream]);
  if (!video) return <audio ref={ref} autoPlay />;
  return <video ref={ref} autoPlay playsInline muted={muted} className={className} style={mirror ? { transform: "scaleX(-1)" } : undefined} />;
}

function hasVideo(s: MediaStream | null) {
  return !!s && s.getVideoTracks().some((t) => t.enabled && t.readyState === "live" && !t.muted);
}

export function CallLayer() {
  const s = useCall();
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (s.phase !== "active") return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [s.phase]);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { if (s.phase === "idle") setErr(null); }, [s.phase]);
  if (s.phase === "idle") return null;

  const c = s.call;
  const isGroup = c?.kind === "group";
  const other = c ? (c.initiator.user_id === calls.me ? c.participants.find((p) => p.user_id !== calls.me) : c.initiator) : null;
  const title = isGroup ? c?.title || "Group call" : other?.name || (s.info?.replace(/^Calling |…$/g, "") ?? "Call");
  const peers = Object.values(s.peers) as Peer[];
  const video = c?.media === "video";
  const run = (fn: () => any) => Promise.resolve().then(fn).catch((e) => setErr((e as Error).message));

  // ---------------------------------------------------------------- incoming
  if (s.phase === "incoming" && c) {
    return (
      <div className="call-screen">
        <div className="call-top">
          <div className="call-kind">{isGroup ? "👥 Group call" : video ? "🎥 Video call" : "📞 Voice call"} · NES Team</div>
          <div className="call-ava pulse-ring"><Avatar name={isGroup ? title : c.initiator.name} size={112} /></div>
          <h2 className="call-name">{isGroup ? title : c.initiator.name}</h2>
          <div className="call-sub">{isGroup ? `${c.initiator.name} is calling the group` : "is calling you…"}</div>
        </div>
        {err && <div className="err">{err}</div>}
        <div className="call-actions">
          <div className="call-act"><button className="round red" onClick={() => calls.decline()} aria-label="Decline">✕</button>Decline</div>
          {video && <div className="call-act"><button className="round grey" onClick={() => run(() => calls.accept(false))} aria-label="Answer with voice only">📞</button>Voice only</div>}
          <div className="call-act"><button className="round green" onClick={() => run(() => calls.accept())} aria-label="Answer">{video ? "🎥" : "📞"}</button>Answer</div>
        </div>
      </div>
    );
  }

  // ---------------------------------------------------------------- ended
  if (s.phase === "ended") {
    return (
      <div className="call-screen">
        <div className="call-top">
          <div className="call-ava"><Avatar name={title || "Call"} size={96} /></div>
          <h2 className="call-name">{title}</h2>
          <div className="call-sub">{s.info || "Call ended"}</div>
        </div>
      </div>
    );
  }

  // ---------------------------------------------------------------- outgoing / connecting / active
  const remoteVideo = peers.filter((p) => hasVideo(p.stream));
  const showGrid = video && remoteVideo.length > 0;
  const timer = s.phase === "active" && s.startedAt ? fmtDur(Math.round((now - s.startedAt) / 1000)) : null;
  return (
    <div className={`call-screen ${showGrid ? "has-video" : ""}`}>
      {/* remote audio/video */}
      {showGrid ? (
        <div className={`call-grid n${Math.min(remoteVideo.length, 4)}`}>
          {remoteVideo.map((p) => (
            <div key={p.user_id} className="tile-v"><Media stream={p.stream} video /><span>{p.name}</span></div>
          ))}
        </div>
      ) : null}
      {peers.filter((p) => !showGrid || !hasVideo(p.stream)).map((p) => <Media key={p.user_id} stream={p.stream} video={false} />)}

      <div className="call-top">
        {!showGrid && (
          <>
            <div className="call-kind">{isGroup ? "👥 Group call" : video ? "🎥 Video call" : "📞 Voice call"}{s.online ? "" : " · reconnecting…"}</div>
            <div className={`call-ava ${s.phase === "outgoing" ? "pulse-ring" : ""}`}><Avatar name={title} size={112} /></div>
            <h2 className="call-name">{title}</h2>
          </>
        )}
        <div className="call-sub">{timer || s.info || (s.phase === "connecting" ? "Connecting…" : "Ringing…")}</div>
        {isGroup && (
          <div className="call-people">
            {c?.participants.filter((p) => p.user_id !== calls.me).map((p) => (
              <span key={p.user_id} className={`chip ${s.peers[p.user_id]?.conn === "connected" ? "ok" : p.state === "ringing" ? "warn" : "muted"}`}>
                {p.name} · {s.peers[p.user_id]?.conn === "connected" ? "in call" : p.state === "ringing" ? "ringing" : p.state === "joined" ? "joining" : p.state}
              </span>
            ))}
          </div>
        )}
      </div>

      {video && s.local && s.cameraOn && <Media stream={s.local} video muted mirror className="self-view" />}
      {err && <div className="err" style={{ margin: "0 20px" }}>{err}</div>}

      <div className="call-actions">
        <div className="call-act"><button className={`round ${s.muted ? "white" : "grey"}`} onClick={() => calls.toggleMute()} aria-label="Mute">{s.muted ? "🔇" : "🎙"}</button>{s.muted ? "Unmute" : "Mute"}</div>
        {video && <div className="call-act"><button className={`round ${s.cameraOn ? "grey" : "white"}`} onClick={() => calls.toggleCamera()} aria-label="Camera">{s.cameraOn ? "📷" : "🚫"}</button>Camera</div>}
        {video && <div className="call-act"><button className="round grey" onClick={() => run(() => calls.flipCamera())} aria-label="Flip camera">🔄</button>Flip</div>}
        <div className="call-act"><button className="round red" onClick={() => calls.hangup()} aria-label="Hang up">✆</button>End</div>
      </div>
    </div>
  );
}
