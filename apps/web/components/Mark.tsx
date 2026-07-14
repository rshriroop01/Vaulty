import { highlightParts } from "@/lib/search";

/** Query-term highlighting per design 2c: bg #FDF4DD, text #946200. */
export function Mark({ text, q }: { text: string; q: string }) {
  return (
    <>
      {highlightParts(text, q).map((part, i) =>
        part.highlight ? (
          <span key={i} className="rounded-[2px] bg-warn-bg px-[2px] font-semibold text-warn">
            {part.text}
          </span>
        ) : (
          <span key={i}>{part.text}</span>
        ),
      )}
    </>
  );
}
