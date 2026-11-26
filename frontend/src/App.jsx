import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity, ArrowDownRight, ArrowRight, Boxes, Check, ChevronDown, CircleHelp,
  Clock3, Download, FileUp, Filter, Gauge, GitBranch, Layers3, LoaderCircle,
  LockKeyhole, Menu, Play, Plus, RefreshCw, Search, ShieldAlert, SlidersHorizontal,
  Sparkles, UploadCloud, Workflow, X,
} from "lucide-react";
import { tv } from "tailwind-variants";

const API = (import.meta.env.VITE_API_URL || import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1").replace(/\/$/, "");
const API_KEY = import.meta.env.VITE_API_KEY || "";
const NAV = [
  { id: "control", label: "Control Tower", icon: Gauge },
  { id: "risk", label: "Risk & AI Actions", icon: Sparkles },
  { id: "process", label: "Process Mining & Sim", icon: GitBranch },
  { id: "workflow", label: "Workflow Designer", icon: Workflow },
  { id: "exceptions", label: "Exceptions", icon: ShieldAlert },
  { id: "procurement", label: "Procurement", icon: Layers3 },
  { id: "inventory", label: "Inventory & Invoices", icon: Boxes },
  { id: "rules", label: "Rules Engine", icon: SlidersHorizontal },
  { id: "imports", label: "Data Import", icon: FileUp },
];
const money = (value) =>
  new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(value || 0);
const dateLabel = (value) => value ? new Date(value).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" }) : "—";

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (API_KEY) headers.set("X-API-Key", API_KEY);
  const response = await fetch(`${API}${path}`, { ...options, headers });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try { message = (await response.json()).detail || message; } catch { /* no JSON body */ }
    throw new Error(message);
  }
  return response.json();
}

