export function CircuitIllustration() {
  return (
    <svg className="circuit-illustration" viewBox="0 0 620 500" role="img" aria-labelledby="circuit-title circuit-desc">
      <title id="circuit-title">A resistor and circuit path</title>
      <desc id="circuit-desc">Line illustration of a resistor connected to a simple circuit with measurement marks.</desc>
      <defs>
        <pattern id="paper-grid" width="24" height="24" patternUnits="userSpaceOnUse">
          <circle cx="1" cy="1" r="1" fill="currentColor" opacity=".22" />
        </pattern>
        <filter id="soft-shadow" x="-30%" y="-30%" width="160%" height="160%">
          <feDropShadow dx="0" dy="18" stdDeviation="16" floodColor="#142d28" floodOpacity=".10" />
        </filter>
      </defs>
      <rect x="1" y="1" width="618" height="498" rx="18" fill="url(#paper-grid)" />
      <path d="M59 344h110V198h91m200 0h95v146h-82" fill="none" stroke="#1d453d" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M59 344v-58m506 58v-58" fill="none" stroke="#1d453d" strokeWidth="3" strokeLinecap="round" />
      <circle cx="59" cy="344" r="6" fill="#c8794f" />
      <circle cx="565" cy="344" r="6" fill="#c8794f" />
      <g filter="url(#soft-shadow)" transform="rotate(-8 311 198)">
        <path d="M170 198h89m104 0h89" stroke="#1d453d" strokeWidth="4" strokeLinecap="round" />
        <rect x="258" y="160" width="108" height="76" rx="16" fill="#f1e9d7" stroke="#1d453d" strokeWidth="3" />
        <path d="M281 161v75" stroke="#d28b4c" strokeWidth="12" />
        <path d="M302 161v75" stroke="#394743" strokeWidth="7" />
        <path d="M323 161v75" stroke="#ba6450" strokeWidth="7" />
        <path d="M344 161v75" stroke="#d2ad62" strokeWidth="7" />
      </g>
      <path d="M306 118v-41h-66" fill="none" stroke="#a7a994" strokeWidth="2" strokeDasharray="5 7" />
      <path d="M238 70v15m-8-8h16" stroke="#a7a994" strokeWidth="2" strokeLinecap="round" />
      <text x="80" y="398" fill="#52635c" fontSize="13" fontFamily="monospace" letterSpacing="2">FIG. 01 · COMPONENT STUDY</text>
      <text x="420" y="126" fill="#a26143" fontSize="12" fontFamily="monospace" letterSpacing="1">R — 3.0 kΩ</text>
      <path d="M419 134h74" stroke="#a26143" strokeWidth="1" />
      <circle cx="170" cy="198" r="5" fill="#1d453d" />
      <circle cx="452" cy="198" r="5" fill="#1d453d" />
    </svg>
  )
}
