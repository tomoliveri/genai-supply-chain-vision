import { DashboardContent } from '@/components/DashboardContent';

interface DemoPageProps {
  searchParams: Promise<{ port?: string }>;
}

/**
 * Server component: reads the `port` query param and passes it to the
 * client-side dashboard.  This avoids the `useSearchParams()` Suspense
 * boundary requirement.
 */
export default async function DemoPage({ searchParams }: DemoPageProps) {
  const params = await searchParams;
  return <DashboardContent portSlug={params.port ?? null} />;
}