function App() {
  const [organizations, setOrganizations] = useState([]);
  const [orgId, setOrgId] = useState("");
  const [locations, setLocations] = useState([]);
  const [locationId, setLocationId] = useState("");
  const [view, setView] = useState("control");
  const [data, setData] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [mobileNav, setMobileNav] = useState(false);
  const org = organizations.find((item) => item.id === orgId);
  const manufacturing = org?.industry_type === "MANUFACTURING";
  const labels = manufacturing
    ? { items: "Parts", locations: "Plants", vendor: "Supplier", order: "Purchase order" }
    : { items: "SKUs", locations: "Distribution hubs", vendor: "Supplier", order: "Purchase order" };
  const locationQuery = locationId ? `?location_id=${encodeURIComponent(locationId)}` : "";

  const load = useCallback(async () => {
    if (!orgId) return;
    setLoading(true);
    setError("");
    try {
      const [context, kpis, intelligence, process, exceptions, pos, stockInvoices, rules, workflows, imports] =
        await Promise.all([
          api(`/tenant-context/${orgId}`),
          api(`/control-tower/${orgId}${locationQuery}`),
          api(`/intelligence/${orgId}${locationQuery}`),
          api(`/process-mining/${orgId}`),
          api(`/exceptions/${orgId}/list`),
          api(`/procurement/${orgId}${locationQuery}`),
          api(`/inventory-invoices/${orgId}${locationQuery}`),
          api(`/rules/${orgId}`),
          api(`/workflows/${orgId}`),
          api(`/imports/${orgId}`),
        ]);
      setLocations(context.locations || []);
      setData({ kpis, intelligence, process, exceptions, pos, ...stockInvoices, rules, workflows, imports });
    } catch (err) {
      setError(err.message || "Unable to connect to the operations API.");
    } finally {
      setLoading(false);
    }
  }, [orgId, locationQuery]);

  useEffect(() => {
    api("/bootstrap")
      .then((bootstrap) => {
        const tenants = bootstrap.organizations || [];
        setOrganizations(tenants);
        setOrgId((current) => current || tenants[0]?.id || "");
      })
      .catch((err) => setError(`Backend unavailable: ${err.message}`))
      .finally(() => setLoading(false));
  }, []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!toast) return undefined;
    const timeout = setTimeout(() => setToast(""), 3500);
    return () => clearTimeout(timeout);
  }, [toast]);

  const flash = (message) => setToast(message);
  const patch = async (path, payload, method = "PATCH") => {
    try {
      await api(path, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      flash("Changes saved successfully");
      await load();
    } catch (err) { setError(err.message); }
  };
  const activeNav = NAV.find((item) => item.id === view);

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileNav ? "sidebar-open" : ""}`}>
        <div className="brand">
          <div className="brand-mark"><Activity size={19} strokeWidth={2.4} /></div>
          <div><strong>northstar</strong><span>OPERATIONS INTELLIGENCE</span></div>
          <button className="icon-button sidebar-close" onClick={() => setMobileNav(false)} aria-label="Close menu"><X size={18} /></button>
        </div>
        <div className="workspace-label">WORKSPACE</div>
        <nav className="side-nav">
          {NAV.map(({ id, label, icon: Icon }, index) => (
            <button key={id} className={`nav-item ${view === id ? "active" : ""}`} onClick={() => { setView(id); setMobileNav(false); }}>
              <Icon size={17} strokeWidth={1.8} /><span>{label}</span>
              {id === "exceptions" && data.exceptions?.filter((exc) => exc.status === "OPEN").length > 0 &&
                <span className="nav-count">{data.exceptions.filter((exc) => exc.status === "OPEN").length}</span>}
              {index === 0 && <span className="nav-shortcut">⌘1</span>}
            </button>
          ))}
        </nav>
        <div className="sidebar-spacer" />
        <div className="sidebar-footer">
          <div className="online-dot" /> <span>All systems operational</span>
          <button className="icon-button help-button" title="Help"><CircleHelp size={16} /></button>
        </div>
        <div className="user-card">
          <div className="avatar">AN</div><div className="user-meta"><strong>Aditya Nair</strong><span>Enterprise Admin</span></div>
          <ChevronDown size={15} className="muted-icon" />
        </div>
      </aside>

      {mobileNav && <button className="mobile-scrim" onClick={() => setMobileNav(false)} aria-label="Close navigation" />}
      <main className="main-area">
        <header className="context-bar">
          <div className="context-left">
            <button className="icon-button mobile-menu" onClick={() => setMobileNav(true)} aria-label="Open navigation"><Menu size={20} /></button>
            <span className="breadcrumb">Operations <span>/</span> <b>{activeNav?.label}</b></span>
          </div>
          <div className="context-controls">
            <label className="select-control org-select">
              <span className="select-icon">ORG</span>
              <select value={orgId} onChange={(event) => { setOrgId(event.target.value); setLocationId(""); }}>
                {!organizations.length && <option value="">Loading tenants…</option>}
                {organizations.map((tenant) => <option key={tenant.id} value={tenant.id}>{tenant.name}</option>)}
              </select><ChevronDown size={14} />
            </label>
            <div className="profile-switch" title="Industry profile follows the selected tenant">
              <span className={!manufacturing ? "profile-active" : ""}>FMCG</span><span className={manufacturing ? "profile-active" : ""}>MFG</span>
            </div>
            <label className="select-control location-select">
              <span className="location-dot" />
              <select value={locationId} onChange={(event) => setLocationId(event.target.value)}>
                <option value="">All {labels.locations}</option>
                {locations.map((location) => <option key={location.id} value={location.id}>{location.name}</option>)}
              </select><ChevronDown size={14} />
            </label>
            <button className="icon-button refresh-button" onClick={load} title="Refresh data"><RefreshCw size={16} /></button>
          </div>
        </header>
        <div className="page-wrap">
          <div className="page-heading">
            <div><div className="eyebrow">{org?.industry_type || "ENTERPRISE"} · LIVE OPERATIONS</div><h1>{activeNav?.label}</h1>
              <p>{pageDescription(view, org?.name, labels)}</p></div>
            <div className="heading-actions"><span className="live-pill"><i /> LIVE DATA</span><button className="date-button"><Clock3 size={14} /> Last 30 days <ChevronDown size={13} /></button></div>
          </div>
          {error && <div className="error-banner"><ShieldAlert size={17} /><span>{error}</span><button onClick={() => setError("")}><X size={16} /></button></div>}
          {loading && !data.kpis ? <div className="loading-state"><LoaderCircle className="spin" size={26} /> Connecting to operations workspace…</div> :
            <ViewContent view={view} data={data} labels={labels} locationId={locationId} orgId={orgId} patch={patch} flash={flash} load={load} />}
          <footer className="page-footer"><span>Northstar Operations Intelligence <span className="footer-dot">·</span> Secure tenant workspace</span><span>Data refreshes on demand <span className="footer-dot">·</span> INR</span></footer>
        </div>
      </main>
      {toast && <div className="toast"><Check size={16} />{toast}</div>}
    </div>
  );
}

function pageDescription(view, orgName, labels) {
  const descriptions = {
    control: `A real-time view of operational health, exposure and supplier performance${orgName ? ` for ${orgName}` : ""}.`,
    risk: `Prioritised risk signals and practical actions across ${labels.vendor.toLowerCase()}s and ${labels.items.toLowerCase()}.`,
    process: "Understand process variants, surface rework loops and test operational improvements.",
    workflow: "Turn operational signals into consistent, governed actions.",
    exceptions: "Review, assign and resolve operational exceptions with a clear audit trail.",
    procurement: "Monitor spend, supplier delivery performance and approval cycle times.",
    inventory: "Inspect stock health alongside invoice-to-purchase-order variances.",
    rules: "Maintain the thresholds that detect operational risk across your tenant.",
    imports: "Bring operational records into a governed, auditable data pipeline.",
  };
  return descriptions[view];
}

function ViewContent({ view, data, labels, locationId, orgId, patch, flash, load }) {
  switch (view) {
    case "control": return <ControlTower data={data} labels={labels} />;
    case "risk": return <RiskView intelligence={data.intelligence} labels={labels} />;
    case "process": return <ProcessView process={data.process} orgId={orgId} />;
    case "workflow": return <WorkflowView workflows={data.workflows} orgId={orgId} patch={patch} />;
    case "exceptions": return <ExceptionsView exceptions={data.exceptions} orgId={orgId} patch={patch} flash={flash} />;
    case "procurement": return <ProcurementView pos={data.pos} labels={labels} />;
    case "inventory": return <InventoryView inventory={data.inventory} invoices={data.invoices} labels={labels} />;
    case "rules": return <RulesView rules={data.rules} orgId={orgId} patch={patch} load={load} />;
    case "imports": return <ImportView imports={data.imports} orgId={orgId} flash={flash} load={load} locationId={locationId} />;
    default: return null;
  }
}

function ControlTower({ data, labels }) {
  const kpis = data.kpis || {};
  const open = (data.exceptions || []).filter((exc) => exc.status === "OPEN").sort((a, b) => impactRank(b.severity) - impactRank(a.severity));
  const vendors = Object.entries(kpis.vendor_reliability_scorecards || {});
  return <>
    <div className="kpi-grid">
      <KpiCard label="FINANCIAL EXPOSURE" value={money(kpis.total_financial_exposure)} change="Open exception impact" icon={ShieldAlert} tone="red" />
      <KpiCard label={`${labels.order.toUpperCase()} SPEND`} value={money(kpis.po_spend)} change={`${(data.pos || []).length} active records`} icon={Layers3} tone="blue" />
      <KpiCard label="SUPPLIER OTIF" value={kpis.otif_percent == null ? "—" : `${kpis.otif_percent}%`} change="On-time, in-full delivery" icon={Activity} tone="green" />
      <KpiCard label="INVENTORY CAPITAL" value={money(kpis.inventory_capital)} change={`${kpis.stockout_alerts || 0} stockout alerts`} icon={Boxes} tone="amber" />
    </div>
    <div className="content-grid content-grid-main">
      <section className="panel exceptions-panel">
        <PanelHeader title="Priority exceptions" eyebrow="NEEDS ATTENTION" trailing={<span className="count-badge">{open.length} OPEN</span>} />
        {open.length ? <div className="exception-feed">{open.slice(0, 5).map((exc) => <ExceptionRow key={exc.id} exception={exc} />)}</div> :
          <EmptyState icon={Check} title="Clear skies" text="No open exceptions require attention." />}
        <div className="panel-bottom"><span>3-way invoice leakage risk</span><b>{money(kpis.three_way_invoice_leakage_risk)}</b></div>
      </section>
      <section className="panel vendor-panel">
        <PanelHeader title="Supplier reliability" eyebrow="ON-TIME DELIVERY" trailing={<span className="subtle-label">{vendors.length} SUPPLIERS</span>} />
        {vendors.length ? <div className="vendor-bars">{vendors.map(([name, vendor]) => {
          const score = vendor.otif_percent ?? 0;
          return <div className="vendor-bar-row" key={name}><div className="vendor-name"><span>{name}</span><b>{vendor.otif_percent == null ? "No deliveries" : `${score}%`}</b></div><div className="bar-track"><div className={`bar-fill ${score >= 90 ? "bar-green" : score >= 70 ? "bar-amber" : "bar-red"}`} style={{ width: `${Math.max(score, 2)}%` }} /></div><small>{vendor.purchase_orders} orders <span>·</span> {vendor.avg_approval_days}d avg approval</small></div>;
        })}</div> : <EmptyState icon={Activity} title="No supplier data" text="Purchase orders will show supplier scorecards here." />}
        <div className="vendor-summary"><div><strong>{kpis.avg_approval_days ?? "—"}<small>days</small></strong><span>Avg. approval cycle</span></div><ArrowRight size={17} /><div><strong>{kpis.stockout_alerts || 0}</strong><span>Stockout alerts</span></div></div>
      </section>
    </div>
    <div className="bottom-insight"><div className="insight-icon"><Sparkles size={17} /></div><div><b>Operations pulse</b><span>Monitor supplier reliability and resolve high-impact exceptions to protect working capital.</span></div><span className="pulse-tag">AI INSIGHT</span></div>
  </>;
}

function KpiCard({ label, value, change, icon: Icon, tone }) {
  return <section className={kpiCardStyles({ tone })}><div className="kpi-top"><span>{label}</span><i className={kpiIconStyles({ tone })}><Icon size={16} /></i></div><strong className="kpi-value">{value}</strong><div className="kpi-foot"><span className={trendStyles({ tone })}><ArrowDownRight size={13} />{change}</span></div></section>;
}
const kpiCardStyles = tv({ base: "kpi-card", variants: { tone: { red: "kpi-card-risk", blue: "kpi-card-spend", green: "kpi-card-positive", amber: "kpi-card-warning" } } });
const kpiIconStyles = tv({ base: "kpi-icon", variants: { tone: { red: "red", blue: "blue", green: "green", amber: "amber" } } });
const trendStyles = tv({ base: "trend", variants: { tone: { red: "red", blue: "blue", green: "green", amber: "amber" } } });
function PanelHeader({ title, eyebrow, trailing }) {
  return <div className="panel-header"><div><span className="eyebrow">{eyebrow}</span><h2>{title}</h2></div>{trailing}</div>;
}
function ExceptionRow({ exception, action }) {
  return <div className="exception-row"><span className={`severity-dot ${exception.severity?.toLowerCase()}`} /><div className="exception-copy"><b>{exception.title}</b><span>{exception.description}</span></div><b className="exception-impact">{money(exception.financial_impact)}</b>{action}</div>;
}
function EmptyState({ icon: Icon, title, text }) {
  return <div className="empty-state"><Icon size={23} /><b>{title}</b><span>{text}</span></div>;
}
function SectionTitle({ title, detail, count }) {
  return <div className="table-title"><div><h2>{title}</h2><span>{detail}</span></div>{count != null && <span className="count-badge">{count} RECORDS</span>}</div>;
}
function DataTable({ columns, rows, empty, renderRow }) {
  if (!rows?.length) return <EmptyState icon={Search} title="Nothing to show yet" text={empty || "Records will appear here when available."} />;
  return <div className="table-scroll"><table><thead><tr>{columns.map((col) => <th key={col}>{col}</th>)}</tr></thead><tbody>{rows.map(renderRow)}</tbody></table></div>;
}

function RiskView({ intelligence = {}, labels }) {
  const [tab, setTab] = useState("vendors");
  const vendors = intelligence.vendors || [];
  const items = intelligence.items || [];
  return <section className="panel data-panel"><PanelHeader title="Risk scorecards" eyebrow="EXPLAINABLE PRIORITISATION" trailing={<span className="score-legend"><i /> 0 LOW <i /> 100 HIGH</span>} />
    <div className="tabs"><button className={tab === "vendors" ? "tab-active" : ""} onClick={() => setTab("vendors")}>{labels.vendor}s <span>{vendors.length}</span></button><button className={tab === "items" ? "tab-active" : ""} onClick={() => setTab("items")}>{labels.items} <span>{items.length}</span></button></div>
    {tab === "vendors" ? <DataTable columns={["SUPPLIER", "RISK SCORE", "ORDERS", "PRESCRIPTIVE ACTIONS"]} rows={vendors} empty="Supplier risks will appear as purchasing and invoice data accumulates." renderRow={(vendor) => <tr key={vendor.vendor}><td><b>{vendor.vendor}</b></td><td><RiskScore score={vendor.risk_score} /></td><td>{vendor.purchase_orders}</td><td><ActionList actions={vendor.prescriptive_actions} /></td></tr>} /> :
      <DataTable columns={[labels.items.toUpperCase(), "RISK SCORE", "LOCATION", "PRESCRIPTIVE ACTIONS"]} rows={items} renderRow={(item) => <tr key={`${item.item_code}-${item.location_id}`}><td><b>{item.item_code}</b><small className="table-sub">{item.item_description}</small></td><td><RiskScore score={item.risk_score} /></td><td>{item.location_id.slice(0, 8)}…</td><td><ActionList actions={item.prescriptive_actions} /></td></tr>} />}
  </section>;
}
function RiskScore({ score }) {
  const tone = score >= 70 ? "risk-high" : score >= 35 ? "risk-med" : "risk-low";
  return <div className="risk-score"><div className="risk-track"><div className={tone} style={{ width: `${score}%` }} /></div><b className={tone}>{score}</b></div>;
}
function ActionList({ actions = [] }) {
  return <ul className="action-list">{actions.map((action) => <li key={action}><ArrowRight size={12} />{action}</li>)}</ul>;
}

function ProcessView({ process = {}, orgId }) {
  const [approval, setApproval] = useState(3);
  const [sla, setSla] = useState(0);
  const [simulation, setSimulation] = useState(null);
  const [busy, setBusy] = useState(false);
  const run = async () => {
    setBusy(true);
    try { setSimulation(await api(`/simulate/${orgId}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ approval_target_days: Number(approval), delivery_sla_days: Number(sla) }) })); }
    catch (err) { setSimulation({ error: err.message }); }
    finally { setBusy(false); }
  };
  return <div className="content-grid process-grid">
    <section className="panel"><PanelHeader title="Discovered variants" eyebrow="PROCESS MINING" trailing={<span className="count-badge">{process.cases_analyzed || 0} CASES</span>} />
      {process.execution_variants?.length ? <div className="variant-list">{process.execution_variants.map((variant, index) => <div className="variant-row" key={variant.variant}><div className="variant-number">{String(index + 1).padStart(2, "0")}</div><div className="variant-content"><div className="variant-steps">{variant.variant.split(" -> ").map((step, stepIndex) => <span key={`${step}-${stepIndex}`} className={step.includes("REJECTED") || step.includes("RESUBMITTED") ? "rework-step" : ""}>{stepIndex > 0 && <ArrowRight size={12} />}{step}</span>)}</div><small>{variant.cases} {variant.cases === 1 ? "case" : "cases"}</small></div><span className={variant.variant.includes("REJECTED") ? "rework-flag" : "variant-flag"}>{variant.variant.includes("REJECTED") ? "REWORK LOOP" : "STANDARD"}</span></div>)}</div> : <EmptyState icon={GitBranch} title="No event traces yet" text="Process variants appear once case events have been imported." />}
      <div className="process-summary"><div><span>REWORK RATE</span><b className={process.rework_rate_percent ? "text-red" : ""}>{process.rework_rate_percent ?? 0}%</b></div><div><span>AVG. CYCLE TIME</span><b>{process.cycle_time_hours?.average ?? "—"} <small>hrs</small></b></div><div><span>CASES ANALYZED</span><b>{process.cases_analyzed || 0}</b></div></div>
    </section>
    <section className="panel simulator"><PanelHeader title="What-if simulator" eyebrow="ESTIMATE · NOT A COMMITMENT" trailing={<div className="estimate-icon"><Sparkles size={16} /></div>} />
      <p className="sim-intro">Explore how tighter operating targets may reduce exceptions and unlock capital.</p>
      <div className="slider-field"><div><label>Approval target</label><b>{approval} <small>days</small></b></div><input type="range" min="1" max="10" value={approval} onChange={(event) => setApproval(event.target.value)} /><div className="range-labels"><span>1 day</span><span>10 days</span></div></div>
      <div className="slider-field"><div><label>Delivery SLA tolerance</label><b>{sla} <small>days late</small></b></div><input type="range" min="0" max="14" value={sla} onChange={(event) => setSla(event.target.value)} /><div className="range-labels"><span>On time</span><span>14 days</span></div></div>
      <button className="primary-button full-button" onClick={run} disabled={busy}>{busy ? <LoaderCircle size={16} className="spin" /> : <Play size={15} fill="currentColor" />} Run estimate</button>
      {simulation && (simulation.error ? <div className="inline-error">{simulation.error}</div> : <div className="simulation-results"><span className="estimate-label">ESTIMATED OUTCOME</span><div><b>{simulation.estimated_exceptions_eliminated}</b><span>exceptions potentially avoided</span></div><div><b>{money(simulation.estimated_working_capital_unlocked)}</b><span>working capital unlocked</span></div><small>Directional estimate using current records and stated assumptions.</small></div>)}
      <div className="sim-note"><CircleHelp size={14} /> Estimates are directional and depend on source data quality.</div>
    </section>
  </div>;
}

