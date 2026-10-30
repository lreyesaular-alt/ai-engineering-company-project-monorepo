
"use client";

import {
  FormEvent,
  Suspense,
  useEffect,
  useState,
} from "react";
import Link from "next/link";
import {
  useRouter,
  useSearchParams,
} from "next/navigation";
import {
  createInboundOrder,
  getIngredients,
  getUserUuid,
  Ingredient,
} from "../../../../../lib/inventory";
import { getToken } from "../../../../../lib/auth";

function InboundPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [ingredients, setIngredients] = useState<Ingredient[]>([]);
  const [ingredientId, setIngredientId] = useState("");
  const [quantity, setQuantity] = useState("");
  const [supplierName, setSupplierName] = useState("");
  const [locationId, setLocationId] = useState("1");
  const [loading, setLoading] = useState(true);
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
            (ingredient) =>
              String(ingredient.id) === selected
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

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();

    setError("");
    setMessage("");

    const amount = Number(quantity);

    if (!ingredientId || !amount || amount <= 0) {
      setError(
        "Selecciona un ingrediente e introduce una cantidad válida."
      );
      return;
    }

    if (!supplierName.trim()) {
      setError("Introduce el nombre del proveedor.");
      return;
    }

    try {
      setSubmitting(true);

      await createInboundOrder({
        ingredient_id: Number(ingredientId),
        quantity: amount,
        supplier_name: supplierName.trim(),
        location_id: Number(locationId),
        user_uuid: getUserUuid(),
      });

      setQuantity("");
      setSupplierName("");
      setMessage("Entrega registrada correctamente.");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "No se pudo registrar la entrada."
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
            Registrar orden de entrada
          </h1>

          <p className="mt-1 text-zinc-600">
            Registra una entrega recibida de un proveedor.
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
                  onChange={(event) =>
                    setIngredientId(event.target.value)
                  }
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

              <div>
                <label
                  htmlFor="quantity"
                  className="mb-2 block text-sm font-medium text-zinc-700"
                >
                  Cantidad recibida
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
                  className="w-full rounded-lg border border-zinc-300 px-3 py-2"
                  placeholder="Ej. 50"
                />
              </div>

              <div>
                <label
                  htmlFor="supplier"
                  className="mb-2 block text-sm font-medium text-zinc-700"
                >
                  Proveedor
                </label>

                <input
                  id="supplier"
                  type="text"
                  required
                  value={supplierName}
                  onChange={(event) =>
                    setSupplierName(event.target.value)
                  }
                  className="w-full rounded-lg border border-zinc-300 px-3 py-2"
                  placeholder="Ej. Carnes del Valle S.A."
                />
              </div>

              <div>
                <label
                  htmlFor="location"
                  className="mb-2 block text-sm font-medium text-zinc-700"
                >
                  Local receptor
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
                disabled={submitting}
                className="w-full rounded-lg bg-black px-4 py-3 font-medium text-white hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {submitting
                  ? "Registrando..."
                  : "Registrar entrada"}
              </button>
            </form>
          )}
        </section>
      </div>
    </main>
  );
}

export default function InboundPage() {
  return (
    <Suspense
      fallback={
        <main className="min-h-screen bg-zinc-100 p-6">
          <div className="mx-auto max-w-3xl rounded-xl border bg-white p-8 text-center shadow-sm">
            <p className="text-zinc-600">
              Cargando...
            </p>
          </div>
        </main>
      }
    >
      <InboundPageContent />
    </Suspense>
  );
}
