export function visibleLedgerOrders(orders, showHistory) {
  const rows = orders || [];
  if (showHistory) return rows;
  return rows.filter((order) => order.status !== "作废");
}

export function voidedLedgerCount(orders) {
  return (orders || []).filter((order) => order.status === "作废").length;
}
