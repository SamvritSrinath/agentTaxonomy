import { Spinner } from "./Spinner";

export interface LoadingNoticeProps {
  loading: boolean;
  error?: string | null;
  label?: string;
}

export function LoadingNotice({ loading, error, label = "Loading…" }: LoadingNoticeProps) {
  if (error) {
    return <p className="error">{error}</p>;
  }
  if (loading) {
    return (
      <p className="loading-notice">
        <Spinner label={label} size="sm" />
      </p>
    );
  }
  return null;
}
