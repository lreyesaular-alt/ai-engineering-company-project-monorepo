
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  getIngredients,
  Ingredient,
} from "../../../../lib/inventory";
import { getToken } from "../../../../lib/auth";

export default function InventoryProductsPage() {
  const router = useRouter();

  const [ingredients, setIngredients] = useState<Ingredient[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function loadIngredients() {
    try {
      setLoading(true);
      setError("");

      const data = await getIngredients();
      setIngredients(data);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "No se pudieron cargar los ingredientes."
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

    loadIngredients();
  }, [router]);

  function getStockClass(stock: number) {
    if (stock <= 10) {
      return "bg-red-100 text-red-700";
    }

    return "bg-green-100 text-green-700";
  }

  function getStockLabel(stock: number) {
    return stock <= 10 ? "Stock bajo" : "Stock saludable";
  }

  function getCategoryLabel(category: string) {
    const labels: Record<string, string> = {
      meat: "Carne",
      produce: "Producto fresco",
      sauce: "Salsa",
      beverage: "Bebida",
      packaging: "Packaging",
      cleaning: "Limpieza",
    };

    return labels[category] ?? category;
  }

  return (
    <main className="min-h-screen bg-zinc-100 p-6">
      <div className="mx-auto max-w-7xl">
        <header className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-medium text-zinc-500">
              BRASALAND · BACKOFFICE
            </p>

            <h1 className="text-3xl font-bold text-zinc-900">
              Gestión de Inventario
            </h1>

            <p className="mt-1 text-zinc-600">
              Consulta el stock actual de ingredientes.
            </p>
          </div>

          <Link
            href="/"
            className="rounded-lg border border-zinc-300 bg-white px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50"
          >
            Volver al inicio
          </Link>
        </header>

        <nav className="mb-6 flex flex-wrap gap-2">
          <Link
            href="/backoffice/inventory/products"
            className="rounded-lg bg-black px-4 py-2 text-sm font-medium text-white"
          >
            Productos
          </Link>

          <Link
            href="/backoffice/inventory/orders/inbound"
            className="rounded-lg border bg-white px-4 py-2 text-sm font-medium"
          >
            Registrar entrada
          </Link>

          <Link
            href="/backoffice/inventory/orders/outbound"
            className="rounded-lg border bg-white px-4 py-2 text-sm font-medium"
          >
            Registrar salida
          </Link>

          <Link
            href="/backoffice/inventory/orders"
            className="rounded-lg border bg-white px-4 py-2 text-sm font-medium"
          >
            Historial
          </Link>
        </nav>

        {loading && (
          <section className="rounded-xl border bg-white p-8 text-center shadow-sm">
            Cargando ingredientes...
          </section>
        )}

        {!loading && error && (
          <section className="rounded-xl border border-red-200 bg-red-50 p-6">
            <h2 className="font-semibold text-red-800">
              No se pudo cargar el inventario
            </h2>

            <p className="mt-2 text-sm text-red-700">
              {error}
            </p>

            <button
              type="button"
              onClick={loadIngredients}
              className="mt-4 rounded-lg bg-red-700 px-4 py-2 text-sm font-medium text-white"
            >
              Reintentar
            </button>
          </section>
        )}

        {!loading && !error && (
          <section className="overflow-hidden rounded-xl border bg-white shadow-sm">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b bg-zinc-50">
                  <tr>
                    <th className="px-5 py-4">
                      Ingrediente
                    </th>

                    <th className="px-5 py-4">
                      SKU
                    </th>

                    <th className="px-5 py-4">
                      Categoría
                    </th>

                    <th className="px-5 py-4">
                      País
                    </th>

                    <th className="px-5 py-4">
                      Stock actual
                    </th>

                    <th className="px-5 py-4">
                      Acciones
                    </th>
                  </tr>
                </thead>

                <tbody>
                  {ingredients.map((ingredient) => (
                    <tr
                      key={ingredient.id}
                      className="border-b last:border-0 hover:bg-zinc-50"
                    >
                      <td className="px-5 py-4 font-medium text-zinc-900">
                        {ingredient.name}
                      </td>

                      <td className="px-5 py-4 text-zinc-600">
                        {ingredient.sku}
                      </td>

                      <td className="px-5 py-4 text-zinc-600">
                        {getCategoryLabel(
                          ingredient.category
                        )}
                      </td>

                      <td className="px-5 py-4 text-zinc-600">
                        {ingredient.country}
                      </td>

                      <td className="px-5 py-4">
                        <div className="flex flex-col items-start gap-1">
                          <span
                            className={`rounded-full px-3 py-1 font-semibold ${getStockClass(
                              ingredient.current_stock
                            )}`}
                          >
                            {ingredient.current_stock}{" "}
                            {ingredient.unit}
                          </span>

                          <span className="text-xs text-zinc-500">
                            {getStockLabel(
                              ingredient.current_stock
                            )}
                          </span>
                        </div>
                      </td>

                      <td className="px-5 py-4">
                        <div className="flex flex-wrap gap-2">
                          <Link
                            href={`/backoffice/inventory/orders/inbound?ingredient=${ingredient.id}`}
                            className="rounded-lg bg-zinc-900 px-3 py-2 text-xs font-medium text-white"
                          >
                            Entrada
                          </Link>

                          <Link
                            href={`/backoffice/inventory/orders/outbound?ingredient=${ingredient.id}`}
                            className="rounded-lg border border-zinc-300 px-3 py-2 text-xs font-medium text-zinc-800"
                          >
                            Salida
                          </Link>
                        </div>
                      </td>
                    </tr>
                  ))}

                  {ingredients.length === 0 && (
                    <tr>
                      <td
                        colSpan={6}
                        className="px-5 py-10 text-center text-zinc-500"
                      >
                        No hay ingredientes registrados.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </div>
    </main>
  );
}
