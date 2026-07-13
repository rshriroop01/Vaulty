export function ComingSoon({ title, milestone }: { title: string; milestone: string }) {
  return (
    <>
      <h1 className="mb-0.5 text-[21px] font-semibold tracking-[-0.01em]">{title}</h1>
      <p className="mb-[22px] text-[13px] text-text-sub">
        Ships in {milestone} — see docs/ROADMAP.md.
      </p>
      <div className="rounded-card border border-dashed border-border bg-card px-6 py-10 text-center text-[12.5px] text-text-sub">
        This area is scaffolded and waiting for its milestone.
      </div>
    </>
  );
}
