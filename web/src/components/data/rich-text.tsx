import { Fragment } from "react";

/**
 * Renders the small amount of inline emphasis our copy uses (`<b>…</b>`, `**…**`, `<br>`) as React elements.
 * The text is never treated as HTML, so headlines or names inside it cannot inject markup.
 */
export function RichText({ text }: { text: string }) {
  const parts = text.split(/(<b>.*?<\/b>|\*\*.*?\*\*|<br\s*\/?>)/gs);
  return (
    <>
      {parts.map((part, i) => {
        if (/^<br\s*\/?>$/.test(part)) return <br key={i} />;
        const bold = /^<b>(.*)<\/b>$/s.exec(part) ?? /^\*\*(.*)\*\*$/s.exec(part);
        if (bold) return <strong key={i} className="text-foreground font-semibold">{bold[1]}</strong>;
        return <Fragment key={i}>{part}</Fragment>;
      })}
    </>
  );
}
