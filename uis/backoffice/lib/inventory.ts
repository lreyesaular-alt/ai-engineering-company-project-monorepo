import { api } from "./api";

export type Ingredient = {
  id: number;
  name: string;
  sku: string;
  unit: string;
  category: string;
  country: string;
  current_stock: number;
};

export type InboundOrder = {
  id: number;
  ingredient_id: number;
  quantity: number;
  supplier_name: string;
  location_id: number;
  created_at: string;
  user_uuid: string;
};

export type OutboundOrder = {
  id: number;
  ingredient_id: number;
  quantity: number;
  reason: "consumption" | "waste";
  location_id: number;
  created_at: string;
  user_uuid: string;
};

export type InventoryOrder = {
  id: number;
  ingredient_id: number;
  ingredient_name: string;
  type: "inbound" | "outbound";
  quantity: number;
  supplier_name: string | null;
  reason: string | null;
  location_id: number;
  created_at: string;
  user_uuid: string;
};

export async function getIngredients(): Promise<Ingredient[]> {
  const response = await api("/inventory/products");
  const data = await response.json();

  if (!Array.isArray(data)) {
    throw new Error("La API no devolvió una lista de ingredientes.");
  }

  return data;
}

export async function getIngredient(
  id: number
): Promise<Ingredient> {
  const response = await api(`/inventory/products/${id}`);
  const data = await response.json();

  if (!data || typeof data !== "object") {
    throw new Error("La API devolvió datos inválidos.");
  }

  return data;
}

export async function createInboundOrder(data: {
  ingredient_id: number;
  quantity: number;
  supplier_name: string;
  location_id: number;
  user_uuid: string;
}): Promise<InboundOrder> {
  const response = await api("/inventory/orders/inbound", {
    method: "POST",
    body: JSON.stringify(data),
  });

  return response.json();
}

export async function createOutboundOrder(data: {
  ingredient_id: number;
  quantity: number;
  reason: "consumption" | "waste";
  location_id: number;
  user_uuid: string;
}): Promise<OutboundOrder> {
  const response = await api("/inventory/orders/outbound", {
    method: "POST",
    body: JSON.stringify(data),
  });

  return response.json();
}

export async function getInventoryOrders(): Promise<
  InventoryOrder[]
> {
  const response = await api("/inventory/orders");
  const data = await response.json();

  if (!Array.isArray(data)) {
    throw new Error("La API no devolvió una lista de órdenes.");
  }

  return data;
}

export function getUserUuid(): string {
  if (typeof window === "undefined") {
    return "";
  }

  const token = localStorage.getItem("access_token");

  if (!token) {
    return "";
  }

  try {
    const payload = token.split(".")[1];

    if (!payload) {
      return "";
    }

    const normalized = payload
      .replace(/-/g, "+")
      .replace(/_/g, "/");

    const decoded = JSON.parse(
      atob(normalized.padEnd(normalized.length + (4 - normalized.length % 4) % 4, "="))
    );

    return String(decoded.sub ?? "");
  } catch {
    return "";
  }
}
