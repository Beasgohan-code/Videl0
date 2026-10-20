"use client";
import { Component, type ReactNode } from "react";
export class PanelBoundary extends Component<
  { children: ReactNode; name: string },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <section
        role="alert"
        className="mx-auto my-8 max-w-xl rounded-2xl border border-amber-300/20 bg-amber-300/5 p-6"
      >
        <h2 className="text-lg font-semibold">This panel needs to restart</h2>
        <p className="mt-2 text-sm text-white/60">
          {this.props.name} encountered a problem. Other tools are still
          available. Your saved local drafts and design files are not deleted.
        </p>
        <button
          onClick={() => this.setState({ failed: false })}
          className="ios-btn ios-btn-glass mt-5 text-sm"
        >
          Retry this panel
        </button>
        <p className="mt-3 text-xs text-white/40">
          Unsaved session-only changes may be lost when restarting this panel.
        </p>
      </section>
    );
  }
}
