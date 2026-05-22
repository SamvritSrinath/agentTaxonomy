import { useEffect, useId, useMemo, useRef, useState } from "react";

export interface ComboboxOption {
  value: string;
  label: string;
}

export interface ComboboxProps {
  id?: string;
  label?: string;
  value: string;
  options: ComboboxOption[];
  onChange: (value: string) => void;
  disabled?: boolean;
  placeholder?: string;
  allowCustomValue?: boolean;
  emptyMessage?: string;
}

export function Combobox({
  id,
  label,
  value,
  options,
  onChange,
  disabled = false,
  placeholder,
  allowCustomValue = false,
  emptyMessage = "No matches"
}: ComboboxProps) {
  const autoId = useId();
  const inputId = id ?? autoId;
  const rootRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [highlight, setHighlight] = useState(0);

  const displayLabel = useMemo(() => {
    const match = options.find((o) => o.value === value);
    return match?.label ?? value;
  }, [options, value]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) {
      return options;
    }
    return options.filter(
      (o) =>
        o.label.toLowerCase().startsWith(q) ||
        o.value.toLowerCase().startsWith(q)
    );
  }, [options, query]);

  useEffect(() => {
    setHighlight(0);
  }, [query, open]);

  useEffect(() => {
    function onDocClick(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  function selectOption(option: ComboboxOption) {
    onChange(option.value);
    setQuery("");
    setOpen(false);
  }

  function onInputChange(next: string) {
    setQuery(next);
    if (allowCustomValue) {
      onChange(next);
    }
    setOpen(true);
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (!open && (event.key === "ArrowDown" || event.key === "ArrowUp")) {
      setOpen(true);
      return;
    }
    if (event.key === "Escape") {
      setOpen(false);
      setQuery("");
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setHighlight((h) => Math.min(h + 1, Math.max(0, filtered.length - 1)));
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      setHighlight((h) => Math.max(h - 1, 0));
      return;
    }
    if (event.key === "Enter" && open && filtered[highlight]) {
      event.preventDefault();
      selectOption(filtered[highlight]);
    }
  }

  const inputValue = open ? query : allowCustomValue ? value : displayLabel;

  return (
    <div className="combobox" ref={rootRef}>
      {label ? (
        <label htmlFor={inputId} className="combobox-label">
          {label}
        </label>
      ) : null}
      <input
        id={inputId}
        type="text"
        className="combobox-input"
        value={inputValue}
        disabled={disabled}
        placeholder={placeholder}
        onFocus={() => setOpen(true)}
        onChange={(e) => onInputChange(e.target.value)}
        onKeyDown={onKeyDown}
        autoComplete="off"
      />
      {open && !disabled ? (
        <ul className="combobox-list" role="listbox">
          {filtered.length === 0 ? (
            <li className="combobox-option combobox-empty">{emptyMessage}</li>
          ) : (
            filtered.map((option, index) => (
              <li
                key={`${option.value}-${option.label}`}
                role="option"
                aria-selected={option.value === value}
                className={
                  index === highlight ? "combobox-option combobox-option-active" : "combobox-option"
                }
                onMouseEnter={() => setHighlight(index)}
                onMouseDown={(e) => {
                  e.preventDefault();
                  selectOption(option);
                }}
              >
                {option.label}
              </li>
            ))
          )}
        </ul>
      ) : null}
    </div>
  );
}
