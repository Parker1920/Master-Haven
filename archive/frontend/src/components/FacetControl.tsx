/**
 * FacetControl — one facet's input from its schema definition.
 * Shared by the create/edit form and the Browse filter rail.
 *
 *  single  → themed select ("Any" + options)
 *  multi   → themed checkbox list with show-more past `limit`
 *  boolean → a single themed checkbox
 */

import { useState } from "react";
import { FacetDef } from "../api/client";

export function FacetControl({
  def, value, onChange, limit = 8,
}: {
  def: FacetDef;
  value: string[];
  onChange: (v: string[]) => void;
  limit?: number;
}) {
  const [expanded, setExpanded] = useState(false);

  if (def.control === "boolean") {
    const on = value.includes("true");
    return (
      <label className="ta-cat-facet-check">
        <input type="checkbox" checked={on} onChange={(e) => onChange(e.target.checked ? ["true"] : [])} />
        <span>{def.label}</span>
      </label>
    );
  }

  if (def.control === "date") {
    return (
      <input
        type="date"
        className="ta-form-input ta-cat-facet-select"
        value={value[0] ?? ""}
        onChange={(e) => onChange(e.target.value ? [e.target.value] : [])}
      />
    );
  }

  if (def.control === "single") {
    return (
      <select
        className="ta-form-select ta-cat-facet-select"
        value={value[0] ?? ""}
        onChange={(e) => onChange(e.target.value ? [e.target.value] : [])}
      >
        <option value="">Any</option>
        {def.options.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    );
  }

  const opts = expanded ? def.options : def.options.slice(0, limit);
  return (
    <div className="ta-cat-facet-opts">
      {opts.map((o) => {
        const on = value.includes(o);
        return (
          <label key={o} className="ta-cat-facet-check">
            <input
              type="checkbox"
              checked={on}
              onChange={(e) => onChange(e.target.checked ? [...value, o] : value.filter((x) => x !== o))}
            />
            <span>{o}</span>
          </label>
        );
      })}
      {def.options.length > limit && (
        <button type="button" className="ta-cat-facet-more" onClick={() => setExpanded((x) => !x)}>
          {expanded ? "Show less" : `Show ${def.options.length - limit} more`}
        </button>
      )}
    </div>
  );
}
