// Inline stroke icons — no icon-library dependency.

export function ServiceIcon({ name }) {
  const common = {
    className: 'ico',
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.8,
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
  }
  switch (name) {
    case 'app':
      return (
        <svg {...common}>
          <rect x="3" y="4" width="18" height="14" rx="2" />
          <path d="M3 9h18M8 21h8" />
        </svg>
      )
    case 'chart':
      return (
        <svg {...common}>
          <path d="M3 3v18h18" />
          <path d="M7 15l4-5 3 3 4-6" />
        </svg>
      )
    case 'ai':
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="3" />
          <path d="M12 2v3m0 14v3M2 12h3m14 0h3" />
        </svg>
      )
    case 'server':
      return (
        <svg {...common}>
          <rect x="3" y="10" width="18" height="10" rx="2" />
          <path d="M7 10V7a5 5 0 0110 0v3" />
        </svg>
      )
    default:
      return null
  }
}

export function LockIcon() {
  return (
    <svg viewBox="0 0 24 24">
      <rect x="5" y="11" width="14" height="10" rx="2" />
      <path d="M8 11V7a4 4 0 018 0v4" />
    </svg>
  )
}
