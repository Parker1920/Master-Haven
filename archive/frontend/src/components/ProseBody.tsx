/**
 * ProseBody — tiny markdown-ish renderer for story / inquisition / draft
 * bodies. Lighter than a full markdown library; covers the subset our
 * editors actually use:
 *
 *   **bold**, *italic*, `code`
 *   [link text](https://…)
 *   > blockquote line(s)
 *   - unordered list items (per-line)
 *   1. ordered list items (per-line)
 *
 * Paragraph break = blank line.
 *
 * Implementation: regex-driven inline replacement; block parsing splits
 * on blank lines, then dispatches per-leading-character. Safe-by-default:
 * everything else is rendered as plain text, so we never inject raw HTML
 * from author input.
 */

import { Fragment, useMemo } from "react";

interface Props {
  body: string;
  className?: string;
}

type Block =
  | { kind: "p"; lines: string[] }
  | { kind: "quote"; lines: string[] }
  | { kind: "ul"; items: string[] }
  | { kind: "ol"; items: string[] };

function parseBlocks(body: string): Block[] {
  const blocks: Block[] = [];
  const paragraphs = body.split(/\n\n+/);
  for (const raw of paragraphs) {
    const lines = raw.split(/\n/).map((l) => l.replace(/\s+$/, ""));
    if (lines.every((l) => /^>\s?/.test(l))) {
      blocks.push({
        kind: "quote",
        lines: lines.map((l) => l.replace(/^>\s?/, "")),
      });
      continue;
    }
    if (lines.every((l) => /^[-*]\s+/.test(l))) {
      blocks.push({
        kind: "ul",
        items: lines.map((l) => l.replace(/^[-*]\s+/, "")),
      });
      continue;
    }
    if (lines.every((l) => /^\d+\.\s+/.test(l))) {
      blocks.push({
        kind: "ol",
        items: lines.map((l) => l.replace(/^\d+\.\s+/, "")),
      });
      continue;
    }
    blocks.push({ kind: "p", lines });
  }
  return blocks;
}

/**
 * Render the inline portion of a single text run: handles bold, italic,
 * inline code, and links. Order matters — links first (so brackets in
 * markdown don't trip the emphasis matcher), then code, then bold,
 * then italic.
 *
 * Walk the string token-by-token, emitting React elements + plain text.
 */
function renderInline(text: string, keyPrefix: string): React.ReactNode {
  // Regex captures (in priority order):
  //   1. [label](url)
  //   2. `code`
  //   3. **bold**
  //   4. *italic*
  // We use a single combined regex with named alternation. Falls back to
  // raw text for the leading non-match slice each iteration.
  const re = /(\[([^\]]+)\]\(([^)\s]+)\))|(`([^`]+)`)|(\*\*([^*]+)\*\*)|(\*([^*]+)\*)/g;
  const out: React.ReactNode[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) {
      out.push(text.slice(last, m.index));
    }
    const key = `${keyPrefix}-${i++}`;
    if (m[1]) {
      // [label](url)
      const href = m[3];
      const safeHref = /^(https?:|mailto:|#)/.test(href) ? href : `#`;
      out.push(
        <a key={key} href={safeHref} target={safeHref.startsWith("http") ? "_blank" : undefined} rel="noreferrer">
          {m[2]}
        </a>
      );
    } else if (m[4]) {
      out.push(<code key={key} className="ta-prose-code">{m[5]}</code>);
    } else if (m[6]) {
      out.push(<strong key={key}>{m[7]}</strong>);
    } else if (m[8]) {
      out.push(<em key={key}>{m[9]}</em>);
    }
    last = re.lastIndex;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

function renderLines(lines: string[], keyPrefix: string): React.ReactNode {
  // Multi-line paragraph: each line wraps to next with a single space,
  // but explicit two-trailing-spaces produce a <br/> like markdown.
  return lines.map((line, i) => {
    const wantsBr = / {2,}$/.test(line);
    const clean = line.replace(/ +$/, "");
    return (
      <Fragment key={`${keyPrefix}-l${i}`}>
        {renderInline(clean, `${keyPrefix}-l${i}`)}
        {wantsBr ? <br /> : i < lines.length - 1 ? " " : null}
      </Fragment>
    );
  });
}

export function ProseBody({ body, className }: Props) {
  const blocks = useMemo(() => parseBlocks(body || ""), [body]);
  return (
    <div className={`ta-prose ${className ?? ""}`}>
      {blocks.map((b, i) => {
        if (b.kind === "quote") {
          return <blockquote key={i}>{renderLines(b.lines, `b${i}`)}</blockquote>;
        }
        if (b.kind === "ul") {
          return (
            <ul key={i}>
              {b.items.map((it, j) => (
                <li key={j}>{renderInline(it, `b${i}-i${j}`)}</li>
              ))}
            </ul>
          );
        }
        if (b.kind === "ol") {
          return (
            <ol key={i}>
              {b.items.map((it, j) => (
                <li key={j}>{renderInline(it, `b${i}-i${j}`)}</li>
              ))}
            </ol>
          );
        }
        return <p key={i}>{renderLines(b.lines, `b${i}`)}</p>;
      })}
    </div>
  );
}
