import type { ReactNode } from "react";
import ErrorBoundary from "../../components/ErrorBoundary";
import { Notice, Page, ScreenLoading } from "../../ui";
import "./legacy.css";

type Props = {
  title: ReactNode;
  width?: "narrow" | "wide" | "full";
  /** Show a spinner instead of the content. */
  loading?: boolean;
  error?: string | null;
  right?: ReactNode;
  children?: ReactNode;
};

/** An older screen (files, sets, the full books) inside the new design: back header, centred column, its own error boundary. */
export default function LegacyFrame({ title, width = "wide", loading, error, right, children }: Props) {
  return (
    <Page title={title} width={width} right={right}>
      <div className="legacy">
        {error ? <Notice tone="error">{error}</Notice> : loading ? <ScreenLoading /> : <ErrorBoundary>{children}</ErrorBoundary>}
      </div>
    </Page>
  );
}
