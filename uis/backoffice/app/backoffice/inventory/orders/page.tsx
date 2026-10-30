"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  getInventoryOrders,
  InventoryOrder,
} from "../../../../lib/inventory";
import { getToken } from "../../../../lib/auth";

export default function InventoryOrdersPage() {
  const router = useRouter();

  const [orders, setOrders] = useState<InventoryOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function loadOrders() {
    try {
      setLoading(true);
      setError("");

      const data = await getInventoryOrders();
      setOrders(data);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "No se pudo cargar el historial."
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }

    loadOrders();
  }, [router]);

  function formatDate(value: string) {
    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
      return value;
    }

    return date.toLocaleString("es-ES");
  }

  return (
    <main className="min-h-screen bg-zinc-100 p-6">
      <div className="mx-auto max-w-7xl">
        <header className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <Link
              href="/backoffice/inventory/products"
              className="text-sm font-medium text-zinc-600 hover:text-zinc-900"
            >
              ← Volver a productos
            </Link>

            <h1 className="mt-4 text-3xl font-bold text-zinc-900">
              Historial de órdenes
            </h1>

            <p className="mt-1 text-zinc-600">
              Consulta todas las entradas y salidas registradas.
            </p>
          </div>
        </header>

        {loading && (
          <section className="rounded-xl border bg-white p-8 text-center shadow-sm">
            Cargando historial...
          </section>
        )}

        {!loading && error && (
          <section className="rounded-xl border border-red-200 bg-red-50 p-6">
            <h2 className="font-semibold text-red-800">
              No se pudo cargar el historial
            </h2>

            <p className="mt-2 text-sm text-red-700">
              {error}
            </p>

            <button
              onClick={loadOrders}
              className="mt-4 rounded-lg bg-red-700 px-4 py-2 text-sm font-medium text-white"
            >
              Reintentar
            </button>
          </section>
        )}

        {!loading && !error && (
          <section className="overflow-hidden rounded-xl border bg-white shadow-sm">
            {orders.length === 0 ? (
              <div className="p-8 text-center text-zinc-500">
                No hay órdenes registradas.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="border-b bg-zinc-50">
                    <tr>
                      <th className="px-5 py-4">Producto</th>
                      <th className="px-5 py-4">Cantidad</th>
                      <th className="px-5 py-4">Tipo</th>
                      <th className="px-5 py-4">Motivo / Proveedor</th>
                      <th className="px-5 py-4">Local</th>
                      <th className="px-5 py-4">Fecha</th>
                      <th className="px-5 py-4">Usuario</th>
                    </tr>
                  </thead>

                  <tbody>
                    {orders.map((order) => (
                      <tr
                        key={`${order.type}-${order.id}`}
                        className="border-b last:border-0 hover:bg-zinc-50"
                      >
                        <td className="px-5 py-4 font-medium text-zinc-900">
                          {order.ingredient_name}
                        </td>

                        <td className="px-5 py-4">
                          {order.quantity}
                        </td>

                        <td className="px-5 py-4">
                          <span
                            className={`rounded-full px-3 py-1 text-xs font-semibold ${
                              order.type === "inbound"
                                ? "bg-green-100 text-green-700"
                                : "bg-red-100 text-red-700"
                            }`}
                          >
                            {order.type === "inbound"
                              ? "Entrada"
                              : "Salida"}
                          </span>
                        </td>

                        <td className="px-5 py-4 text-zinc-600">
                          {order.type === "inbound"
                            ? order.supplier_name
                            : order.reason === "waste"
                              ? "Merma"
                              : "Consumo"}
                        </td>

                        <td className="px-5 py-4 text-zinc-600">
                          {order.location_id}
                        </td>

                        <td className="whitespace-nowrap px-5 py-4 text-zinc-600">
                          {formatDate(order.created_at)}
                        </td>

                        <td className="px-5 py-4 text-xs text-zinc-500">
                          {order.user_uuid}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        )}
      </div>
    </main>
  );
}
