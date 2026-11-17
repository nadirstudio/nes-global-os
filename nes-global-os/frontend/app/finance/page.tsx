"use client";
import { useState } from "react";
import Shell, { can, useMe } from "@/components/Shell";
import { Badge, Card, Empty, Err, FormModal, Stat, useAction, useLoad } from "@/components/ui";
import { HBars } from "@/components/charts";
import { api, fmt } from "@/lib/api";

function Finance() {
  const me = useMe();
  const sum = useLoad<any>("/finance/summary");
  const entries = useLoad<any[]>("/finance/entries");
  const invoices = useLoad<any[]>("/finance/invoices");
  const companies = useLoad<any[]>("/companies");
  const customers = useLoad<any[]>("/crm/customers");
  const projects = useLoad<any[]>("/projects");
  const [add, setAdd] = useState<string | null>(null);
  const [inv, setInv] = useState(false);
  const [pay, setPay] = useState<any>(null);
  const act = useAction();
  const cname = (id: string) => companies.data?.find((c) => c.id === id)?.name || "—";
  const s = sum.data;
  const tot = (s?.by_company || []).reduce((a: any, b: any) => ({ revenue: a.revenue + b.revenue, expense: a.expense + b.expense }), { revenue: 0, expense: 0 });
  const outstanding = (invoices.data || []).filter((i) => ["issued", "partial"].includes(i.status)).reduce((a, i) => a + (i.currency === "PKR" ? i.amount - i.paid_amount : 0), 0);
  return (
    <div className="stack" style={{ gap: 14 }}>
      <div className="note">Records and analysis only. NES GLOBAL OS never moves money: receipts record payments already received, and AI agents can only prepare reports.</div>
      <div className="grid g4">
        <Stat label="Revenue (month)" value={fmt.pkr(tot.revenue)} />
        <Stat label="Expenses (month)" value={fmt.pkr(tot.expense)} />
        <Stat label="Net (month)" value={fmt.pkr(tot.revenue - tot.expense)} state={tot.revenue - tot.expense < 0 ? "crit" : tot.revenue ? "ok" : undefined} />
        <Stat label="Receivables" value={fmt.pkr(outstanding)} detail={`${(invoices.data || []).filter((i) => ["issued", "partial"].includes(i.status) && i.due_on && new Date(i.due_on) < new Date()).length} overdue invoices`} />
      </div>
      {can(me, "finance.manage") && (
        <div className="row">
          <button className="btn primary" onClick={() => setAdd("revenue")}>+ Revenue</button>
          <button className="btn" onClick={() => setAdd("expense")}>+ Expense</button>
          <button className="btn" onClick={() => setInv(true)}>+ Invoice</button>
        </div>
      )}
      <Err msg={sum.error || act.err} />
      <div className="grid g2">
        <Card title="Profitability by company (month)">
          <HBars rows={(s?.by_company || []).map((c: any) => ({ label: `${c.company} · net ${fmt.pkr(c.net)}`, values: [{ v: c.revenue, tone: "ok", name: "revenue" }, { v: c.expense, tone: "crit", name: "expense" }] }))} format={fmt.pkr} />
        </Card>
        <Card title="Top services by revenue (month)">
          {s?.top_services?.length ? <HBars rows={s.top_services.map((x: any) => ({ label: x.service, values: [{ v: x.revenue, tone: "info", name: "revenue" }] }))} format={fmt.pkr} />
            : <Empty>Record revenue with a service name to see which services earn most.</Empty>}
        </Card>
      </div>
      <div className="grid g2">
        <Card title="Invoices">
          {invoices.data?.length ? (
            <div className="scroll"><table className="tbl"><thead><tr><th>No.</th><th>Company</th><th>Amount</th><th>Paid</th><th>Due</th><th>Status</th><th /></tr></thead><tbody>
              {invoices.data.map((i) => (
                <tr key={i.id}><td className="mono small">{i.number}</td><td className="small">{cname(i.company_id)}</td><td className="mono">{i.currency} {fmt.num(i.amount)}</td>
                  <td className="mono">{fmt.num(i.paid_amount)}</td><td className="small">{fmt.date(i.due_on)}</td><td><Badge s={i.status} /></td>
                  <td>{can(me, "finance.manage") && ["issued", "partial"].includes(i.status) && <button className="btn sm" onClick={() => setPay(i)}>Receipt</button>}</td></tr>
              ))}</tbody></table></div>
          ) : <Empty>No invoices.</Empty>}
        </Card>
        <Card title="Ledger entries">
          {entries.data?.length ? (
            <div className="scroll"><table className="tbl"><thead><tr><th>Date</th><th>Company</th><th>Type</th><th>Amount</th><th>Detail</th></tr></thead><tbody>
              {entries.data.map((e) => (
                <tr key={e.id}><td className="small mono">{e.occurred_on}</td><td className="small">{cname(e.company_id)}</td><td><Badge s={e.kind === "revenue" ? "good" : "warning"} label={e.kind} /></td>
                  <td className="mono">{e.currency} {fmt.num(e.amount)}{e.currency !== "PKR" && <div className="faint small">@ {e.fx_to_pkr}</div>}</td><td className="small">{e.service || e.category || ""} {e.description ? `· ${e.description}` : ""}</td></tr>
              ))}</tbody></table></div>
          ) : <Empty>No entries yet.</Empty>}
        </Card>
      </div>
      {add && (
        <FormModal title={`Record ${add}`} onClose={() => setAdd(null)} initial={{ currency: "PKR", fx_to_pkr: 1, occurred_on: new Date().toISOString().slice(0, 10) }}
          fields={[
            { name: "company_id", label: "Company", type: "select", required: true, options: (companies.data || []).map((c) => ({ value: c.id, label: c.name })) },
            { name: "amount", label: "Amount", type: "number", required: true },
            { name: "currency", label: "Currency", type: "select", options: ["PKR", "USD", "GBP", "EUR", "AED", "SAR", "CAD", "AUD"].map((c) => ({ value: c, label: c })) },
            { name: "fx_to_pkr", label: "Rate to PKR", type: "number", help: "1 for PKR; otherwise the rate you actually used" },
            { name: "occurred_on", label: "Date", type: "date", required: true },
            ...(add === "revenue" ? [{ name: "service", label: "Service" }] : [{ name: "category", label: "Category", placeholder: "rent, salaries, ads…" }]),
            { name: "project_id", label: "Project", type: "select" as const, options: (projects.data || []).map((p) => ({ value: p.id, label: p.name })) },
            { name: "reference", label: "Reference / receipt no." }, { name: "description", label: "Description", type: "textarea" as const },
          ]}
          onSubmit={async (v) => { await api("/finance/entries", { body: { ...v, kind: add, currency: v.currency || "PKR", fx_to_pkr: v.fx_to_pkr || 1 } }); sum.reload(); entries.reload(); }} />
      )}
      {inv && (
        <FormModal title="New invoice" onClose={() => setInv(false)} initial={{ currency: "PKR" }}
          fields={[
            { name: "company_id", label: "Company (bills as)", type: "select", required: true, options: (companies.data || []).map((c) => ({ value: c.id, label: c.name })) },
            { name: "customer_id", label: "Customer", type: "select", options: (customers.data || []).map((c) => ({ value: c.id, label: c.name })) },
            { name: "amount", label: "Amount", type: "number", required: true },
            { name: "currency", label: "Currency", type: "select", options: ["PKR", "USD", "GBP", "EUR", "AED"].map((c) => ({ value: c, label: c })) },
            { name: "issued_on", label: "Issued", type: "date" }, { name: "due_on", label: "Due", type: "date" },
            { name: "project_id", label: "Project", type: "select", options: (projects.data || []).map((p) => ({ value: p.id, label: p.name })) },
            { name: "description", label: "Description", type: "textarea" },
          ]}
          onSubmit={async (v) => { await api("/finance/invoices", { body: { ...v, currency: v.currency || "PKR" } }); invoices.reload(); }} />
      )}
      {pay && (
        <FormModal title={`Record receipt — ${pay.number}`} onClose={() => setPay(null)} initial={{ amount: pay.amount - pay.paid_amount, fx_to_pkr: 1 }}
          fields={[{ name: "amount", label: `Amount received (${pay.currency})`, type: "number", required: true }, { name: "received_on", label: "Received on", type: "date" },
            ...(pay.currency !== "PKR" ? [{ name: "fx_to_pkr", label: "Rate to PKR", type: "number" as const, required: true }] : []), { name: "reference", label: "Reference" }]}
          onSubmit={async (v) => { await api(`/finance/invoices/${pay.id}/payment`, { body: { ...v, fx_to_pkr: v.fx_to_pkr || 1 } }); invoices.reload(); sum.reload(); entries.reload(); }} />
      )}
    </div>
  );
}

export default function Page() {
  return <Shell title="Finance" sub="Company-wise revenue, expenses, invoices, receipts and profitability · PKR default, multi-currency"><Finance /></Shell>;
}
