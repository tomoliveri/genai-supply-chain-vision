import Link from 'next/link';

const stats = [
  { label: 'Ports monitored', value: '68' },
  { label: 'Analysis frequency', value: 'Daily' },
  { label: 'Monthly cost', value: 'AUD $25' },
  { label: 'Imagery cost', value: 'Free' },
];

const signals = [
  {
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 15a4 4 0 004 4h9a5 5 0 10-.1-9.999 5.002 5.002 0 10-9.78 2.096A4.001 4.001 0 003 15z" />
      </svg>
    ),
    color: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20',
    label: 'Weather events',
    desc: 'Tropical storms, fog, high swell, wind suspensions. Cross-referenced with Open-Meteo archive data.',
  },
  {
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
      </svg>
    ),
    color: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    label: 'Port congestion',
    desc: 'Vessel waiting times, yard fill, crane outages. Detected from imagery and shipping intelligence.',
  },
  {
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
      </svg>
    ),
    color: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
    label: 'Labour actions',
    desc: 'Strike warnings, active stoppages, overtime bans. Tracked across major ports with 14-day advance warning.',
  },
  {
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
    color: 'bg-red-500/10 text-red-400 border-red-500/20',
    label: 'Geopolitical events',
    desc: '18 tracked events: armed conflicts, court rulings voiding concessions, carrier rerouting, insurance spikes.',
  },
];

