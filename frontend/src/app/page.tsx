import Link from 'next/link';

const stats = [
  { label: 'Ports monitored', value: '68' },
  { label: 'Run cadence', value: 'Daily' },
  { label: 'Demo cost', value: '< AUD $25/mo' },
  { label: 'Source imagery', value: 'Sentinel-2' },
];

const signals = [
  {
    label: 'Weather',
    desc: 'Storms, fog, high swell, wind suspensions, and flooding from Open-Meteo context plus visible imagery changes.',
  },
  {
    label: 'Congestion',
    desc: 'Vessel queues, berth saturation, yard pressure, equipment constraints, and dwell-time indicators.',
  },
  {
    label: 'Labour',
    desc: 'Strike warnings, active stoppages, overtime bans, and port-wide industrial action.',
  },
  {
    label: 'Geopolitical',
    desc: '19 tracked events covering conflict, security incidents, court rulings, route disruption, and trade policy.',
  },
];

const steps = [
  {
    n: '01',
    title: 'Acquire',
    desc: 'Cloud Scheduler starts the batch job. Each port gets the latest low-cloud Sentinel-2 scene, cropped to the port AOI and cached in GCS.',
  },
  {
    n: '02',
    title: 'Assess',
    desc: 'Gemini first describes the imagery, then produces a structured assessment using imagery plus weather, labour, and geopolitical context.',
  },
  {
    n: '03',
    title: 'Brief',
    desc: 'Firestore receives a typed briefing with severity, confidence, category, vessel counts, yard fill, and the analyst summary.',
  },
];

