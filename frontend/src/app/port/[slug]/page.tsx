import { redirect } from 'next/navigation';

interface PortPageProps {
  params: Promise<{ slug: string }>;
}

/**
 * Deep-link route: /port/beira-mozambique → /demo?port=beira-mozambique
 *
 * The demo page reads the `port` query param, slugifies each location_name
 * from Firestore, and auto-opens the matching port's briefing drawer.
 */
export default async function PortPage({ params }: PortPageProps) {
  const { slug } = await params;
  redirect(`/demo?port=${encodeURIComponent(slug)}`);
}
