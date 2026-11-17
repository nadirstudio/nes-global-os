export function Logo({ size = 40 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden>
      <rect width="64" height="64" rx="16" fill="#0b1b3a" />
      <circle cx="32" cy="32" r="18" fill="none" stroke="#22d3ee" strokeWidth="3.5" />
      <circle cx="32" cy="32" r="6" fill="#3b82f6" />
      <g stroke="#3b82f6" strokeWidth="3" strokeLinecap="round">
        <line x1="32" y1="10" x2="32" y2="24" /><line x1="32" y1="40" x2="32" y2="54" />
        <line x1="10" y1="32" x2="24" y2="32" /><line x1="40" y1="32" x2="54" y2="32" />
      </g>
    </svg>
  );
}
