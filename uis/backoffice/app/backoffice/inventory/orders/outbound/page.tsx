
"use client";

import { FormEvent, Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  createOutboundOrder,
  getIngredient,
  getIngredients,
  getUserUuid,
  Ingredient,
} from "../../../../../lib/inventory";
import { getToken } from "../../../../../lib/auth";

function OutboundPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [ingredients, setIngredients] = useState<Ingredient[]>([]);
  const [ingredientId, setIngredientId] = useState("");
  const [selectedIngredient, setSelectedIngredient] =
    useState<Ingredient | null>(null);
  const [quantity, setQuantity] = useState("");
  const [reason, setReason] = useState<"consumption" | "waste">(
    "consumption"
  );
  const [locationId, setLocationId] = useState("1");
  const [loading, setLoading] = useState(true);
  const [stockLoading, setStockLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }

    async function load() {
      try {
        setLoading(true);
        setError("");

        const data = await getIngredients();
        setIngredients(data);

        const selected = searchParams.get("ingredient");

        if (
          selected &&
          data.some(
            (ingredient) => String(ingredient.id) === selected
          )
        ) {
          setIngredientId(selected);
        }
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

    load();
  }, [router, searchParams]);

  useEffect(() => {
    if (!ingredientId) {
      setSelectedIngredient(null);
      return;
    }

    async function loadStock() {
      try {
        setStockLoading(true);
        setError("");

        const ingredient = await getIngredient(Number(ingredientId));

        setSelectedIngredient(ingredient);
      } catch (err) {
        setSelectedIngredient(null);
        setError(
          err instanceof Error
            ? err.message
            : "No se pudo consultar el stock."
        );
      } finally {
        setStockLoading(false);
      }
    }

    loadStock();
  }, [ingredientId]);

  const requestedQuantity = Number(quantity) || 0;

  const availableStock =
    selectedIngredient?.current_stock ?? 0;

  const exceedsStock =
    requestedQuantity > 0 &&
    requestedQuantity > availableStock;

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();

    setError("");
    setMessage("");

    if (!ingredientId) {
      setError("Selecciona un ingrediente.");
      return;
    }

    if (!requestedQuantity || requestedQuantity <= 0) {
      setError("Introduce una cantidad válida.");
      return;
    }

    if (exceedsStock) {
      setError(
        `No puedes registrar ${requestedQuantity} ${
          selectedIngredient?.unit ?? ""
        }. Solo hay ${availableStock} disponibles.`
      );
      return;
    }

    try {
      setSubmitting(true);

      await createOutboundOrder({
        ingredient_id: Number(ingredientId),
        quantity: requestedQuantity,
        reason,
        location_id: Number(locationId),
        user_uuid: getUserUuid(),
      });

      setQuantity("");
      setMessage("Salida registrada correctamente.");

      const refreshed = await getIngredient(
        Number(ingredientId)
      );

      setSelectedIngredient(refreshed);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "No se pudo registrar la salida."
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="min-h-screen bg-zinc-100 p-6">
      <div className="mx-auto max-w-3xl">
        <header className="mb-6">
          <Link
            href="/backoffice/inventory/products"
            className="text-sm font-medium text-zinc-600 hover:text-zinc-900"
          >
            ← Volver a productos
          </Link>

          <h1 className="mt-4 text-3xl font-bold text-zinc-900">
            Registrar orden de salida
          </h1>

          <p className="mt-1 text-zinc-600">
            Registra consumo o merma de ingredientes.
          </p>
        </header>

        <section className="rounded-xl border bg-white p-6 shadow-sm">
          {loading ? (
            <p>Cargando ingredientes...</p>
          ) : (
            <form
              onSubmit={handleSubmit}
              className="space-y-5"
            >
              <div>
                <label
                  htmlFor="ingredient"
                  className="mb-2 block text-sm font-medium text-zinc-700"
                >
                  Ingrediente
                </label>

                <select
                  id="ingredient"
                  required
                  value={ingredientId}
                  onChange={(event) => {
                    setIngredientId(event.target.value);
                    setQuantity("");
                    setMessage("");
                    setError("");
                  }}
                  className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2"
                >
                  <option value="">
                    Selecciona un ingrediente
                  </option>

                  {ingredients.map((ingredient) => (
                    <option
                      key={ingredient.id}
                      value={ingredient.id}
                    >
                      {ingredient.name} · {ingredient.sku}
                    </option>
                  ))}
                </select>
              </div>

              {selectedIngredient && (
                <div className="rounded-lg border bg-zinc-50 p-4">
                  <p className="text-sm text-zinc-500">
                    Stock disponible actual
                  </p>

                  {stockLoading ? (
                    <p className="mt-1 font-semibold">
                      Consultando stock...
                    </p>
                  ) : (
                    <p className="mt-1 text-2xl font-bold text-zinc-900">
                      {availableStock}{" "}
                      {selectedIngredient.unit}
                    </p>
                  )}
                </div>
              )}

              <div>
                <label
                  htmlFor="quantity"
                  className="mb-2 block text-sm font-medium text-zinc-700"
                >
                  Cantidad
                </label>

                <input
                  id="quantity"
                  type="number"
                  min="0.01"
                  step="0.01"
                  required
                  value={quantity}
                  onChange={(event) =>
                    setQuantity(event.target.value)
                  }
                  className={`w-full rounded-lg border px-3 py-2 ${
                    exceedsStock
                      ? "border-red-400 bg-red-50"
                      : "border-zinc-300"
                  }`}
                  placeholder="Ej. 5"
                />

                {exceedsStock && (
                  <p
                    className="mt-2 text-sm font-medium text-red-700"
                    role="alert"
                  >
                    ⚠️ La cantidad supera el stock disponible (
                    {availableStock}{" "}
                    {selectedIngredient?.unit}).
                  </p>
                )}
              </div>

              <div>
                <label
                  htmlFor="reason"
                  className="mb-2 block text-sm font-medium text-zinc-700"
                >
                  Motivo
                </label>

                <select
                  id="reason"
                  value={reason}
                  onChange={(event) =>
                    setReason(
                      event.target.value as
                        | "consumption"
                        | "waste"
                    )
                  }
                  className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2"
                >
                  <option value="consumption">
                    Consumo
                  </option>
                  <option value="waste">
                    Merma
                  </option>
                </select>
              </div>

              <div>
                <label
                  htmlFor="location"
                  className="mb-2 block text-sm font-medium text-zinc-700"
                >
                  Local
                </label>

                <select
                  id="location"
                  value={locationId}
                  onChange={(event) =>
                    setLocationId(event.target.value)
                  }
                  className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2"
                >
                  {Array.from(
                    { length: 14 },
                    (_, index) => (
                      <option
                        key={index + 1}
                        value={index + 1}
                      >
                        Local {index + 1}
                      </option>
                    )
                  )}
                </select>
              </div>

              {error && (
                <div
                  role="alert"
                  className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700"
                >
                  {error}
                </div>
              )}

              {message && (
                <div
                  role="status"
                  className="rounded-lg border border-green-200 bg-green-50 p-4 text-sm text-green-700"
                >
                  {message}
                </div>
              )}

              <button
                type="submit"
                disabled={
                  submitting ||
                  stockLoading ||
                  exceedsStock
                }
                className="w-full rounded-lg bg-black px-4 py-3 font-medium text-white hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {submitting
                  ? "Registrando..."
                  : "Registrar salida"}
              </button>
            </form>
          )}
        </section>
      </div>
    </main>
  );
}

export default function OutboundPage() {
  return (
    <Suspense
      fallback={
        <main className="min-h-screen bg-zinc-100 p-6">
          <div className="mx-auto max-w-3xl">
            <section className="rounded-xl border bg-white p-6 shadow-sm">
              <p>Cargando formulario...</p>
            </section>
          </div>
        </main>
      }
    >
      <OutboundPageContent />
    </Suspense>
  );
}