function WorkflowView({ workflows = [], orgId, patch }) {
  const [module, setModule] = useState("PROCUREMENT");
  const [severity, setSeverity] = useState("CRITICAL");
  const [action, setAction] = useState("NOTIFY");
  const [target, setTarget] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const create = async (event) => {
    event.preventDefault(); setBusy(true);
    await patch(`/workflows/${orgId}`, { workflow_name: name || `${module} ${severity.toLowerCase()} automation`, trigger_module: module, trigger_severity: severity, action_type: action, action_target: target || "operations-lead", is_active: true }, "POST");
    setBusy(false); setName(""); setTarget("");
  };
  return <div className="content-grid workflow-grid"><section className="panel workflow-builder"><PanelHeader title="No-code workflow" eyebrow="AUTOMATION DESIGNER" /><p className="section-intro">Define a trigger and a response. Workflows run when matching operational signals are evaluated.</p>
    <form onSubmit={create} className="builder-form">
      <label>Workflow name<input value={name} onChange={(event) => setName(event.target.value)} placeholder="e.g. Escalate late critical orders" /></label>
      <div className="logic-block"><span className="logic-tag if-tag">IF</span><div className="logic-fields"><label>Module<select value={module} onChange={(event) => setModule(event.target.value)}>{["PROCUREMENT", "INVENTORY", "FINANCE", "AP"].map((item) => <option key={item}>{item}</option>)}</select></label><label>Severity<select value={severity} onChange={(event) => setSeverity(event.target.value)}>{["CRITICAL", "HIGH", "MEDIUM", "LOW"].map((item) => <option key={item}>{item}</option>)}</select></label></div></div>
      <div className="logic-connector"><span /> <ArrowDownRight size={14} /></div>
      <div className="logic-block"><span className="logic-tag then-tag">THEN</span><div className="logic-fields"><label>Action<select value={action} onChange={(event) => setAction(event.target.value)}>{["NOTIFY", "PLACE_PAYMENT_HOLD", "CREATE_TASK", "ESCALATE"].map((item) => <option key={item}>{item}</option>)}</select></label><label>Action target<input value={target} onChange={(event) => setTarget(event.target.value)} placeholder="team or queue" /></label></div></div>
      <button className="primary-button" disabled={busy}>{busy ? <LoaderCircle size={15} className="spin" /> : <Plus size={15} />} Create workflow</button>
    </form></section>
    <section className="panel"><PanelHeader title="Active workflows" eyebrow="AUTOMATIONS" trailing={<span className="count-badge">{workflows.length} TOTAL</span>} />
      {workflows.length ? <div className="workflow-list">{workflows.map((item) => <div className="workflow-row" key={item.id}><div className="workflow-glyph"><Workflow size={17} /></div><div className="workflow-main"><b>{item.workflow_name}</b><span>IF <strong>{item.trigger_module}</strong> · <strong>{item.trigger_severity}</strong> <ArrowRight size={11} /> THEN <strong>{item.action_type}</strong></span><small>Target: {item.action_target}</small></div><span className={`status-pill ${item.is_active ? "status-active" : "status-inactive"}`}>{item.is_active ? "ACTIVE" : "PAUSED"}</span></div>)}</div> : <EmptyState icon={Workflow} title="No workflows configured" text="Create a workflow to define a repeatable response." />}
    </section></div>;
}

