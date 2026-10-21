"use client";
import { Component, type ReactNode } from "react";
import { Callout } from "./ui";
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
      <section role="alert" className="mx-auto my-8 w-full max-w-xl">
        <Callout tone="warn" title="This panel needs to restart">
          {this.props.name} encountered a problem. Other tools are still
          available. Your saved local drafts and design files are not deleted.
          <p className="ios-caption mt-3">
            Unsaved session-only changes may be lost when restarting this panel.
          </p>
          <button
            onClick={() => this.setState({ failed: false })}
            className="ios-btn ios-btn-glass mt-4 text-sm"
          >
            Retry this panel
          </button>
        </Callout>
      </section>
    );
  }
}
