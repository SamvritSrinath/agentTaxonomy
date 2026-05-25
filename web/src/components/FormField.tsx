import type { ReactNode } from "react";

export interface FormFieldProps {
  label: string;
  hint?: string;
  htmlFor?: string;
  className?: string;
  children: ReactNode;
}

/** Label + optional hint wrapper for action toolbar form controls. */
export function FormField({ label, hint, htmlFor, className = "", children }: FormFieldProps) {
  return (
    <div className={`form-field ${className}`.trim()}>
      <span className="form-field-label" id={htmlFor ? `${htmlFor}-label` : undefined}>
        {htmlFor ? (
          <label htmlFor={htmlFor}>{label}</label>
        ) : (
          <span>{label}</span>
        )}
      </span>
      {children}
      {hint ? (
        <p className="field-hint" id={htmlFor ? `${htmlFor}-hint` : undefined}>
          {hint}
        </p>
      ) : null}
    </div>
  );
}
