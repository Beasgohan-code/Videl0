/**
 * The shared vocabulary for studio screens.
 *
 * Headers, empty states, callouts and skeletons existed in a dozen local
 * variants. These are the canonical ones: every screen that uses them inherits
 * the same spacing, the same dark-theme contrast and the same accessibility
 * contract (a status is announced, an empty state is not a silent blank box).
 */
import type { ComponentType, ReactNode } from "react";
import { AlertTriangle, CheckCircle2, Inbox, Info, Loader2 } from "lucide-react";

type IconType = ComponentType<{ size?: number | string; className?: string }>;
export type CalloutTone = "info" | "success" | "warn" | "danger";

const calloutIcon: Record<CalloutTone, IconType> = {
  info: Info,
  success: CheckCircle2,
  warn: AlertTriangle,
  danger: AlertTriangle,
};

export function PageHeader({
  eyebrow,
  title,
  subtitle,
  actions,
  titleId,
}: {
  eyebrow?: ReactNode;
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  titleId?: string;
}) {
  return (
    <header className="ios-page-header">
      <div className="min-w-0">
        {eyebrow ? <p className="ios-caps ios-eyebrow">{eyebrow}</p> : null}
        <h1 id={titleId} className="ios-title mt-2">
          {title}
        </h1>
        {subtitle ? <p className="ios-subheadline mt-2 max-w-2xl">{subtitle}</p> : null}
      </div>
      {actions ? <div className="ios-page-actions">{actions}</div> : null}
    </header>
  );
}

export function Callout({
  tone = "info",
  title,
  children,
  icon,
  live,
  className = "",
}: {
  tone?: CalloutTone;
  title?: ReactNode;
  children?: ReactNode;
  icon?: ReactNode;
  /** Announce changes; static guidance should stay quiet. */
  live?: boolean;
  className?: string;
}) {
  const Icon = calloutIcon[tone];
  const announced = live ?? tone !== "info";
  return (
    <div
      className={`ios-callout ${className}`}
      data-tone={tone}
      role={announced ? (tone === "danger" ? "alert" : "status") : undefined}
    >
      {icon ?? <Icon size={18} aria-hidden />}
      <div className="ios-callout-body">
        {title ? <p className="ios-callout-title">{title}</p> : null}
        {children ? <div className={title ? "mt-1" : undefined}>{children}</div> : null}
      </div>
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  hint,
  action,
  compact = false,
  className = "",
}: {
  icon?: ReactNode;
  title: ReactNode;
  hint?: ReactNode;
  action?: ReactNode;
  compact?: boolean;
  className?: string;
}) {
  return (
    <div className={`ios-state ${compact ? "ios-state-compact" : ""} ${className}`}>
      <span className="ios-state-icon" aria-hidden>
        {icon ?? <Inbox size={20} />}
      </span>
      <p className="ios-state-title">{title}</p>
      {hint ? <p className="ios-state-hint">{hint}</p> : null}
      {action ? <div className="ios-state-action">{action}</div> : null}
    </div>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <span aria-hidden className={`ios-skeleton ${className}`} />;
}

/** The shape of the answer while it is still being fetched. */
export function LoadingState({
  label = "Loading…",
  rows = 3,
  className = "",
}: {
  label?: string;
  rows?: number;
  className?: string;
}) {
  return (
    <div className={`space-y-2.5 ${className}`} role="status" aria-live="polite">
      <span className="sr-only">{label}</span>
      {Array.from({ length: Math.max(1, rows) }, (_, index) => (
        <Skeleton key={index} className={index === 0 ? "h-4 w-2/5" : "h-3 w-full"} />
      ))}
    </div>
  );
}

/** A small inline spinner with a label, for a button that is already busy. */
export function BusyLabel({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center gap-2">
      <Loader2 size={15} className="animate-spin" aria-hidden />
      {label}
    </span>
  );
}

export function SectionHead({
  title,
  hint,
  aside,
  id,
}: {
  title: ReactNode;
  hint?: ReactNode;
  aside?: ReactNode;
  id?: string;
}) {
  return (
    <div className="ios-section-head">
      <div className="min-w-0">
        <h2 id={id} className="ios-section-title">
          {title}
        </h2>
        {hint ? <p className="ios-caption mt-0.5">{hint}</p> : null}
      </div>
      {aside ? <div className="flex shrink-0 items-center gap-2">{aside}</div> : null}
    </div>
  );
}