function ExceptionsView({ exceptions = [], orgId, patch, flash }) {
  const [query, setQuery] = useState("");
  const filtered = exceptions.filter((exc) => `${exc.title} ${exc.module} ${exc.severity} ${exc.status}`.toLowerCase().includes(query.toLowerCase()));
  const resolve = async (exc) => {
    await patch(`/exceptions/${exc.id}?org_id=${encodeURIComponent(orgId)}`, { status: "RESOLVED", resolved_by: "Aditya Nair" });
    flash("Exception resolved and audit status updated");
  };
  return <section className="panel data-panel"><SectionTitle title="Exception register" detail="Governance queue · resolve actions are recorded against each exception" count={filtered.length} /><div className="table-toolbar"><label className="search-input"><Search size={15} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search exceptions…" /></label><button className="filter-button"><Filter size={14} /> All statuses <ChevronDown size={13} /></button></div>
    <DataTable columns={["PRIORITY", "EXCEPTION", "MODULE", "FINANCIAL IMPACT", "STATUS", "ACTION"]} rows={filtered} empty="No matching operational exceptions." renderRow={(exc) => <tr key={exc.id}><td><SeverityBadge severity={exc.severity} /></td><td><b>{exc.title}</b><small className="table-sub">{exc.description}</small></td><td><span className="module-label">{exc.module}</span></td><td className="amount-cell">{money(exc.financial_impact)}</td><td><span className={`status-pill ${exc.status === "OPEN" ? "status-open" : "status-resolved"}`}>{exc.status}</span></td><td>{exc.status === "OPEN" ? <button className="resolve-button" onClick={() => resolve(exc)}><Check size={13} /> Resolve</button> : <span className="audit-by">by {exc.resolved_by || "—"}</span>}</td></tr>} /></section>;
}
function SeverityBadge({ severity }) {
  return <span className={`severity-badge severity-${severity?.toLowerCase()}`}><i />{severity}</span>;
}
function impactRank(severity) { return ({ CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1 })[severity] || 0; }

