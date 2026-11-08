type Props = {
  status: string;
  updating: boolean;
  onUpdate: (status: string) => void;
};

export default function IncidentStatusControls({
  status,
  updating,
  onUpdate,
}: Props) {
  const labels: Record<string, string> = {
    OPEN: "Abierto",
    CLOSED: "Cerrado",
    DISCARDED: "Descartado",
  };

  return (
    <div className="mt-6 border-t pt-6">
      <p className="mb-3 text-sm font-medium text-zinc-700">
        Cambiar estado
      </p>

      <div className="flex flex-wrap gap-3">
        {["OPEN", "CLOSED", "DISCARDED"].map((newStatus) => (
          <button
            key={newStatus}
            type="button"
            onClick={() => onUpdate(newStatus)}
            disabled={updating || status === newStatus}
            className="rounded-lg border border-zinc-300 bg-white px-4 py-2 text-sm font-medium text-zinc-800 hover:bg-zinc-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {updating && status !== newStatus
              ? "Actualizando..."
              : labels[newStatus]}
          </button>
        ))}
      </div>
    </div>
  );
}
