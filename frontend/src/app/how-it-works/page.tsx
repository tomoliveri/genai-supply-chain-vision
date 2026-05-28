import Link from 'next/link';

export default function HowItWorksPage() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-200">
      {/* Header */}
      <header className="px-6 py-6 max-w-3xl mx-auto border-b border-slate-800">
        <div className="flex items-center gap-3">
          <Link
            href="/"
            className="text-sm text-slate-500 hover:text-slate-300 transition-colors"
          >
            &larr; SupplyWatch
          </Link>
        </div>
        <h1 className="mt-4 text-2xl md:text-3xl font-bold text-slate-50 tracking-tight">
          Engineering story
        </h1>
        <p className="mt-2 text-sm text-slate-400">
          How this was built, what went wrong, and what the architecture looks
          like. Written for the hiring panel, not the user.
        </p>
      </header>

      <div className="px-6 max-w-3xl mx-auto space-y-16 py-12">
        {/* 1. The problem */}
        <section>
          <h2 className="text-lg font-semibold text-slate-50 mb-4">
            1. The problem
          </h2>
          <p className="text-sm text-slate-400 leading-relaxed">
            Mid-market manufacturers and logistics operators have almost no
            visibility into supply chain disruptions until a shipment is late.
            When a port closes in Panama, a cyclone hits Mozambique or labour
            action stalls Australian terminals, the typical manufacturer finds
            out when their freight forwarder sends an apologetic email. Usually
            a week after the fact.
          </p>
          <p className="mt-3 text-sm text-slate-400 leading-relaxed">
            Tier-1 supply chain visibility platforms (project44, FourKites,
            MarineTraffic) cost USD 100k+ annually and require integration
            projects measured in months. They are excellent products, but they
            are built for enterprises with dedicated logistics teams. The
            mid-market (companies moving 50-500 containers a year) gets left
            with spreadsheets and carrier portals.
          </p>
          <p className="mt-3 text-sm text-slate-400 leading-relaxed">
            SupplyWatch is a working demonstration that a usable geospatial
            disruption monitor is achievable with entirely free satellite data
            (ESA Sentinel-2), a current-generation multimodal model (Gemini
            2.5 Flash) and a handful of GCP services. Total monthly cost at
            demo scale: under AUD $25. Time from first line of code to a
            working dashboard with 68 ports: roughly three weeks of
            nights-and-weekends work.
          </p>
        </section>

        {/* 2. Architecture */}
        <section>
          <h2 className="text-lg font-semibold text-slate-50 mb-4">
            2. Architecture
          </h2>

          {/* Architecture diagram */}
          <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4 md:p-6 mb-6 overflow-x-auto">
            <div className="flex flex-col gap-3 min-w-[600px] text-xs">
              <div className="flex items-center justify-center">
                <div className="rounded-lg border border-amber-800/50 bg-amber-950/30 px-4 py-2 text-center">
                  <div className="font-semibold text-amber-300">
                    Cloud Scheduler
                  </div>
                  <div className="text-amber-500/70">Daily trigger, 2am UTC</div>
                </div>
              </div>

              <div className="flex justify-center text-slate-600">&#8595;</div>

              <div className="flex items-center justify-center">
                <div className="rounded-lg border border-blue-800/50 bg-blue-950/30 px-4 py-2 text-center min-w-[200px]">
                  <div className="font-semibold text-blue-300">
                    Cloud Run Job
                  </div>
                  <div className="text-blue-500/70">Python 3.13 pipeline</div>
                </div>
              </div>

              <div className="flex items-center justify-center gap-8">
                <div className="flex flex-col items-center">
                  <div className="text-slate-600 text-[10px] mb-1">queries</div>
                  <div className="rounded border border-slate-700 bg-slate-800 px-3 py-1.5 text-slate-300">
                    CDSE STAC API
                  </div>
                  <div className="text-slate-600 text-[10px] mt-1">Sentinel-2 L2A</div>
                </div>
                <div className="flex flex-col items-center">
                  <div className="text-slate-600 text-[10px] mb-1">reads creds</div>
                  <div className="rounded border border-slate-700 bg-slate-800 px-3 py-1.5 text-slate-300">
                    Secret Manager
                  </div>
                </div>
                <div className="flex flex-col items-center">
                  <div className="text-slate-600 text-[10px] mb-1">calls</div>
                  <div className="rounded border border-purple-700 bg-purple-950/30 px-3 py-1.5 text-purple-300">
                    Vertex AI
                  </div>
                  <div className="text-purple-500/70 text-[10px] mt-1">Gemini 2.5 Flash</div>
                </div>
                <div className="flex flex-col items-center">
                  <div className="text-slate-600 text-[10px] mb-1">queries</div>
                  <div className="rounded border border-slate-700 bg-slate-800 px-3 py-1.5 text-slate-300">
                    Open-Meteo API
                  </div>
                  <div className="text-slate-600 text-[10px] mt-1">weather archive</div>
                </div>
              </div>

              <div className="flex justify-center text-slate-600">&#8595;</div>

              <div className="flex items-center justify-center gap-8">
                <div className="rounded-lg border border-green-800/50 bg-green-950/30 px-4 py-2 text-center">
                  <div className="font-semibold text-green-300">GCS</div>
                  <div className="text-green-500/70">imagery cache</div>
                </div>
                <div className="rounded-lg border border-green-800/50 bg-green-950/30 px-4 py-2 text-center">
                  <div className="font-semibold text-green-300">Firestore</div>
                  <div className="text-green-500/70">briefings + watchlist</div>
                </div>
              </div>

              <div className="flex justify-center text-slate-600">&#8595;</div>

              <div className="flex items-center justify-center">
                <div className="rounded-lg border border-blue-800/50 bg-blue-950/30 px-4 py-2 text-center min-w-[200px]">
                  <div className="font-semibold text-blue-300">
                    Cloud Run Service
                  </div>
                  <div className="text-blue-500/70">Next.js 16 dashboard</div>
                </div>
              </div>
            </div>
          </div>

          <div className="space-y-3">
            <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-4">
              <h3 className="text-sm font-semibold text-slate-200">
                Daily pipeline (Cloud Run Job)
              </h3>
              <p className="mt-1 text-sm text-slate-400 leading-relaxed">
                Triggered by Cloud Scheduler at 2am UTC. Reads the watchlist
                from Firestore, gets a fresh CDSE OAuth token from Secret
                Manager, queries the Copernicus Data Space Ecosystem STAC API
                for the latest Sentinel-2 L2A scene per port with cloud cover
                under 10%, downloads the true-colour composite, crops it to a
                2km x 2km AOI around the port coordinates and uploads the JPEG
                to GCS. Uses the previous month&apos;s image as a baseline, then
                calls Gemini 2.5 Flash for the two-stage analysis.
              </p>
            </div>

            <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-4">
              <h3 className="text-sm font-semibold text-slate-200">
                Two-stage Gemini analysis
              </h3>
              <p className="mt-1 text-sm text-slate-400 leading-relaxed">
                Stage 1 (Observe): Gemini describes both images in free text:
                vessel count and position, quay activity, yard fill, water
                conditions, landside activity. No disruption assessment at this
                stage. Stage 2 (Assess): a separate call takes those
                observations plus external context (weather from Open-Meteo,
                labour events, geopolitical signals from a curated dataset of
                18 active events) and produces a structured{' '}
                <code className="text-xs bg-slate-800 px-1 py-0.5 rounded">
                  DisruptionAnalysis
                </code>{' '}
                JSON with severity score, confidence grade, disruption category
                and quantitative metrics.
              </p>
            </div>

            <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-4">
              <h3 className="text-sm font-semibold text-slate-200">
                Frontend (Cloud Run Service)
              </h3>
              <p className="mt-1 text-sm text-slate-400 leading-relaxed">
                Next.js 16 App Router, TypeScript strict, Tailwind CSS. Reads
                from Firestore in real time via the Firebase Web SDK. The
                landing page at{' '}
                <code className="text-xs bg-slate-800 px-1 py-0.5 rounded">
                  /
                </code>{' '}
                is a server component with no Firebase dependency. The
                dashboard at{' '}
                <code className="text-xs bg-slate-800 px-1 py-0.5 rounded">
                  /demo
                </code>{' '}
                is a client component with real-time Firestore subscriptions.
                Leaflet renders the interactive map with AOI rectangles drawn
                from port coordinates.
              </p>
            </div>

            <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-4">
              <h3 className="text-sm font-semibold text-slate-200">
                Infrastructure as code
              </h3>
              <p className="mt-1 text-sm text-slate-400 leading-relaxed">
                All GCP resources managed by Terraform with remote state in
                GCS: Cloud Run Job, Cloud Run Service, Cloud Scheduler,
                Artifact Registry, GCS buckets, Secret Manager secrets and IAM
                bindings. Each service account has only the permissions it
                needs. The frontend runner has no direct GCP permissions
                (Firebase is accessed from the browser). The pipeline runner
                has Firestore user, Vertex AI user, GCS object admin on one
                bucket and Secret Manager accessor on two secrets.
              </p>
            </div>
          </div>
        </section>

        {/* 3. Geospatial accuracy guardrail */}
        <section>
          <h2 className="text-lg font-semibold text-slate-50 mb-4">
            3. The geospatial accuracy problem
          </h2>
          <p className="text-sm text-slate-400 leading-relaxed">
            The hardest technical problem in this build was not the AI
            analysis. It was getting the geospatial code right. The failure
            modes are specific and hard to spot: a model will compute a WGS84
            bounding box correctly but pass it to a function expecting
            EPSG:3857. It will swap latitude and longitude because the
            training data is ambiguous about axis order. It will calculate a
            distance in degrees and apply it at 55 degrees north as if it were
            equatorial. These are not hallucinations. They are correct
            computations applied in the wrong coordinate space, invisible until
            you visualise the output on a map or run assertions against known
            reference points.
          </p>

          <p className="mt-3 text-sm text-slate-400 leading-relaxed">
            Write the code, run the tests, fix the failures. That approach
            breaks down when the code generator can&apos;t execute anything. You
            get a loop: the model generates code, you notice a problem, you
            describe it back, it generates new code with different bugs.
          </p>

          <div className="mt-4 rounded-lg border border-amber-800/50 bg-amber-950/20 p-4">
            <h3 className="text-sm font-semibold text-amber-300 mb-2">
              The agentic execution loop
            </h3>
            <p className="text-sm text-slate-300 leading-relaxed">
              I structured geospatial development as an agentic loop: the AI
              wrote code, a sandboxed Python runtime executed it immediately
              against real coordinate pairs, and assertion failures (wrong CRS,
              axis-order mismatch, out-of-bounds tile, projection drift over
              distance) became automatic feedback. The model saw the failure,
              the stack trace and the expected vs actual values, then iterated.
            </p>
            <p className="mt-2 text-sm text-slate-300 leading-relaxed">
              After several iterations the code stabilised. Each function
              acquired inline assertions: for every computed bounding box, check
              that the four corners form a valid WGS84 rectangle. For every
              tile index, check it matches a manual computation for a known
              reference point. For every distance calculation, validate against
              the Haversine formula. The assertions became the guardrail. They
              remain in the committed code and run as part of the test suite.
            </p>
          </div>

          <p className="mt-4 text-sm text-slate-400 leading-relaxed">
            Agentic code generation with an execution sandbox providing
            immediate, machine-readable feedback is the right approach for any
            geospatial work. Customer deployments routinely need
            coordinate-space code: geofencing, route matching, asset tracking,
            spatial queries. Without a tight execution loop, the bugs are
            silent and the debugging is brutal.
          </p>
        </section>

        {/* 4. Reasoning architecture */}
        <section>
          <h2 className="text-lg font-semibold text-slate-50 mb-4">
            4. Reasoning architecture
          </h2>
          <p className="text-sm text-slate-400 leading-relaxed">
            The Gemini analysis is not a one-shot call. The system separates
            observation from assessment. It is a two-stage chain-of-thought
            that stops the model jumping to conclusions based on superficial
            image features.
          </p>

          <p className="mt-3 text-sm text-slate-400 leading-relaxed">
            The system also weighs evidence types against each other. Satellite
            imagery is the primary signal, but it has a known failure mode: a
            port can look completely normal from orbit while being operationally
            dead. A court ruling voiding concessions in Panama (April 2026)
            stopped all vessel movement at Balboa and Cristobal, but the
            satellite image still showed berthed vessels and stacked containers.
            A single-modal system looking only at pixels would report normal
            operations. SupplyWatch injects external context (geopolitical
            events, weather data, labour actions) and has explicit rules about
            which evidence takes precedence.
          </p>

          <div className="mt-4 rounded-lg border border-slate-800 bg-slate-900/50 p-4">
            <h3 className="text-sm font-semibold text-slate-200 mb-2">
              Worked example: Beira, Mozambique
            </h3>
            <p className="text-sm text-slate-300 leading-relaxed">
              The Sentinel-2 image of Beira from March 2026 showed vessels at
              berth, yard stacks at expected levels and operating cranes. On
              imagery alone, severity 1 or 2 would have been reasonable.
              External weather data from Open-Meteo showed tropical storm
              conditions in the Mozambique Channel, with the port (limited
              sheltered berthing) reporting 12.5 days average vessel waiting
              time. The assessment prompt tells Gemini that severe weather with
              documented congestion at the specific port overrides ambiguous
              imagery. The result was severity 5/5 with high confidence.
            </p>
            <p className="mt-2 text-sm text-slate-300 leading-relaxed">
              The inverse also works: a port in a region with active
              geopolitical events but no direct impact on that specific terminal
              is not flagged. The prompt constrains external context to ports
              directly in the conflict zone or subject to the court ruling. This
              stops the system painting an entire region red because one nearby
              port has a problem.
            </p>
          </div>

          <p className="mt-4 text-sm text-slate-400 leading-relaxed">
            Primary signal from imagery, secondary signals from external data,
            explicit precedence rules encoded in the system. The alternative is
            a single-modal model that looks at pixels, reports what it sees and
            has no mechanism for knowing when the picture is incomplete.
          </p>
        </section>

        {/* 5. Cost engineering */}
        <section>
          <h2 className="text-lg font-semibold text-slate-50 mb-4">
            5. Cost
          </h2>
          <p className="text-sm text-slate-400 leading-relaxed">
            The entire system runs on under AUD $25/month at current demo scale
            (68 ports, daily analysis).
          </p>

          <div className="mt-4 overflow-x-auto">
            <div className="min-w-[500px] rounded-lg border border-slate-800 overflow-hidden">
              <div className="grid grid-cols-3 text-xs font-medium text-slate-400 bg-slate-800/50 px-4 py-2">
                <div>Service</div>
                <div>Monthly cost (AUD)</div>
                <div>Notes</div>
              </div>
              {[
                ['Cloud Run Job', '~$3.00', '2 vCPU, 4 GB, ~5 min/day. Scales to zero.'],
                ['Cloud Run Service', '~$2.00', '256 Mi, 1 vCPU. Scales to zero.'],
                ['Vertex AI (Gemini Flash)', '~$6.00', '136 images/day, 2 calls each.'],
                ['Firestore', '~$1.50', 'Reads: dashboard queries. Writes: 1 doc/port/day.'],
                ['GCS', '~$0.80', '~136 JPEGs/month at ~50 KB each. Lifecycle deletes after 90 days.'],
                ['Cloud Scheduler', '~$3.00', '1 job/day = 30 invocations/month ($0.10 each).'],
                ['Secret Manager', '~$0.50', '2 secrets, ~60 accesses/month.'],
                ['Sentinel-2 data', 'Free', 'ESA Copernicus programme. No API key required.'],
                ['Open-Meteo weather', 'Free', 'No API key. Archive API for historical backfill.'],
                ['Total', '~$16.80', ''],
              ].map(([service, cost, notes], i) => (
                <div
                  key={service}
                  className={`grid grid-cols-3 text-xs px-4 py-2 ${
                    service === 'Total'
                      ? 'bg-blue-950/30 text-blue-200 font-semibold border-t border-blue-800/30'
                      : i % 2 === 0
                        ? 'bg-slate-900/30 text-slate-300'
                        : 'text-slate-300'
                  }`}
                >
                  <div>{service}</div>
                  <div className={service === 'Total' ? 'text-blue-300' : 'text-slate-300'}>
                    {cost}
                  </div>
                  <div className="text-slate-500">{notes}</div>
                </div>
              ))}
            </div>
          </div>

          <p className="mt-4 text-sm text-slate-400 leading-relaxed">
            Cloud Run scales to zero between runs, so compute cost is
            proportional to usage, not uptime. Sentinel-2 data is free
            (taxpayer-funded by the EU Copernicus programme). Flash is used
            over Pro because its multimodal quality is sufficient for satellite
            imagery analysis and the cost difference compounds at scale across
            hundreds of ports and daily runs. GCS lifecycle policies delete
            imagery older than 90 days automatically.
          </p>
        </section>

        {/* 6. What I'd build next */}
        <section>
          <h2 className="text-lg font-semibold text-slate-50 mb-4">
            6. What I&apos;d build next
          </h2>
          <p className="text-sm text-slate-400 leading-relaxed mb-4">
            Scoped as if for a real customer with a supply chain visibility
            budget of around AUD $5,000/month.
          </p>

          <div className="space-y-3">
            {[
              {
                title: 'SAR integration (Sentinel-1) for cloud-covered regions',
                body: 'Sentinel-2 optical imagery fails when there is cloud cover. Many of the most disrupted ports are in tropical regions where cloud cover exceeds 50% on most days. Sentinel-1 C-band SAR penetrates cloud and provides backscatter intensity that can detect vessel presence, yard fill changes and infrastructure changes. The challenge is that SAR imagery requires different preprocessing (radiometric calibration, speckle filtering, geocoding) and the Gemini prompts need a different visual vocabulary. A production system would run both: Sentinel-2 as primary, Sentinel-1 as the fallback when cloud cover exceeds the threshold.',
              },
              {
                title: 'Customer-specific anomaly types',
                body: 'The current system detects generic disruption categories (weather, congestion, labour, incident). A real deployment would define custom anomaly types per customer: an automotive manufacturer cares about RoRo terminal congestion and parts-container dwell times, a retailer cares about yard fill at intermodal rail yards, an electronics manufacturer cares about air freight terminal throughput. Each custom type maps to specific observable features in the imagery and specific external data sources, and the Gemini prompt is parameterised per customer.',
              },
              {
                title: 'Email and Slack briefing delivery',
                body: 'The dashboard is useful for exploration, but most supply chain operators need briefings pushed to them. A delivery layer would maintain per-user port watchlists, generate a daily summary email with the top 3-5 disrupted ports, send Slack/Teams notifications for severity-4-and-above events within 30 minutes of detection, and support configurable quiet hours and severity thresholds per user.',
              },
              {
                title: 'Shipment impact estimation',
                body: 'The highest-value feature: if a customer provides a CSV of active shipments (container IDs, ETD, ETA, origin port, destination port, carrier), the system cross-references disruption data to estimate which shipments are likely delayed and by how many days, with a probability distribution rather than a point estimate, plus alternative routing options with cost/time trade-offs. This is what moves SupplyWatch from a monitoring tool to something that changes procurement decisions.',
              },
            ].map((item) => (
              <div
                key={item.title}
                className="rounded-lg border border-slate-800 bg-slate-900/50 p-4"
              >
                <h3 className="text-sm font-semibold text-slate-200">
                  {item.title}
                </h3>
                <p className="mt-1 text-sm text-slate-400 leading-relaxed">
                  {item.body}
                </p>
              </div>
            ))}
          </div>
        </section>

        {/* 7. Source */}
        <section>
          <h2 className="text-lg font-semibold text-slate-50 mb-4">
            7. Source code
          </h2>
          <p className="text-sm text-slate-400 leading-relaxed">
            SupplyWatch is open source. The repository contains the full
            backend pipeline (Python), frontend dashboard
            (Next.js/TypeScript), Terraform infrastructure definitions and
            this documentation.
          </p>
          <p className="mt-2 text-sm text-slate-500">
            GitHub repository: link coming soon. Contact Tom Oliveri for
            access in the meantime.
          </p>
        </section>
      </div>

      {/* Footer */}
      <footer className="px-6 pb-12 max-w-3xl mx-auto border-t border-slate-800 pt-8">
        <div className="flex flex-wrap gap-6 text-sm text-slate-500">
          <Link href="/" className="hover:text-slate-300 transition-colors">
            Home
          </Link>
          <Link href="/demo" className="hover:text-slate-300 transition-colors">
            Live dashboard
          </Link>
          <span>Built by Tom Oliveri, 2026</span>
        </div>
      </footer>
    </div>
  );
}
