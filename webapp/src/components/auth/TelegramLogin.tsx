"use client";
import { useEffect, useRef, useState } from "react";

type TgUser = {
  id: number;
  first_name: string;
  last_name?: string;
  username?: string;
  photo_url?: string;
  auth_date: number;
  hash: string;
};

export function TelegramLogin({
  botUsername,
  onAuth,
  cornerRadius = 14,
}: {
  botUsername: string;
  onAuth: (user: TgUser) => void;
  cornerRadius?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!botUsername) return;

    // Callback global for TG widget
    (window as any).onTelegramAuth = (user: TgUser) => onAuth(user);

    const script = document.createElement("script");
    script.src = "https://telegram.org/js/telegram-widget.js?22";
    script.async = true;
    script.setAttribute("data-telegram-login", botUsername.replace("@", ""));
    script.setAttribute("data-size", "large");
    script.setAttribute("data-radius", String(cornerRadius));
    script.setAttribute("data-onauth", "onTelegramAuth(user)");
    script.setAttribute("data-request-access", "write");
    if (ref.current) {
      ref.current.innerHTML = "";
      ref.current.appendChild(script);
    }
    setLoaded(true);
    return () => {
      try { script.remove(); } catch {}
      delete (window as any).onTelegramAuth;
    };
  }, [botUsername, onAuth, cornerRadius]);

  return (
    <div className="flex flex-col items-center gap-3">
      <div ref={ref} className="min-h-[44px] flex items-center justify-center" />
      {!loaded && <p className="ios-caption">Loading Telegram widget…</p>}
      <p className="ios-caption text-center max-w-[320px] leading-relaxed">
        Sign in with Telegram to verify ownership. Only the bot <b>OWNER_ID</b> can access Studio & Chat.
      </p>
    </div>
  );
}

export function OwnerGate({
  children,
  ownerId,
}: {
  children: React.ReactNode;
  ownerId: number;
}) {
  const [user, setUser] = useState<TgUser | null>(null);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    try {
      const raw = localStorage.getItem("videl_tg_user");
      if (raw) setUser(JSON.parse(raw));
    } catch {}
    setChecked(true);
  }, []);

  const isOwner = user && String(user.id) === String(ownerId);
  const botUsername = process.env.NEXT_PUBLIC_BOT_USERNAME || "Videl0Bot";

  if (!checked) return <div className="p-8 text-center ios-caption">Checking session…</div>;

  if (!user) {
    return (
      <div className="max-w-[420px] mx-auto mt-10 ios-card-elevated p-8 text-center animate-spring">
        <div className="h-14 w-14 mx-auto rounded-full bg-white text-black flex items-center justify-center text-xl font-bold">◍</div>
        <h2 className="ios-title mt-4">Sign in required</h2>
        <p className="ios-subheadline mt-2">Studio & Chat are owner-only. Verify with Telegram.</p>
        <div className="mt-6 flex justify-center">
          <TelegramLogin
            botUsername={botUsername}
            onAuth={(u) => {
              localStorage.setItem("videl_tg_user", JSON.stringify(u));
              fetch("/api/auth", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(u) })
                .then(r => r.json()).then(j => {
                  if (j.ok) setUser(u);
                  else alert(j.error || "Not owner");
                });
            }}
          />
        </div>
        <p className="ios-caption mt-4">Bot: @{botUsername} • Owner: <code>{ownerId || "—"}</code></p>
      </div>
    );
  }

  if (!isOwner) {
    return (
      <div className="max-w-[440px] mx-auto mt-10 ios-card p-8 text-center animate-spring">
        <h3 className="ios-headline">⦿ Access denied</h3>
        <p className="ios-subheadline mt-2">Signed in as <b>{user.first_name} @{user.username}</b> (<code>{user.id}</code>) but owner is <code>{ownerId}</code>.</p>
        <div className="mt-6 flex gap-2 justify-center">
          <button onClick={() => { localStorage.removeItem("videl_tg_user"); location.reload(); }} className="ios-btn ios-btn-glass">Switch account</button>
          <a href="/dashboard" className="ios-btn ios-btn-primary">Go Dashboard</a>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