const steps = [
  {
    n: '01',
    title: 'Imagery acquired',
    desc: 'Cloud Scheduler triggers the pipeline at 2am UTC. The latest Sentinel-2 L2A scene is fetched per port from the Copernicus Data Space API, cropped to a 2km AOI and cached in GCS.',
  },
  {
    n: '02',
    title: 'Gemini analyses',
    desc: 'Two-stage analysis: Gemini first describes the imagery, then assesses it against weather data, labour events and geopolitical signals. External context can override ambiguous imagery.',
  },
  {
    n: '03',
    title: 'Briefing written',
    desc: 'A structured briefing lands in Firestore: severity score, confidence grade, disruption category, vessel counts, yard fill percentage. Visible in the dashboard within minutes of the run completing.',
  },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 antialiased">

      {/* Background grid */}
      <div
        className="pointer-events-none fixed inset-0 opacity-[0.03]"
        style={{
          backgroundImage:
            'linear-gradient(to right, #94a3b8 1px, transparent 1px), linear-gradient(to bottom, #94a3b8 1px, transparent 1px)',
          backgroundSize: '60px 60px',
        }}
      />

      {/* Hero */}
      <section className="relative px-6 pt-20 pb-16 md:pt-32 md:pb-24 max-w-4xl mx-auto">

        {/* Eyebrow */}
        <div className="inline-flex items-center gap-2 rounded-full border border-blue-500/30 bg-blue-500/10 px-3 py-1 text-xs font-medium text-blue-400 mb-8">
          <span className="relative flex h-1.5 w-1.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-blue-500" />
          </span>
          Live — updated daily
        </div>

        <h1 className="text-4xl md:text-6xl font-bold tracking-tight text-slate-50 leading-[1.1]">
          Know about port disruptions{' '}
          <span className="bg-gradient-to-r from-blue-400 via-indigo-400 to-purple-400 bg-clip-text text-transparent">
            before your freight forwarder does
          </span>
        </h1>

        <p className="mt-6 text-lg text-slate-400 max-w-2xl leading-relaxed">
          SupplyWatch monitors 68 major ports daily with free Sentinel-2
          satellite imagery and Gemini Flash. Every port gets a structured
          disruption briefing, every day.
        </p>

        {/* Stat row */}
        <div className="mt-8 flex flex-wrap gap-3">
          {stats.map((s) => (
            <div
              key={s.label}
              className="flex items-center gap-2 rounded-lg border border-slate-800 bg-slate-900 px-3 py-2"
            >
              <span className="text-sm font-semibold text-slate-100">{s.value}</span>
              <span className="text-xs text-slate-500">{s.label}</span>
            </div>
          ))}
        </div>

        {/* CTAs */}
        <div className="mt-8 flex flex-wrap gap-3">
          <Link
            href="/demo"
            className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-blue-500 transition-colors shadow-lg shadow-blue-500/20"
          >
            Open the dashboard
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
            </svg>
          </Link>
          <Link
            href="/how-it-works"
            className="inline-flex items-center gap-2 rounded-lg border border-slate-700 px-5 py-2.5 text-sm font-semibold text-slate-300 hover:border-slate-500 hover:text-slate-100 transition-colors"
          >
            Engineering story
          </Link>
        </div>
      </section>

      {/* Divider */}
      <div className="max-w-4xl mx-auto px-6">
        <div className="h-px bg-gradient-to-r from-transparent via-slate-800 to-transparent" />
      </div>

      {/* How it works */}
      <section className="px-6 py-20 max-w-4xl mx-auto">
        <p className="text-xs font-semibold uppercase tracking-widest text-slate-500 mb-3">How it works</p>
        <h2 className="text-2xl md:text-3xl font-bold text-slate-50 mb-12">
          Fully automated. Zero manual steps.
        </h2>

        <div className="grid md:grid-cols-3 gap-6">
          {steps.map((step) => (
            <div key={step.n} className="relative rounded-xl border border-slate-800 bg-slate-900/60 p-6">
              <div className="text-3xl font-black text-slate-800 mb-4 select-none">{step.n}</div>
              <h3 className="text-sm font-semibold text-slate-100 mb-2">{step.title}</h3>
              <p className="text-sm text-slate-400 leading-relaxed">{step.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Divider */}
      <div className="max-w-4xl mx-auto px-6">
        <div className="h-px bg-gradient-to-r from-transparent via-slate-800 to-transparent" />
      </div>

      {/* Signal types */}
      <section className="px-6 py-20 max-w-4xl mx-auto">
        <p className="text-xs font-semibold uppercase tracking-widest text-slate-500 mb-3">Signal types</p>
        <h2 className="text-2xl md:text-3xl font-bold text-slate-50 mb-12">
          Four data sources in every briefing
        </h2>

        <div className="grid md:grid-cols-2 gap-4">
          {signals.map((s) => (
            <div key={s.label} className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 flex gap-4">
              <div className={`shrink-0 inline-flex items-center justify-center w-10 h-10 rounded-lg border ${s.color}`}>
                {s.icon}
              </div>
              <div>
                <h3 className="text-sm font-semibold text-slate-100 mb-1">{s.label}</h3>
                <p className="text-sm text-slate-400 leading-relaxed">{s.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Divider */}
      <div className="max-w-4xl mx-auto px-6">
        <div className="h-px bg-gradient-to-r from-transparent via-slate-800 to-transparent" />
      </div>

      {/* Beira example */}
      <section className="px-6 py-20 max-w-4xl mx-auto">
        <p className="text-xs font-semibold uppercase tracking-widest text-slate-500 mb-3">Example briefing</p>
        <h2 className="text-2xl md:text-3xl font-bold text-slate-50 mb-8">
          Imagery and external data, together
        </h2>

        <div className="rounded-xl border border-red-900/40 bg-gradient-to-br from-red-950/30 to-slate-900/60 p-6 md:p-8">
          <div className="flex items-center gap-3 mb-5">
            <div className="flex items-center justify-center w-8 h-8 rounded-full bg-red-500/20 shrink-0">
              <svg className="w-4 h-4 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" />
              </svg>
            </div>
            <div>
              <h3 className="text-base font-semibold text-red-300">Port of Beira, Mozambique</h3>
              <p className="text-xs text-slate-500">Severity 5/5 · Confidence: High · March 2026</p>
            </div>
          </div>

          <div className="grid md:grid-cols-2 gap-6">
            <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-4">
              <p className="text-xs font-semibold uppercase tracking-widest text-slate-500 mb-2">Satellite imagery said</p>
              <p className="text-sm text-slate-300 leading-relaxed">
                Vessels at berth. Yard stacks at expected levels. Cranes
                operating. Normal.
              </p>
            </div>
            <div className="rounded-lg border border-red-900/40 bg-red-950/20 p-4">
              <p className="text-xs font-semibold uppercase tracking-widest text-red-500/70 mb-2">External data said</p>
              <p className="text-sm text-slate-300 leading-relaxed">
                Tropical storm conditions. 12.5 days average vessel waiting
                time. Limited sheltered berthing.
              </p>
            </div>
          </div>

          <p className="mt-5 text-sm text-slate-400 leading-relaxed">
            SupplyWatch flagged severity 5/5. A single-modal model looking
            only at pixels would have called it normal. The system has
            explicit rules for when external evidence overrides ambiguous
            imagery.
          </p>

          <Link
            href="/port/beira-mozambique"
            className="inline-flex items-center gap-1.5 mt-5 text-sm text-blue-400 hover:text-blue-300 transition-colors"
          >
            View the full Beira briefing
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
            </svg>
          </Link>
        </div>
      </section>

      {/* Divider */}
      <div className="max-w-4xl mx-auto px-6">
        <div className="h-px bg-gradient-to-r from-transparent via-slate-800 to-transparent" />
      </div>

      {/* Bottom CTA */}
      <section className="px-6 py-20 max-w-4xl mx-auto text-center">
        <h2 className="text-2xl md:text-3xl font-bold text-slate-50 mb-3">
          All 68 ports are live
        </h2>
        <p className="text-slate-400 mb-8 max-w-md mx-auto">
          The dashboard updates daily. No login required to explore it.
        </p>
        <Link
          href="/demo"
          className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-6 py-3 text-sm font-semibold text-white hover:bg-blue-500 transition-colors shadow-lg shadow-blue-500/20"
        >
          Open the dashboard
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
          </svg>
        </Link>
      </section>

      {/* Footer */}
      <footer className="px-6 pb-12 max-w-4xl mx-auto border-t border-slate-800 pt-8">
        <div className="flex flex-wrap gap-6 text-sm text-slate-500">
          <Link href="/demo" className="hover:text-slate-300 transition-colors">
            Live dashboard
          </Link>
          <Link href="/how-it-works" className="hover:text-slate-300 transition-colors">
            Engineering story
          </Link>
          <span>Built by Tom Oliveri, 2026</span>
          <a href="https://github.com/tomoliveri/genai-supply-chain-vision" className="hover:text-slate-300 transition-colors" target="_blank" rel="noopener noreferrer">GitHub</a>
        </div>
      </footer>
    </div>
  );
}
