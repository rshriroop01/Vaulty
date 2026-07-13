/**
 * Auth layout — screen 2a: 44% navy brand panel with trust bullets,
 * content area centers the 380px auth card.
 */
export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen text-text">
      <div className="hidden w-[44%] flex-none flex-col bg-ink p-[52px_56px] text-white md:flex">
        <div className="flex items-center gap-2.5">
          <div className="grid h-[30px] w-[30px] place-items-center rounded-control bg-white/14 font-mono text-[14px] font-bold">
            V
          </div>
          <span className="text-[17px] font-bold">Vaultly</span>
        </div>
        <div className="mt-24 max-w-[360px] text-[30px] font-semibold leading-[1.25] tracking-[-0.01em]">
          Every important document. One secure vault.
        </div>
        <div className="mt-3.5 max-w-[360px] text-[14px] leading-[1.6] text-[#b9c6d3]">
          Receipts, warranties, insurance, medical records — organized automatically, found in
          seconds.
        </div>
        <div className="mt-auto grid gap-2.5 text-[12.5px] text-[#b9c6d3]">
          {[
            "AES-256 encryption at rest · TLS 1.3 in transit",
            "Every access recorded in an audit log",
            "Two-factor authentication built in",
          ].map((line) => (
            <div key={line} className="flex items-center gap-[9px]">
              <span className="h-[7px] w-[7px] rounded-[2px] bg-[#5c88b0]" />
              {line}
            </div>
          ))}
        </div>
      </div>
      <div className="grid flex-1 place-items-center bg-app p-10">{children}</div>
    </div>
  );
}
