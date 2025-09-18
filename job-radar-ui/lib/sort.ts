// lib/sort.ts
export const ALLOWED_ORDERS = [
  'id_desc',
  'id_asc',
  'posted_at_desc',
  'posted_at_asc'
] as const;

export type Order = (typeof ALLOWED_ORDERS)[number];

export const ALLOWED_ORDERS_SET = new Set<Order>(ALLOWED_ORDERS);
