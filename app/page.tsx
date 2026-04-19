import Link from "next/link";

export default function Home() {
  return (
    <div className="font-sans flex items-center justify-center min-h-screen bg-gray-950 text-white">
      <main className="flex flex-col gap-6 items-center text-center px-8">
        <h1 className="text-3xl font-bold">Stock Dashboard</h1>
        <p className="text-gray-400 max-w-sm">
          Live tracking for Peter Wolff Flagship Fund, AI World War III Portfolio, and Photonics is Next — with price alerts.
        </p>
        <Link
          href="/dashboard"
          className="rounded-full bg-blue-600 hover:bg-blue-700 text-white font-semibold text-sm px-8 py-3 transition-colors"
        >
          Open Dashboard →
        </Link>
      </main>
    </div>
  );
}