export default function LandingPage() {
  return (
    <div className="min-h-[100dvh] bg-[#f5f2ea] text-[#171713] antialiased">
      <header className="border-b border-[#d8d0c0]">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4 sm:px-6">
          <Link href="/" className="text-sm font-semibold tracking-tight">
            SupplyWatch
          </Link>
          <nav className="flex items-center gap-5 text-sm text-[#5f5a4f]">
            <Link href="/demo" className="hover:text-[#171713]">
              Dashboard
            </Link>
            <Link href="/how-it-works" className="hover:text-[#171713]">
              Engineering
            </Link>
          </nav>
        </div>
      </header>

      <main>
        <section className="mx-auto grid max-w-6xl gap-10 px-4 py-14 sm:px-6 md:grid-cols-[1.05fr_0.95fr] md:py-20">
          <div>
            <p className="mb-4 text-xs font-semibold uppercase tracking-[0.18em] text-[#776f60]">
              Daily geospatial supply-chain briefings
            </p>
            <h1 className="max-w-3xl text-4xl font-semibold leading-tight tracking-tight text-[#171713] md:text-6xl">
              Port disruption intelligence from satellite imagery and external signals.
            </h1>
            <p className="mt-6 max-w-2xl text-base leading-7 text-[#5f5a4f] md:text-lg">
              SupplyWatch monitors 68 major ports with Sentinel-2 imagery,
              Gemini Flash, and curated operational context. The dashboard is a
              live demo: no account required.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                href="/demo"
                className="inline-flex min-h-11 items-center rounded-md bg-[#171713] px-5 text-sm font-semibold text-[#f5f2ea] hover:bg-[#343126]"
              >
                Open dashboard
              </Link>
              <Link
                href="/how-it-works"
                className="inline-flex min-h-11 items-center rounded-md border border-[#bdb39f] px-5 text-sm font-semibold text-[#343126] hover:border-[#171713]"
              >
                Read engineering story
              </Link>
            </div>
          </div>

          <div className="self-end rounded-md border border-[#cfc6b4] bg-[#fbfaf6] p-4 shadow-sm">
            <div className="border-b border-[#dfd8ca] pb-3">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#776f60]">
                Current briefing format
              </p>
              <div className="mt-3 flex items-start justify-between gap-4">
                <div>
                  <h2 className="text-lg font-semibold">Port of Beira, Mozambique</h2>
                  <p className="mt-1 text-sm text-[#6d6558]">
                    Severity 5/5 · High confidence · Congestion
                  </p>
                </div>
                <span className="rounded-sm bg-[#9f2d20] px-2 py-1 text-xs font-semibold text-white">
                  Active
                </span>
              </div>
            </div>

            <div className="grid gap-3 py-4 text-sm sm:grid-cols-3">
              <div>
                <p className="text-xs uppercase tracking-[0.14em] text-[#8a8172]">Yard fill</p>
                <p className="mt-1 text-2xl font-semibold">85%</p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-[0.14em] text-[#8a8172]">At berth</p>
                <p className="mt-1 text-2xl font-semibold">10</p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-[0.14em] text-[#8a8172]">Anchorage</p>
                <p className="mt-1 text-2xl font-semibold">0</p>
              </div>
            </div>

            <p className="border-t border-[#dfd8ca] pt-3 text-sm leading-6 text-[#5f5a4f]">
              Double-digit vessel waiting times and high yard utilization point
              to severe congestion even though the terminal still appears active
              from orbit.
            </p>
          </div>
        </section>

        <section className="border-y border-[#d8d0c0] bg-[#ebe5d8]">
          <div className="mx-auto grid max-w-6xl gap-px px-4 py-px sm:grid-cols-4 sm:px-6">
            {stats.map((s) => (
              <div key={s.label} className="bg-[#ebe5d8] py-5 sm:bg-[#f5f2ea] sm:px-5">
                <p className="text-2xl font-semibold tracking-tight">{s.value}</p>
                <p className="mt-1 text-xs uppercase tracking-[0.14em] text-[#776f60]">{s.label}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-4 py-14 sm:px-6 md:py-18">
          <div className="grid gap-8 md:grid-cols-[0.8fr_1.2fr]">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#776f60]">
                Pipeline
              </p>
              <h2 className="mt-3 text-2xl font-semibold tracking-tight md:text-3xl">
                Three stages, no manual review step.
              </h2>
            </div>
            <div className="grid gap-4">
              {steps.map((step) => (
                <div key={step.n} className="grid gap-4 border-t border-[#d8d0c0] pt-4 sm:grid-cols-[4rem_1fr]">
                  <p className="font-mono text-sm text-[#8a8172]">{step.n}</p>
                  <div>
                    <h3 className="text-sm font-semibold">{step.title}</h3>
                    <p className="mt-1 text-sm leading-6 text-[#5f5a4f]">{step.desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="border-y border-[#d8d0c0] bg-[#fbfaf6]">
          <div className="mx-auto max-w-6xl px-4 py-14 sm:px-6 md:py-18">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#776f60]">
              Signal types
            </p>
            <div className="mt-6 grid gap-4 md:grid-cols-2">
              {signals.map((s) => (
                <div key={s.label} className="border-t border-[#d8d0c0] pt-4">
                  <h3 className="text-sm font-semibold">{s.label}</h3>
                  <p className="mt-2 text-sm leading-6 text-[#5f5a4f]">{s.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-4 py-14 sm:px-6 md:py-18">
          <div className="grid gap-8 md:grid-cols-[0.8fr_1.2fr]">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#776f60]">
                Worked example
              </p>
              <h2 className="mt-3 text-2xl font-semibold tracking-tight md:text-3xl">
                Static explanation, live dashboard.
              </h2>
            </div>
            <div className="rounded-md border border-[#cfc6b4] bg-[#fbfaf6] p-5">
              <p className="text-sm leading-6 text-[#5f5a4f]">
                The Beira example is static copy from the current dataset, used
                to explain why a multimodal system matters. The live route
                remains the source of truth when future daily runs change the
                briefing.
              </p>
              <div className="mt-5 grid gap-4 md:grid-cols-2">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#8a8172]">
                    Imagery alone
                  </p>
                  <p className="mt-2 text-sm leading-6 text-[#343126]">
                    Vessels at berth, yard stacks visible, cranes operating.
                    The port can look active.
                  </p>
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#8a8172]">
                    Combined assessment
                  </p>
                  <p className="mt-2 text-sm leading-6 text-[#343126]">
                    Yard pressure near 85%, double-digit waiting times, and
                    corridor risk make this a severe congestion briefing.
                  </p>
                </div>
              </div>
              <Link
                href="/port/beira-mozambique"
                className="mt-5 inline-flex text-sm font-semibold text-[#284f3b] hover:text-[#171713]"
              >
                Open Beira in the live dashboard
              </Link>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-[#d8d0c0]">
        <div className="mx-auto flex max-w-6xl flex-wrap gap-5 px-4 py-8 text-sm text-[#6d6558] sm:px-6">
          <Link href="/demo" className="hover:text-[#171713]">
            Live dashboard
          </Link>
          <Link href="/how-it-works" className="hover:text-[#171713]">
            Engineering story
          </Link>
          <a
            href="https://github.com/tomoliveri/genai-supply-chain-vision"
            className="hover:text-[#171713]"
            target="_blank"
            rel="noopener noreferrer"
          >
            GitHub
          </a>
          <span>Built by Tom Oliveri, 2026</span>
        </div>
      </footer>
    </div>
  );
}
