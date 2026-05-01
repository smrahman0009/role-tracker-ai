/**
 * LetterRenderer — renders a cover-letter's plain-text-with-markdown
 * source as actual rich text. Handles only what the agent emits:
 *
 *   - `**bold**`     → <strong>
 *   - `[text](url)`  → <a href="url" target="_blank">
 *   - `\n\n`         → paragraph break
 *   - `\n` inside    → <br /> (soft line break, e.g. multi-line header)
 *
 * No external dependency — a tiny inline parser is plenty for the
 * shape the agent produces. If we ever need lists / tables / headings
 * we can swap in react-markdown.
 */

import { Fragment } from "react";

interface Props {
  text: string;
  className?: string;
}

export function LetterRenderer({ text, className }: Props) {
  const paragraphs = text.split(/\n\n+/).filter((p) => p.trim());
  return (
    <div className={className}>
      {paragraphs.map((para, i) => (
        <p
          key={i}
          className="mb-4 last:mb-0 text-sm text-slate-800 leading-relaxed"
        >
          {renderParagraph(para, i)}
        </p>
      ))}
    </div>
  );
}

function renderParagraph(para: string, paraIndex: number): React.ReactNode {
  const lines = para.split("\n");
  return lines.map((line, i) => (
    <Fragment key={i}>
      {renderInline(line, `${paraIndex}-${i}`)}
      {i < lines.length - 1 && <br />}
    </Fragment>
  ));
}

function renderInline(text: string, prefix: string): React.ReactNode[] {
  const out: React.ReactNode[] = [];
  let remaining = text;
  let key = 0;

  while (remaining.length > 0) {
    const bold = remaining.match(/^\*\*([^*\n]+?)\*\*/);
    if (bold) {
      out.push(<strong key={`${prefix}-${key++}`}>{bold[1]}</strong>);
      remaining = remaining.slice(bold[0].length);
      continue;
    }
    const link = remaining.match(/^\[([^\]]+)\]\(([^)]+)\)/);
    if (link) {
      const href = link[2].startsWith("http")
        ? link[2]
        : `https://${link[2]}`;
      out.push(
        <a
          key={`${prefix}-${key++}`}
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="text-indigo-700 hover:underline"
        >
          {link[1]}
        </a>,
      );
      remaining = remaining.slice(link[0].length);
      continue;
    }
    const nextSpecial = remaining.search(/\*\*|\[/);
    if (nextSpecial === -1) {
      out.push(<Fragment key={`${prefix}-${key++}`}>{remaining}</Fragment>);
      break;
    }
    if (nextSpecial > 0) {
      out.push(
        <Fragment key={`${prefix}-${key++}`}>
          {remaining.slice(0, nextSpecial)}
        </Fragment>,
      );
      remaining = remaining.slice(nextSpecial);
    } else {
      // Unclosed `**` or `[` at position 0 — emit it as literal so we
      // don't infinite-loop, then continue.
      out.push(<Fragment key={`${prefix}-${key++}`}>{remaining[0]}</Fragment>);
      remaining = remaining.slice(1);
    }
  }
  return out;
}
