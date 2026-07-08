import Link from "next/link";

export default function Home() {
  return (
    <div className="font-sans flex items-center justify-center min-h-screen bg-gray-950 text-white">
      <main className="flex flex-col gap-6 items-center text-center px-8">
        <h1 className="text-3xl font-bold">Stock Dashboard</h1>
        <p className="text-gray-400 max-w-sm">
          Live tracking for Peter Wolff Flagship Fund, AI World War III Portfolio, and Photonics is Next — with price alerts.
        </p>
        <div className="flex flex-wrap justify-center gap-3">
          <Link
            href="/dashboard"
            className="rounded-full bg-blue-600 hover:bg-blue-700 text-white font-semibold text-sm px-8 py-3 transition-colors"
          >
            Open Dashboard →
          </Link>
          <Link
            href="/revisions"
            className="rounded-full bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-sm px-8 py-3 transition-colors"
          >
            Revision Velocity →
          </Link>
        </div>
      </main>
    </div>
  );
}
