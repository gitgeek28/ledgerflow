export function LogoMark({ className = "size-7" }: { className?: string }) {
  return (
    <svg viewBox="0 0 28 28" className={className} aria-hidden>
      <rect width="28" height="28" rx="8" className="fill-accent" />
      <path d="M8 7.5v13h12" fill="none" stroke="var(--accent-ink)" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M12.5 15.5l2.6 2.4 4.9-6" fill="none" stroke="var(--accent-ink)" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" opacity=".85" />
    </svg>
  );
}

export function Wordmark() {
  return (
    <div className="flex items-center gap-2.5">
      <LogoMark />
      <div className="leading-tight">
        <div className="text-[15px] font-semibold tracking-tight text-ink">LedgerFlow</div>
        <div className="text-[10.5px] text-ink-3">Accounts Payable Operations</div>
      </div>
    </div>
  );
}
