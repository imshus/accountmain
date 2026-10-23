import { Component, type ErrorInfo, type ReactNode } from "react";

type State = { error: Error | null };

/** Shows a message instead of a blank page if a part of the screen fails to render. */
export default class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Display error", error, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="callout error" role="alert">
        <strong>Something on this screen could not be displayed.</strong> {this.state.error.message}{" "}
        <button className="button small-button" onClick={() => this.setState({ error: null })}>
          Try again
        </button>{" "}
        <button className="button small-button" onClick={() => window.location.reload()}>
          Reload page
        </button>
      </div>
    );
  }
}
