/**
 * Room voice: peer-to-peer WebRTC with the room stream as the postman.
 *
 * There is no second socket and no media server. The room already polls an
 * ordered event feed every couple of seconds, so a signal is one more event —
 * written by the backend, addressed to one seat, and relayed to the browser by
 * the route that already exists. That keeps the transport honest: if the room
 * is readable, voice can connect; if it is not, nothing else works either.
 *
 * The limits are stated in the UI rather than hidden: Telegram's in-app webview
 * often refuses a microphone, so a refusal is a first-class state (`blocked`),
 * the microphone starts muted, and a room can still talk through voice notes.
 */

export type VoiceSignal = {
  kind: "offer" | "answer" | "ice" | "bye";
  to: number;
  data: Record<string, unknown>;
};

export type VoiceState =
  | { status: "off" | "asking" | "ready" | "live" | "blocked" | "unsupported"; error?: string }
  | { status: "connecting"; peer: number };

/** Is this browser even allowed to try? */
export function canVoice(): boolean {
  if (typeof window === "undefined") return false;
  return Boolean(
    window.RTCPeerConnection &&
      navigator.mediaDevices &&
      typeof navigator.mediaDevices.getUserMedia === "function",
  );
}

/**
 * Why a microphone fails matters to the person reading the message: "denied"
 * means their webview or settings, "no device" means the hardware.
 */
export function voiceFailure(error: unknown): { status: "blocked" | "unsupported"; error: string } {
  const name = (error as { name?: string })?.name || "";
  if (name === "NotAllowedError" || name === "SecurityError") {
    return {
      status: "blocked",
      error:
        "This webview refused the microphone. Open Videl in Chrome or Safari, or use voice notes instead.",
    };
  }
  if (name === "NotFoundError" || name === "OverconstrainedError") {
    return { status: "unsupported", error: "No microphone was found on this device." };
  }
  if (name === "NotReadableError") {
    return { status: "blocked", error: "Another app is holding the microphone." };
  }
  return {
    status: "blocked",
    error: "Voice could not start here. Voice notes still work.",
  };
}

/** One connection per peer, created only when the microphone is already granted. */
export type Peer = {
  id: number;
  connection: RTCPeerConnection;
  stream: MediaStream;
  polite: boolean;
};

type Hooks = {
  send: (signal: VoiceSignal) => void;
  onRemote: (peer: number, stream: MediaStream | null) => void;
  onState: (state: VoiceState) => void;
};

/**
 * A tiny, deliberately boring mesh: every seated player connects to every other
 * one. A four-seat table is six connections, which is the most this design will
 * ever need; more seats would want an SFU and that is a different product.
 */
export class RoomVoice {
  private peers = new Map<number, Peer>();
  private stream: MediaStream | null = null;
  private me: number;
  private hooks: Hooks;
  private closed = false;

  constructor(me: number, hooks: Hooks) {
    this.me = me;
    this.hooks = hooks;
  }