function ProcurementView({ pos = [], labels }) {
  const delivered = pos.filter((po) => po.actual_delivery_date && po.expected_delivery_date);
  const onTime = delivered.filter((po) => po.actual_delivery_date <= po.expected_delivery_date).length;
  const avgApproval = pos.length ? pos.reduce((sum, po) => sum + (po.approval_days || 0), 0) / pos.length : 0;
  return <><div className="mini-kpi-row"><MiniKpi label="TOTAL PO SPEND" value={money(pos.reduce((sum, po) => sum + po.total_amount, 0))} /><MiniKpi label="PURCHASE ORDERS" value={pos.length} /><MiniKpi label="DELIVERY OTIF" value={delivered.length ? `${Math.round(onTime / delivered.length * 100)}%` : "—"} /><MiniKpi label="AVG. APPROVAL CYCLE" value={`${avgApproval.toFixed(1)} days`} /></div>
    <section className="panel data-panel"><SectionTitle title={`${labels.order} tracker`} detail="Delivery reliability and approval cycle performance" count={pos.length} /><DataTable columns={["PO NUMBER", "SUPPLIER", labels.items.toUpperCase(), "ORDER DATE", "EXPECTED", "DELIVERED", "APPROVAL", "PO VALUE"]} rows={pos} empty="Purchase orders appear here after they are imported." renderRow={(po) => {
      const late = po.actual_delivery_date && po.expected_delivery_date && po.actual_delivery_date > po.expected_delivery_date;
      return <tr key={po.id}><td><b className="mono">{po.po_number}</b></td><td>{po.vendor_name}</td><td><b>{po.item_code}</b><small className="table-sub">{po.item_description}</small></td><td>{dateLabel(po.order_date)}</td><td>{dateLabel(po.expected_delivery_date)}</td><td><span className={late ? "text-red" : ""}>{dateLabel(po.actual_delivery_date)}</span>{late && <small className="table-sub text-red">Late delivery</small>}</td><td><span className={(po.approval_days || 0) > 5 ? "text-amber" : ""}>{po.approval_days ?? "—"} days</span></td><td className="amount-cell">{money(po.total_amount)}</td></tr>;
    }} /></section></>;
}
function MiniKpi({ label, value }) {
  return <div className="mini-kpi"><span>{label}</span><b>{value}</b></div>;
}

