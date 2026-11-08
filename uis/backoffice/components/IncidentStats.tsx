type Props = {
  byCategory: Record<string, number>;
  byStatus: Record<string, number>;
};

export default function IncidentStats({
  byCategory,
  byStatus,
}: Props) {
  const categoryLabels: Record<string, string> = {
    CUSTOMER_COMPLAINT: "Quejas de clientes",
    FOOD_QUALITY: "Calidad de alimentos",
    EQUIPMENT: "Equipamiento",
    SUPPLY: "Suministros",
    STAFF: "Personal",
  };

  const statusLabels: Record<string, string> = {
    OPEN: "Abiertos",
    CLOSED: "Cerrados",
    DISCARDED: "Descartados",
  };

  return (
    <section className="mt-8 grid gap-6 lg:grid-cols-2">
      <div className="rounded-xl border bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-zinc-900">
          Incidentes por categoría
        </h2>
        <div className="mt-4 space-y-3">
          {Object.entries(byCategory).map(([key, count]) => (
            <div key={key} className="flex justify-between border-b pb-2">
              <span className="text-sm text-zinc-600">
                {categoryLabels[key] ?? key}
              </span>
              <span className="font-semibold">{count}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-xl border bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-zinc-900">
          Incidentes por estado
        </h2>
        <div className="mt-4 space-y-3">
          {Object.entries(byStatus).map(([key, count]) => (
            <div key={key} className="flex justify-between border-b pb-2">
              <span className="text-sm text-zinc-600">
                {statusLabels[key] ?? key}
              </span>
              <span className="font-semibold">{count}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