  /** Ask once; every later join reuses the same microphone track. */
  async start(): Promise<boolean> {
    if (this.stream) return true;
    if (!canVoice()) {
      this.hooks.onState({ status: "unsupported", error: "This browser has no WebRTC support." });
      return false;
    }
    this.hooks.onState({ status: "asking" });
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
        video: false,
      });
    } catch (error) {
      this.hooks.onState(voiceFailure(error));
      return false;
    }
    // Joining a table should never broadcast the room's background noise
    // before the person has decided to speak: mute until push-to-talk.
    this.stream.getAudioTracks().forEach((track) => (track.enabled = false));
    this.hooks.onState({ status: "ready" });
    return true;
  }

  microphone(): MediaStream | null {
    return this.stream;
  }

  setMuted(muted: boolean) {
    this.stream?.getAudioTracks().forEach((track) => (track.enabled = !muted));
  }

  /** I speak first; the other side answers. Ties are broken by seat number. */
  async offerTo(peer: number) {
    if (!this.stream || this.peers.has(peer)) return;
    const connection = new RTCPeerConnection({
      iceServers: [{ urls: ["stun:stun.l.google.com:19302", "stun:stun1.l.google.com:19302"] }],
    });
    const polite = this.me > peer;
    const entry: Peer = { id: peer, connection, stream: this.stream, polite };
    this.peers.set(peer, entry);
    this.stream.getTracks().forEach((track) => connection.addTrack(track, this.stream!));
    this.wire(entry);

    if (!polite) {
      this.hooks.onState({ status: "connecting", peer });
      const offer = await connection.createOffer();
      await connection.setLocalDescription(offer);
      this.hooks.send({ kind: "offer", to: peer, data: { type: offer.type, sdp: offer.sdp } });
    }
  }

  private wire(peer: Peer) {
    peer.connection.onicecandidate = (event) => {
      if (!event.candidate || this.closed) return;
      this.hooks.send({
        kind: "ice",
        to: peer.id,
        data: {
          candidate: event.candidate.candidate,
          sdpMid: event.candidate.sdpMid,
          sdpMLineIndex: event.candidate.sdpMLineIndex,
        },
      });
    };
    peer.connection.ontrack = (event) => {
      const [remote] = event.streams;
      this.hooks.onRemote(peer.id, remote || null);
      this.hooks.onState({ status: "live" });
    };
    peer.connection.onconnectionstatechange = () => {
      const state = peer.connection.connectionState;
      if (state === "failed" || state === "closed") this.drop(peer.id);
      if (state === "connected") this.hooks.onState({ status: "live" });
    };
  }

  /** Apply a signal that came from the room feed. */
  async receive(signal: VoiceSignal, from: number) {
    if (!this.stream || this.closed || from === this.me) return;
    let peer = this.peers.get(from);
    if (!peer) {
      const connection = new RTCPeerConnection({
        iceServers: [{ urls: ["stun:stun.l.google.com:19302", "stun:stun1.l.google.com:19302"] }],
      });
      peer = { id: from, connection, stream: this.stream, polite: this.me > from };
      this.peers.set(from, peer);
      this.stream.getTracks().forEach((track) => connection.addTrack(track, this.stream!));
      this.wire(peer);
    }
    const { connection } = peer;

    if (signal.kind === "bye") {
      this.drop(from);
      return;
    }
    if (signal.kind === "ice") {
      const data = signal.data as { candidate?: string; sdpMid?: string | null; sdpMLineIndex?: number | null };
      if (!data?.candidate) return;
      try {
        await connection.addIceCandidate({
          candidate: data.candidate,
          sdpMid: data.sdpMid ?? undefined,
          sdpMLineIndex: data.sdpMLineIndex ?? undefined,
        });
      } catch {
        /* A candidate that arrives after the peer is gone is not an error. */
      }
      return;
    }

    const data = signal.data as { type: RTCSdpType; sdp: string };
    if (!data?.sdp) return;
    const description = { type: data.type, sdp: data.sdp };
    const collision = signal.kind === "offer" && connection.signalingState !== "stable";
    if (collision) {
      // Glare: both sides offered. The polite side yields and answers theirs.
      if (!peer.polite) return;
      await connection.setLocalDescription({ type: "rollback" } as RTCSessionDescriptionInit).catch(() => {});
    }
    try {
      await connection.setRemoteDescription(description);
      if (signal.kind === "offer") {
        const answer = await connection.createAnswer();
        await connection.setLocalDescription(answer);
        this.hooks.send({ kind: "answer", to: from, data: { type: answer.type, sdp: answer.sdp } });
        this.hooks.onState({ status: "live" });
      }
    } catch {
      this.drop(from);
    }
  }

  /** End one connection without dropping the microphone. */
  drop(peer: number) {
    const entry = this.peers.get(peer);
    if (!entry) return;
    entry.connection.close();
    this.peers.delete(peer);
    this.hooks.onRemote(peer, null);
  }

  /** Everyone I am currently connected to. */
  live(): number[] {
    return [...this.peers.keys()];
  }

  hangUp() {
    this.closed = true;
    this.peers.forEach((entry) => {
      this.hooks.send({ kind: "bye", to: entry.id, data: {} });
      entry.connection.close();
      this.hooks.onRemote(entry.id, null);
    });
    this.peers.clear();
    this.stream?.getTracks().forEach((track) => track.stop());
    this.stream = null;
    this.hooks.onState({ status: "off" });
  }
}
