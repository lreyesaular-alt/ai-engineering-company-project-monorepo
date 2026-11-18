"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "../../lib/api";
import { getToken } from "../../lib/auth";

type LocationPerformance = {
  location_id: string;
  country: "CO" | "US";
  currency: "COP" | "USD";
  week_start: string;
  total_purchase_cost: number;
  total_waste_cost: number;
  waste_ratio: number;
  stockout_events_count: number;
  price_alert_events_count: number;
  computed_at: string;
};

type WeeklyReport = {
  week_start: string;
  locations: LocationPerformance[];
};

function currentMonday(): string {
  const today = new Date();
  const day = today.getDay();
  const monday = new Date(today);
  monday.setDate(today.getDate() - ((day + 6) % 7));

  const year = monday.getFullYear();
  const month = String(monday.getMonth() + 1).padStart(2, "0");
  const date = String(monday.getDate()).padStart(2, "0");

  return `${year}-${month}-${date}`;
}

function isMonday(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const date = new Date(`${value}T12:00:00Z`);
  return !Number.isNaN(date.getTime()) &&
    date.toISOString().slice(0, 10) === value &&
    date.getUTCDay() === 1;
}

function money(value: number, currency: "COP" | "USD"): string {
  return new Intl.NumberFormat("es-CO", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(value);
}

export default function ReportingPage() {
  const router = useRouter();
  const [weekStart, setWeekStart] = useState("");
  const [report, setReport] = useState<WeeklyReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadReport = useCallback(async (week: string) => {
    if (!isMonday(week)) {
      setError("Selecciona un lunes como inicio de semana.");
      setReport(null);
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError("");
      setReport(null);

      const response = await api(
        `/reporting/weekly-location-performance?week_start=${encodeURIComponent(week)}`
      );
      const data: WeeklyReport = await response.json();

      if (!data || !Array.isArray(data.locations)) {
        throw new Error("La API devolvio un reporte invalido.");
      }

      setReport(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "No se pudo cargar el reporte."
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }

    if (!weekStart) {
      const timer = window.setTimeout(() => {
        setWeekStart(currentMonday());
      }, 0);
      return () => window.clearTimeout(timer);
    }

    const timer = window.setTimeout(() => {
      void loadReport(weekStart);
    }, 0);

    return () => window.clearTimeout(timer);
  }, [router, loadReport, weekStart]);

  return (
    <main className="min-h-screen bg-zinc-100 p-8">
      <div className="mx-auto max-w-7xl">
        <header className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-medium text-zinc-500">BRASALAND</p>
            <h1 className="text-3xl font-bold text-zinc-900">
              Desempe?o semanal de negocio
            </h1>
            <p className="mt-1 text-zinc-600">
              Compras, desperdicios, roturas de stock y alertas por ubicaci?n.
            </p>
          </div>
          <Link
            href="/"
            className="rounded-lg border border-zinc-300 bg-white px-4 py-2 text-sm font-medium text-zinc-900 hover:bg-zinc-50"
          >
            Volver al inicio
          </Link>
        </header>

        <section className="mb-6 rounded-xl border bg-white p-5 shadow-sm">
          <label htmlFor="week-start" className="block text-sm font-medium text-zinc-700">
            Inicio de semana (lunes)
          </label>
          <div className="mt-2 flex flex-wrap items-center gap-3">
            <input
              id="week-start"
              type="date"
              value={weekStart}
              onChange={(event) => setWeekStart(event.target.value)}
              className="rounded-lg border border-zinc-300 px-3 py-2 text-zinc-900"
            />
            <button
              type="button"
              onClick={() => void loadReport(weekStart)}
              disabled={loading || !isMonday(weekStart)}
              className="rounded-lg bg-black px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-50"
            >
              Actualizar reporte
            </button>
          </div>
          <p className="mt-2 text-xs text-zinc-500">
            Los importes se muestran en la moneda de cada ubicaci?n: COP o USD.
          </p>
        </section>

        {loading && (
          <div className="rounded-xl border bg-white p-6 text-zinc-600 shadow-sm">
            Cargando indicadores semanales...
          </div>
        )}

        {!loading && error && (
          <div className="rounded-xl border border-red-200 bg-red-50 p-6">
            <p className="font-medium text-red-800">No se pudo cargar el reporte</p>
            <p className="mt-1 text-sm text-red-700">{error}</p>
          </div>
        )}

        {!loading && !error && report && report.locations.length === 0 && (
          <div className="rounded-xl border bg-white p-6 shadow-sm">
            <h2 className="font-semibold text-zinc-900">
              Sin datos para la semana {report.week_start}
            </h2>
            <p className="mt-2 text-sm text-zinc-600">
              Todav?a no hay indicadores calculados para esta semana.
              Comprueba la ejecuci?n del pipeline y la disponibilidad de
              costos monetarios en la telemetr?a.
            </p>
          </div>
        )}

        {!loading && !error && report && report.locations.length > 0 && (
          <section className="rounded-xl border bg-white p-5 shadow-sm">
            <div className="mb-4">
              <h2 className="text-xl font-semibold text-zinc-900">
                Indicadores por ubicaci?n
              </h2>
              <p className="mt-1 text-sm text-zinc-500">
                Semana del {report.week_start} ? {report.locations.length} ubicaciones
              </p>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-left text-sm">
                <thead>
                  <tr className="border-b bg-zinc-50 text-zinc-700">
                    <th className="px-3 py-3">Ubicaci?n</th>
                    <th className="px-3 py-3">Pa?s</th>
                    <th className="px-3 py-3">Costo de compras</th>
                    <th className="px-3 py-3">Costo de desperdicios</th>
                    <th className="px-3 py-3">Ratio de desperdicio</th>
                    <th className="px-3 py-3">Roturas de stock</th>
                    <th className="px-3 py-3">Alertas de precio</th>
                  </tr>
                </thead>
                <tbody>
                  {report.locations.map((row) => (
                    <tr
                      key={`${row.location_id}-${row.week_start}`}
                      className="border-b last:border-0"
                    >
                      <td className="px-3 py-3 font-medium text-zinc-900">
                        {row.location_id}
                      </td>
                      <td className="px-3 py-3 text-zinc-600">{row.country}</td>
                      <td className="whitespace-nowrap px-3 py-3">
                        {money(row.total_purchase_cost, row.currency)}
                      </td>
                      <td className="whitespace-nowrap px-3 py-3">
                        {money(row.total_waste_cost, row.currency)}
                      </td>
                      <td className="px-3 py-3">
                        {(row.waste_ratio * 100).toFixed(2)}%
                      </td>
                      <td className="px-3 py-3">{row.stockout_events_count}</td>
                      <td className="px-3 py-3">{row.price_alert_events_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </div>
    </main>
  );
}
