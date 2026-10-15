import React, { useEffect, useState } from "react";
import { brokerOrderRecords } from "./brokerOrderSheet";

const GRID_STATUSES = ["未挂", "已挂", "已成", "作废"];
const BASE_STATUSES = ["待买入", "已成", "作废"];

function statusChoices(order) {
  if (order?.status === "待买入" || String(order?.note || "").startsWith("底仓")) {
    return BASE_STATUSES;
  }
  return GRID_STATUSES;
}

export default function OrderLedgerCard({
  etfCode,
  etfName,
  anchorPrice,
  currentPrice,
  basePosition,
  orders,
}) {
  const [plan, setPlan] = useState(null);
  const [message, setMessage] = useState("");
  const [staleOrders, setStaleOrders] = useState([]);

  const load = async (price) => {
    if (!etfCode) return;
    const query = price ? `?price=${encodeURIComponent(price)}` : "";
    const res = await fetch(`/api/ledger/${etfCode}${query}`);
    const json = await res.json();
    if (json.success) setPlan(json.data);
  };

  useEffect(() => {
    load(currentPrice).catch(() => setMessage("账本暂时读不出来"));
  }, [etfCode, currentPrice]);

  const save = async (postedPolicy) => {
    if (!etfCode) return;
    setMessage("");
    const res = await fetch("/api/ledger", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        etfCode,
        etfName: etfName || "",
        anchorPrice,
        currentPrice,
        postedPolicy: postedPolicy || undefined,
        base: {
          shares: basePosition?.shares || 0,
          price: basePosition?.current_price || anchorPrice,
        },
        orders: brokerOrderRecords({ orders, basePosition, anchorPrice }),
      }),
    });
    const json = await res.json();
    if (res.status === 409 && json.needs_choice) {
      setStaleOrders(json.stale_orders || []);
      setMessage(json.error || "请选择如何处理旧的已挂单");
      return;
    }
    if (!json.success) {
      setMessage(json.error || "保存失败");
      return;
    }
    setStaleOrders([]);
    setPlan(json.data);
    setMessage("已写入本机账本");
  };

  const mark = async (orderId, status) => {
    const res = await fetch(`/api/ledger/orders/${orderId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status, etfCode, currentPrice }),
    });
    const json = await res.json();
    if (json.success && json.data) setPlan(json.data);
  };

  const rows = plan?.orders || [];
  return (
    <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50/70 p-4 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h5 className="text-sm font-bold text-slate-800">本地挂单账本</h5>
          <p className="text-[11px] text-slate-500">
            保存在本机数据库。状态可标成未挂、已挂、已成、作废。留利润不会自动执行。
          </p>
        </div>
        <button
          type="button"
          onClick={save}
          className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-900 text-white"
        >
          保存当前挂单
        </button>
      </div>
      {message && <p className="text-xs text-slate-600">{message}</p>}
      {staleOrders.length > 0 && (
        <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 space-y-2">
          <p className="text-xs text-amber-900">
            有 {staleOrders.length} 笔已挂单不在新网格里
            （{staleOrders.map((order) => `${order.side} ${Number(order.trigger_price).toFixed(3)}`).join("，")}）。
          </p>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => save("void")}
              className="px-2.5 py-1 rounded-lg text-xs font-semibold bg-amber-800 text-white"
            >
              旧的已挂单一并作废
            </button>
            <button
              type="button"
              onClick={() => save("keep")}
              className="px-2.5 py-1 rounded-lg text-xs font-semibold border border-amber-400 bg-white text-amber-900"
            >
              只保留新表里还有的档
            </button>
          </div>
        </div>
      )}
      {rows.length === 0 ? (
        <p className="text-xs text-slate-400">还没有保存。保存后会按现价标出今天可能成交的未完成单。</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="text-slate-500">
              <tr>
                <th className="text-left py-1">方向</th>
                <th className="text-right">触发价</th>
                <th className="text-right">股数</th>
                <th className="text-left">备注</th>
                <th className="text-left">状态</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((order) => (
                <tr key={order.id} className="border-t border-slate-200">
                  <td className="py-1.5">{order.side}</td>
                  <td className="text-right font-mono">{Number(order.trigger_price).toFixed(3)}</td>
                  <td className="text-right font-mono">{order.shares}</td>
                  <td className="text-slate-600">
                    {order.note}
                    {order.may_fill_today ? (
                      <span className="ml-1 text-amber-700 font-semibold">今天可能成交</span>
                    ) : null}
                  </td>
                  <td>
                    <select
                      value={order.status}
                      onChange={(event) => mark(order.id, event.target.value)}
                      className="bg-white border border-slate-200 rounded px-1 py-0.5"
                    >
                      {statusChoices(order).map((status) => (
                        <option key={status} value={status}>{status}</option>
                      ))}
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
