/**
 * Loading — shared spinner / loading indicator.
 *
 * Replaces ad-hoc "Loading…" strings scattered across pages so we get
 * one visual treatment. Pass `inline` for use mid-line, default is a
 * centered block matching the old .ta-loading class.
 */

interface Props {
  label?: string;
  inline?: boolean;
}

export function Loading({ label = "Loading…", inline = false }: Props) {
  if (inline) {
    return (
      <span className="ta-loading-inline" aria-live="polite">
        <span className="ta-spinner" aria-hidden="true" /> {label}
      </span>
    );
  }
  return (
    <div className="ta-loading" aria-live="polite">
      <span className="ta-spinner" aria-hidden="true" />
      <span style={{ marginLeft: 8 }}>{label}</span>
    </div>
  );
}
