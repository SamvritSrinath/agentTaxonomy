export interface SpinnerProps {
  label?: string;
  size?: "sm" | "md";
}

export function Spinner({ label, size = "md" }: SpinnerProps) {
  return (
    <span className={`spinner spinner-${size}`} role="status" aria-live="polite">
      <span className="spinner-ring" aria-hidden />
      {label ? <span className="spinner-label">{label}</span> : null}
    </span>
  );
}