function InventoryView({ inventory = [], invoices = [], labels }) {
  return <><div className="mini-kpi-row"><MiniKpi label={`${labels.items.toUpperCase()} TRACKED`} value={inventory.length} /><MiniKpi label="BELOW REORDER" value={inventory.filter((item) => item.stock_on_hand < item.reorder_level).length} /><MiniKpi label="AGEING STOCK > 90D" value={inventory.filter((item) => item.days_since_last_movement > 90).length} /><MiniKpi label="INVOICE VARIANCE" value={money(invoices.reduce((sum, invoice) => sum + Math.max(0, invoice.invoice_amount - invoice.po_reference_amount), 0))} /></div>
    <section className="panel data-panel inventory-table"><SectionTitle title="Stock health" detail="Reorder coverage, ageing and carrying capital" count={inventory.length} /><DataTable columns={[labels.items.toUpperCase(), "CATEGORY", "ON HAND", "REORDER POINT", "COVERAGE", "LAST MOVEMENT", "CAPITAL AT COST", "HEALTH"]} rows={inventory} renderRow={(item) => {
      const low = item.stock_on_hand < item.reorder_level; const ageing = item.days_since_last_movement > 90;
      return <tr key={item.id}><td><b>{item.item_code}</b><small className="table-sub">{item.item_description}</small></td><td>{item.category}</td><td><b>{item.stock_on_hand.toLocaleString("en-IN")}</b></td><td>{item.reorder_level.toLocaleString("en-IN")}</td><td>{item.reorder_level ? `${(item.stock_on_hand / item.reorder_level).toFixed(1)}×` : "—"}</td><td className={ageing ? "text-amber" : ""}>{item.days_since_last_movement} days</td><td className="amount-cell">{money(item.stock_on_hand * item.unit_cost)}</td><td><span className={`health-pill ${low ? "health-low" : ageing ? "health-age" : "health-good"}`}>{low ? "REORDER" : ageing ? "AGEING" : "HEALTHY"}</span></td></tr>;
    }} /></section>
    <section className="panel data-panel invoice-panel"><SectionTitle title="3-way invoice match audit" detail="Invoice amount compared against PO reference amount" count={invoices.length} /><DataTable columns={["INVOICE", "SUPPLIER", "PO REFERENCE", "PO AMOUNT", "INVOICE AMOUNT", "VARIANCE", "PAYMENT"]} rows={invoices} empty="No invoices to reconcile yet." renderRow={(invoice) => {
      const variance = invoice.invoice_amount - invoice.po_reference_amount;
      return <tr key={invoice.id}><td><b className="mono">{invoice.invoice_number}</b></td><td>{invoice.vendor_name}</td><td className="mono">{invoice.po_number}</td><td>{money(invoice.po_reference_amount)}</td><td className="amount-cell">{money(invoice.invoice_amount)}</td><td className={variance > 0 ? "text-red amount-cell" : "amount-cell"}>{variance > 0 ? "+" : ""}{money(variance)}</td><td><span className={`status-pill ${invoice.payment_status === "ON_HOLD" ? "status-open" : "status-active"}`}>{invoice.payment_status}</span></td></tr>;
    }} /></section></>;
}

function RulesView({ rules = [], orgId, patch, load }) {
  const [edits, setEdits] = useState({});
  const [busy, setBusy] = useState(false);
  const save = async () => {
    setBusy(true);
    try {
      for (const [id, threshold] of Object.entries(edits)) {
        await api(`/rules/${id}?org_id=${encodeURIComponent(orgId)}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ threshold_value: Number(threshold) }) });
      }
      await api(`/rules/${orgId}/evaluate`, { method: "POST" });
      setEdits({});
      await load();
    } catch (err) { window.alert(err.message); }
    finally { setBusy(false); }
  };
  return <section className="panel data-panel"><div className="rules-heading"><SectionTitle title="Business rules" detail="Active thresholds used to detect exceptions" count={rules.length} /><button className="primary-button" onClick={save} disabled={busy}><Check size={15} /> {busy ? "Saving…" : "Save & re-run"}</button></div>
    <div className="rule-list">{rules.map((rule) => <div className="rule-row" key={rule.id}><div className="rule-icon"><SlidersHorizontal size={16} /></div><div className="rule-name"><b>{rule.rule_name}</b><span>{rule.rule_code} <span>·</span> {rule.module}</span></div><span className="rule-metric">{rule.metric}</span><div className="rule-expression"><span>{rule.operator}</span><input type="number" step="any" value={edits[rule.id] ?? rule.threshold_value} onChange={(event) => setEdits((current) => ({ ...current, [rule.id]: event.target.value }))} /></div><SeverityBadge severity={rule.severity} /><span className={`status-pill ${rule.is_active ? "status-active" : "status-inactive"}`}>{rule.is_active ? "ACTIVE" : "PAUSED"}</span></div>)}</div>
    <div className="rules-note"><LockKeyhole size={14} /> Rule evaluations regenerate the tenant’s open exceptions from current purchase, stock and invoice records.</div>
  </section>;
}

function ImportView({ imports = [], orgId, flash, load, locationId }) {
  const [file, setFile] = useState(null);
  const [mappingText, setMappingText] = useState('{"PO Number":"po_number","Location ID":"location_id","Vendor Name":"vendor_name","Item Code":"item_code","Item Description":"item_description","Quantity":"quantity","Unit Price":"unit_price","Total Amount":"total_amount","Order Date":"order_date","Expected Delivery Date":"expected_delivery_date","Actual Delivery Date":"actual_delivery_date","Approval Days":"approval_days"}');
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const mapping = useMemo(() => { try { return JSON.parse(mappingText); } catch { return null; } }, [mappingText]);
  const submit = async (mode) => {
    if (!file) { setError("Choose a CSV file to continue."); return; }
    if (!mapping) { setError("Column mapping must be valid JSON."); return; }
    const form = new FormData(); form.append("file", file); form.append("mapping", JSON.stringify(mapping));
    if (mode === "preview") {
      setBusy(true); setError("");
      try { setPreview(await api("/connectors/csv/preview", { method: "POST", body: form })); }
      catch (err) { setError(err.message); }
      finally { setBusy(false); }
      return;
    }
    if (!preview) { setError("Preview the file before ingesting."); return; }
    setBusy(true); setError("");
    try {
      const result = await api(`/connectors/csv/ingest/${orgId}`, { method: "POST", body: form });
      flash(`${result.records_processed} records ingested · ${result.status}`);
      setPreview(null); setFile(null); await load();
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };
  return <div className="content-grid import-grid"><section className="panel import-wizard"><PanelHeader title="CSV upload wizard" eyebrow="DATA CONNECTOR" />
    <div className="wizard-steps"><span className="wizard-current"><i>1</i> Upload file</span><span><i>2</i> Map columns</span><span><i>3</i> Validate & ingest</span></div>
    <label className="upload-zone">{file ? <><div className="upload-icon"><Check size={20} /></div><b>{file.name}</b><span>{(file.size / 1024).toFixed(1)} KB · Ready to preview</span></> : <><div className="upload-icon"><UploadCloud size={21} /></div><b>Choose an ERP export CSV</b><span>Click to browse · CSV format</span></>}<input type="file" accept=".csv,text/csv" onChange={(event) => { setFile(event.target.files?.[0] || null); setPreview(null); setError(""); }} /></label>
    <label className="mapping-label">COLUMN MAPPING <span>CSV column → canonical field</span><textarea value={mappingText} onChange={(event) => setMappingText(event.target.value)} spellCheck="false" /></label>
    {error && <div className="inline-error">{error}</div>}
    {preview && <div className="preview-result"><b><Check size={15} /> Preview complete</b><span>{preview.valid_rows} valid rows · {preview.errors.length} validation issues</span>{preview.errors.slice(0, 3).map((item, index) => <small key={index}>Row {item.row}: {item.error}</small>)}{preview.sample.length > 0 && <pre>{JSON.stringify(preview.sample[0], null, 2)}</pre>}</div>}
    <div className="upload-actions"><button className="secondary-button" onClick={() => submit("preview")} disabled={busy || !file}>{busy ? <LoaderCircle size={15} className="spin" /> : <Search size={15} />} Preview & validate</button><button className="primary-button" onClick={() => submit("ingest")} disabled={busy || !preview || !preview.valid_rows}><Download size={15} /> Ingest records</button></div>
    <div className="import-footnote"><LockKeyhole size={13} /> Duplicate PO numbers update existing tenant records. All imports are audit logged.</div>
  </section>
    <section className="panel import-guidance"><PanelHeader title="Import guidance" eyebrow="BUILT FOR ERP DATA" /><div className="guidance-list"><GuidanceItem number="01" title="Map your headers" text="Connect your CSV column names to the canonical purchase order fields." /><GuidanceItem number="02" title="Preview before loading" text="Review parsed rows and validation errors before any database changes." /><GuidanceItem number="03" title="Tenant-safe upsert" text="Only locations belonging to this organization are accepted. Existing PO numbers are updated." /></div><div className="sample-callout"><FileUp size={17} /><div><b>Sample ERP purchase orders</b><span>See docs/sample_erp_pos.csv for the expected shape.</span></div></div></section>
    <section className="panel import-history"><SectionTitle title="Import audit history" detail="Tenant data-load log" count={imports.length} /><DataTable columns={["FILE", "SOURCE", "IMPORTED", "RECORDS", "STATUS", "IMPORTED BY"]} rows={imports} empty="Completed data imports will be recorded here." renderRow={(item) => <tr key={item.id}><td><b>{item.file_name}</b></td><td>{item.source_type}</td><td>{dateLabel(item.created_at)}</td><td>{item.records_processed}</td><td><span className={`status-pill ${item.status === "COMPLETED" ? "status-active" : "status-open"}`}>{item.status}</span></td><td>{item.imported_by || "—"}</td></tr>} /></section>
  </div>;
}
function GuidanceItem({ number, title, text }) {
  return <div className="guidance-item"><span>{number}</span><div><b>{title}</b><p>{text}</p></div></div>;
}

export default App;
