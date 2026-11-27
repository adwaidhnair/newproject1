import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity, ArrowDownRight, ArrowRight, Boxes, Check, ChevronDown, CircleHelp,
  Clock3, Download, FileUp, Filter, Gauge, GitBranch, Layers3, LoaderCircle,
  KeyRound, LockKeyhole, Menu, Play, Plus, RefreshCw, Search, ShieldAlert,
  SlidersHorizontal, Sparkles, UploadCloud, UserRound, UsersRound, Workflow, X,
} from "lucide-react";
import { tv } from "tailwind-variants";
import "./team.css";

const API = (import.meta.env.VITE_API_URL || import.meta.env.VITE_API_BASE_URL || "/api/v1").replace(/\/$/, "");
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
  { id: "admin-power", label: "Admin Power", icon: UsersRound },
];
const MODULES = NAV.filter((item) => item.id !== "admin-power");
const IMPORT_FIELDS = [
  { id: "po_number", label: "Purchase order number", required: true },
  { id: "location_id", label: "Location ID", required: true },
  { id: "vendor_name", label: "Vendor / supplier", required: true },
  { id: "item_code", label: "Item / material code", required: true },
  { id: "item_description", label: "Item description", required: true },
  { id: "quantity", label: "Quantity", required: true },
  { id: "unit_price", label: "Unit price", required: true },
  { id: "total_amount", label: "Total amount", required: true },
  { id: "order_date", label: "Order date", required: true },
  { id: "expected_delivery_date", label: "Expected delivery date" },
  { id: "actual_delivery_date", label: "Actual delivery date" },
  { id: "approval_days", label: "Approval days" },
  { id: "dept_id", label: "Department ID" },
];
const money = (value) =>
  new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(value || 0);
const dateLabel = (value) => value ? new Date(value).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" }) : "—";

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  const response = await fetch(`${API}${path}`, { ...options, headers, credentials: "include" });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try { message = (await response.json()).detail || message; } catch { /* no JSON body */ }
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

function App() {
  const [authenticated, setAuthenticated] = useState(false);
  const [authInitialized, setAuthInitialized] = useState(false);
  const [authMode, setAuthMode] = useState("login");
  const [authError, setAuthError] = useState("");
  const [authBusy, setAuthBusy] = useState(false);
  const [registrationEnabled, setRegistrationEnabled] = useState(false);
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [setupToken, setSetupToken] = useState("");
  const [organizationName, setOrganizationName] = useState("");
  const [industryType, setIndustryType] = useState("");
  const [invitation, setInvitation] = useState(null);
  const inviteToken = useMemo(() => new URLSearchParams(window.location.search).get("invite"), []);
  const [organizations, setOrganizations] = useState([]);
  const [currentUser, setCurrentUser] = useState(null);
  const [orgId, setOrgId] = useState("");
  const [locations, setLocations] = useState([]);
  const [locationId, setLocationId] = useState("");
  const [view, setView] = useState("control");
  const [data, setData] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [mobileNav, setMobileNav] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [profileError, setProfileError] = useState("");
  const [profileBusy, setProfileBusy] = useState(false);
  const org = organizations.find((item) => item.id === orgId);
  const currentRole = org?.role || "viewer";
  const isAdmin = ["admin", "owner"].includes(currentRole);
  const enabledModuleIds = useMemo(
    () => isAdmin ? MODULES.map((item) => item.id) : (org?.module_permissions || MODULES.map((item) => item.id)),
    [isAdmin, org],
  );
  const visibleNav = NAV.filter((item) => item.id === "admin-power"
    ? isAdmin
    : enabledModuleIds.includes(item.id));
  const activeNav = visibleNav.find((item) => item.id === view);
  const industryTypeCode = org?.industry_type?.trim().toUpperCase();
  const manufacturing = industryTypeCode === "MANUFACTURING";
  const labels = industryTypeCode === "FMCG"
    ? { items: "SKUs", locations: "Distribution hubs", vendor: "Supplier", order: "Purchase order" }
    : manufacturing
      ? { items: "Parts", locations: "Plants", vendor: "Supplier", order: "Purchase order" }
      : { items: "Items", locations: "Locations", vendor: "Supplier", order: "Purchase order" };
  const locationQuery = locationId ? `?location_id=${encodeURIComponent(locationId)}` : "";

  const authenticate = async (event) => {
    event.preventDefault();
    setAuthBusy(true);
    setAuthError("");
    try {
      const endpoint = inviteToken
        ? "/auth/accept-invitation"
        : authMode === "register"
          ? "/auth/register"
          : "/auth/login";
      const payload = inviteToken
        ? {
          token: inviteToken,
          email: invitation?.email || email,
          username,
          password,
          full_name: fullName || undefined,
        }
        : authMode === "register"
          ? {
            email,
            username,
            password,
            full_name: fullName,
            setup_token: setupToken,
            organization_id: orgId && orgId !== "__new__" ? orgId : undefined,
            organization_name: orgId === "__new__" ? organizationName : undefined,
            industry_type: orgId === "__new__" ? industryType : undefined,
          }
          : { username, password };
      const result = await api(endpoint, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
      });
      setCurrentUser(result.user);
      setAuthenticated(true);
      setAuthError("");
    } catch (err) {
      setAuthError(err.message);
    } finally {
      setAuthBusy(false);
    }
  };

  const load = useCallback(async () => {
    if (!orgId) return;
    setLoading(true);
    setError("");
    try {
      const context = await api(`/tenant-context/${orgId}`);
      const nextData = {
        kpis: {}, intelligence: {}, process: {}, exceptions: [], pos: [],
        inventory: [], invoices: [], rules: [], workflows: [], imports: [],
      };
      const moduleRequests = [
        ["control", `/control-tower/${orgId}${locationQuery}`, "kpis"],
        ["risk", `/intelligence/${orgId}${locationQuery}`, "intelligence"],
        ["process", `/process-mining/${orgId}`, "process"],
        ["exceptions", `/exceptions/${orgId}/list`, "exceptions"],
        ["procurement", `/procurement/${orgId}${locationQuery}`, "pos"],
        ["inventory", `/inventory-invoices/${orgId}${locationQuery}`, "inventory"],
        ["rules", `/rules/${orgId}`, "rules"],
        ["workflow", `/workflows/${orgId}`, "workflows"],
        ["imports", `/imports/${orgId}`, "imports"],
      ].filter(([moduleId]) => enabledModuleIds.includes(moduleId));
      const results = await Promise.all(moduleRequests.map(([, path]) => api(path)));
      moduleRequests.forEach(([, , key], index) => {
        if (key === "inventory") {
          nextData.inventory = results[index].inventory || [];
          nextData.invoices = results[index].invoices || [];
        } else {
          nextData[key] = results[index];
        }
      });
      setLocations(context.locations || []);
      setData(nextData);
    } catch (err) {
      setError(err.message || "Unable to connect to the operations API.");
    } finally {
      setLoading(false);
    }
  }, [orgId, locationQuery, enabledModuleIds]);

  useEffect(() => {
    let active = true;
    Promise.all([
      api("/auth/bootstrap-status"),
      api("/auth/me").catch((err) => {
        if (err.status === 401) return null;
        throw err;
      }),
    ]).then(([bootstrapStatus, session]) => {
      if (!active) return;
      setRegistrationEnabled(Boolean(bootstrapStatus.registration_enabled));
      const availableOrganizations = bootstrapStatus.organizations || [];
      setOrganizations(availableOrganizations);
      setOrgId((current) => (
        availableOrganizations.some((tenant) => tenant.id === current)
          ? current
          : (availableOrganizations[0]?.id || "")
      ));
      setAuthenticated(Boolean(session));
      if (session) {
        setCurrentUser(session.user);
        setOrganizations(session.organizations || []);
        setOrgId(session.organizations?.[0]?.id || "");
      } else {
        setCurrentUser(null);
      }
    }).catch((err) => {
      if (active) setAuthError(`Backend unavailable: ${err.message}`);
    }).finally(() => {
      if (active) {
        setAuthInitialized(true);
        setLoading(false);
      }
    });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    if (!authenticated) return;
    api("/auth/me")
      .then((session) => {
        setCurrentUser(session.user);
        const tenants = session.organizations || [];
        setOrganizations(tenants);
        setOrgId((current) => tenants.some((tenant) => tenant.id === current) ? current : (tenants[0]?.id || ""));
      })
      .catch((err) => {
        setAuthenticated(false);
        setCurrentUser(null);
        setAuthError(err.message);
      });
  }, [authenticated]);
  useEffect(() => {
    if (!inviteToken) return;
    setAuthMode("register");
    api(`/auth/invitations/${encodeURIComponent(inviteToken)}`)
      .then((result) => {
        setInvitation(result);
        setEmail(result.email);
      })
      .catch((err) => setAuthError(err.message));
  }, [inviteToken]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!toast) return undefined;
    const timeout = setTimeout(() => setToast(""), 3500);
    return () => clearTimeout(timeout);
  }, [toast]);

  const flash = (message) => setToast(message);
  const onOrganizationCreated = (organization) => {
    setOrganizations((current) => [
      ...current.filter((tenant) => tenant.id !== organization.id),
      { ...organization, role: "owner" },
    ]);
    setOrgId(organization.id);
    setLocationId("");
    setView("control");
    flash(`${organization.name} is ready`);
  };
  const onOrganizationUpdated = (updates) => {
    setOrganizations((current) => current.map((tenant) => (
      tenant.id === orgId ? { ...tenant, ...updates } : tenant
    )));
  };
  const patch = async (path, payload, method = "PATCH") => {
    try {
      await api(path, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      flash("Changes saved successfully");
      await load();
    } catch (err) { setError(err.message); }
  };
  useEffect(() => {
    if (!visibleNav.some((item) => item.id === view)) setView(visibleNav[0]?.id || "no-access");
  }, [view, visibleNav]);

  const signOut = async () => {
    try { await api("/auth/logout", { method: "POST" }); }
    catch (err) { setError(err.message); }
    setAuthenticated(false);
    setCurrentUser(null);
    setOrganizations([]);
    setOrgId("");
  };

  const changePassword = async (event) => {
    event.preventDefault();
    setProfileError("");
    if (newPassword !== confirmPassword) {
      setProfileError("The new passwords do not match.");
      return;
    }
    setProfileBusy(true);
    try {
      await api("/auth/change-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setProfileError("");
      flash("Password changed successfully");
    } catch (err) {
      setProfileError(err.message);
    } finally {
      setProfileBusy(false);
    }
  };

  if (!authInitialized) return <main className="auth-shell"><div className="auth-loading"><LoaderCircle className="spin" size={24} /> Connecting securely…</div></main>;

  if (!authenticated) return (
    <main className="auth-shell">
      <form className="auth-card" onSubmit={authenticate}>
        <div className="brand-mark"><Activity size={19} /></div>
        <p className="eyebrow">FLOUXI OPERATIONS INTELLIGENCE</p>
        <h1>{inviteToken ? "Join your organization" : authMode === "register" ? "First-time owner setup" : "Sign in"}</h1>
        <p className="muted">{inviteToken
          ? invitation ? `Accept your invitation to ${invitation.organization_name}.` : "Checking your invitation…"
          : authMode === "register"
            ? "One-time owner provisioning. A valid setup token is required; public self-registration is disabled."
            : "Sign in with your username and password to access your authorized organizations."}</p>
        {(authMode === "register" || inviteToken) && <label>Full name<input autoComplete="name" value={fullName} onChange={(event) => setFullName(event.target.value)} required /></label>}
        {authMode !== "login" || inviteToken
          ? <label>Email<input type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} readOnly={Boolean(inviteToken)} required /></label>
          : null}
        <label>Username<input autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} minLength={3} maxLength={64} required /></label>
        <label>Password<input type="password" autoComplete={authMode === "register" || inviteToken ? "new-password" : "current-password"} minLength={authMode === "register" || inviteToken ? 12 : undefined} value={password} onChange={(event) => setPassword(event.target.value)} required /></label>
        {authMode === "register" && !inviteToken && <>
          <label>First-owner setup token<input type="password" autoComplete="off" value={setupToken} onChange={(event) => setSetupToken(event.target.value)} required /></label>
          <label>Organization
            <select value={orgId} onChange={(event) => setOrgId(event.target.value)} required>
              <option value="" disabled>Select an organization</option>
              {organizations.map((tenant) => <option key={tenant.id} value={tenant.id}>{tenant.name}</option>)}
              <option value="__new__">Create a new organization…</option>
            </select>
          </label>
          {orgId === "__new__" && <>
            <label>Organization name<input value={organizationName} onChange={(event) => setOrganizationName(event.target.value)} required /></label>
            <label>Industry / business domain<input value={industryType} onChange={(event) => setIndustryType(event.target.value)} placeholder="e.g. Retail, Manufacturing, Healthcare" required /></label>
          </>}
        </>}
        {authError && <div className="error-banner">{authError}</div>}
        <button className="primary-button" type="submit" disabled={authBusy || (inviteToken && !invitation) || (authMode === "register" && !orgId)}>{authBusy ? "Please wait…" : inviteToken ? "Accept invitation" : authMode === "register" ? "Create owner account" : "Sign in"}</button>
        {!inviteToken && registrationEnabled && <button className="text-button" type="button" onClick={() => { setAuthError(""); setAuthMode(authMode === "login" ? "register" : "login"); }}>{authMode === "login" ? "First-time setup" : "Back to sign in"}</button>}
      </form>
    </main>
  );

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileNav ? "sidebar-open" : ""}`}>
        <div className="brand">
          <div className="brand-mark"><Activity size={19} strokeWidth={2.4} /></div>
          <div><strong>flouxi</strong><span>OPERATIONS INTELLIGENCE</span></div>
          <button className="icon-button sidebar-close" onClick={() => setMobileNav(false)} aria-label="Close menu"><X size={18} /></button>
        </div>
        <div className="workspace-label">WORKSPACE</div>
        <nav className="side-nav">
          {visibleNav.map(({ id, label, icon: Icon }, index) => (
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
          <div className="avatar">{currentUser?.full_name?.slice(0, 2)?.toUpperCase() || "ERP"}</div><div className="user-meta"><strong>{currentUser?.full_name || "Signed in"}</strong><span>{currentRole}</span></div>
          <div className="user-actions">
            <button className="text-button" onClick={() => { setProfileError(""); setProfileOpen(true); }}>Profile</button>
            <button className="text-button" onClick={signOut}>Sign out</button>
          </div>
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
            <div className="profile-switch" title={`Industry terminology follows ${org?.industry_type || "the selected organization"}`}>
              <span className="profile-active">{industryTypeCode === "FMCG" ? "FMCG" : manufacturing ? "MFG" : "GENERIC ERP"}</span>
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
            <ViewContent view={view} data={data} labels={labels} locationId={locationId} orgId={orgId} patch={patch} flash={flash} load={load} currentRole={currentRole} onOrganizationCreated={onOrganizationCreated} onOrganizationUpdated={onOrganizationUpdated} />
          }
          <footer className="page-footer"><span>Flouxi Operations Intelligence <span className="footer-dot">·</span> Secure tenant workspace</span><span>Data refreshes on demand <span className="footer-dot">·</span> INR</span></footer>
        </div>
      </main>
      {profileOpen && <div className="modal-scrim" onMouseDown={(event) => {
        if (event.target === event.currentTarget) setProfileOpen(false);
      }}>
        <section className="profile-dialog" role="dialog" aria-modal="true" aria-labelledby="profile-title">
          <div className="profile-dialog-header">
            <div className="profile-dialog-icon"><UserRound size={18} /></div>
            <div><span className="eyebrow">ACCOUNT SETTINGS</span><h2 id="profile-title">Your profile</h2></div>
            <button className="icon-button" type="button" onClick={() => setProfileOpen(false)} aria-label="Close profile"><X size={18} /></button>
          </div>
          <div className="profile-identity">
            <div className="avatar">{currentUser?.full_name?.slice(0, 2)?.toUpperCase() || "ERP"}</div>
            <div><b>{currentUser?.full_name}</b><span>{currentUser?.username} · {currentRole}</span></div>
          </div>
          <div className="profile-email"><span>Email</span><b>{currentUser?.email}</b></div>
          <form className="password-form" onSubmit={changePassword}>
            <div className="profile-section-title"><KeyRound size={15} /><b>Change password</b></div>
            <label>Current password<input type="password" autoComplete="current-password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} required /></label>
            <label>New password<input type="password" autoComplete="new-password" minLength={12} value={newPassword} onChange={(event) => setNewPassword(event.target.value)} required /></label>
            <label>Confirm new password<input type="password" autoComplete="new-password" minLength={12} value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} required /></label>
            <p className="password-hint">Use at least 12 characters. Changing your password signs out any other active sessions.</p>
            {profileError && <div className="error-banner">{profileError}</div>}
            <div className="profile-dialog-actions">
              <button className="secondary-button" type="button" onClick={() => setProfileOpen(false)}>Close</button>
              <button className="primary-button" type="submit" disabled={profileBusy}>{profileBusy ? "Saving…" : "Update password"}</button>
            </div>
          </form>
        </section>
      </div>}
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
    "admin-power": "Create users, manage role and module access, review audit history, and configure this workspace.",
  };
  return descriptions[view];
}

function ViewContent({ view, data, labels, locationId, orgId, patch, flash, load, currentRole, onOrganizationCreated, onOrganizationUpdated }) {
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
    case "admin-power": return <AdminPower orgId={orgId} currentRole={currentRole} onOrganizationCreated={onOrganizationCreated} onOrganizationUpdated={onOrganizationUpdated} />;
    case "no-access": return <section className="panel"><EmptyState icon={LockKeyhole} title="No modules enabled" text="Ask your organization administrator to grant access to an operational module." /></section>;
    default: return null;
  }
}

function AdminPower({ orgId, currentRole, onOrganizationCreated, onOrganizationUpdated }) {
  const [members, setMembers] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  const [settings, setSettings] = useState({ workspace_name: "", default_currency: "INR", timezone: "Asia/Kolkata" });
  const [newUser, setNewUser] = useState({
    full_name: "",
    email: "",
    username: "",
    role: "viewer",
    password: "",
    module_permissions: ["control"],
  });
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("analyst");
  const [invitationUrl, setInvitationUrl] = useState("");
  const [organizationName, setOrganizationName] = useState("");
  const [industryType, setIndustryType] = useState("");
  const [busy, setBusy] = useState(false);
  const [savingSettings, setSavingSettings] = useState(false);
  const [organizationBusy, setOrganizationBusy] = useState(false);
  const [error, setError] = useState("");
  const [organizationError, setOrganizationError] = useState("");
  const isOwner = currentRole === "owner";

  const loadAdminData = useCallback(async () => {
    try {
      const [memberList, settingsResult, logs] = await Promise.all([
        api(`/organizations/${orgId}/members`),
        api(`/organizations/${orgId}/admin-power/settings`),
        api(`/organizations/${orgId}/admin-power/audit-logs?limit=100`),
      ]);
      setMembers(memberList);
      setSettings(settingsResult.settings);
      setAuditLogs(logs);
      setError("");
    } catch (err) {
      setError(err.message);
    }
  }, [orgId]);

  useEffect(() => { loadAdminData(); }, [loadAdminData]);

  const createUser = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api(`/organizations/${orgId}/users`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(newUser),
      });
      setNewUser({
        full_name: "",
        email: "",
        username: "",
        role: "viewer",
        password: "",
        module_permissions: ["control"],
      });
      await loadAdminData();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const updateMember = async (member, changes) => {
    setError("");
    try {
      await api(`/organizations/${orgId}/members/${member.user_id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(changes),
      });
      await loadAdminData();
    } catch (err) {
      setError(err.message);
    }
  };

  const saveSettings = async (event) => {
    event.preventDefault();
    setSavingSettings(true);
    setError("");
    try {
      const result = await api(`/organizations/${orgId}/admin-power/settings`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ settings }),
      });
      onOrganizationUpdated({
        name: result.settings.workspace_name,
        base_currency: result.settings.default_currency,
      });
      await loadAdminData();
    } catch (err) {
      setError(err.message);
    } finally {
      setSavingSettings(false);
    }
  };

  const invite = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    setInvitationUrl("");
    try {
      const result = await api(`/organizations/${orgId}/invitations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: inviteEmail, role: inviteRole }),
      });
      setInvitationUrl(result.invitation_url || `${window.location.origin}/?invite=${encodeURIComponent(result.invitation_token)}`);
      setInviteEmail("");
      await loadAdminData();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const createOrganization = async (event) => {
    event.preventDefault();
    setOrganizationBusy(true);
    setOrganizationError("");
    try {
      const organization = await api("/organizations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: organizationName.trim(),
          industry_type: industryType.trim(),
          base_currency: "INR",
        }),
      });
      setOrganizationName("");
      setIndustryType("");
      onOrganizationCreated(organization);
    } catch (err) {
      setOrganizationError(err.message);
    } finally {
      setOrganizationBusy(false);
    }
  };

  return <div className="team-layout admin-power-layout">
    {error && <div className="error-banner"><ShieldAlert size={16} /><span>{error}</span></div>}
    <section className="panel team-panel admin-user-create">
      <PanelHeader title="Create a user" eyebrow="NO-CODE ACCOUNT PROVISIONING" />
      <p className="muted team-help">Set an initial password and module access. The user can sign in immediately with their username or email.</p>
      <form className="admin-user-form" onSubmit={createUser}>
        <label>Name<input autoComplete="name" value={newUser.full_name} onChange={(event) => setNewUser((current) => ({ ...current, full_name: event.target.value }))} required /></label>
        <label>Email<input type="email" autoComplete="email" value={newUser.email} onChange={(event) => setNewUser((current) => ({ ...current, email: event.target.value }))} required /></label>
        <label>Username<input autoComplete="username" minLength={3} maxLength={64} value={newUser.username} onChange={(event) => setNewUser((current) => ({ ...current, username: event.target.value }))} required /></label>
        <label>Initial password<input type="password" autoComplete="new-password" minLength={12} value={newUser.password} onChange={(event) => setNewUser((current) => ({ ...current, password: event.target.value }))} required /><small>At least 12 characters. Share it securely; the user can change it in Profile.</small></label>
        <label>Role<select value={newUser.role} onChange={(event) => setNewUser((current) => ({ ...current, role: event.target.value }))}><option value="viewer">Standard user · Viewer</option><option value="analyst">Standard user · Analyst</option>{isOwner && <option value="admin">Administrator</option>}</select></label>
        <div className="permission-picker">
          <span className="permission-picker-title">Initial operational modules</span>
          <div className="permission-check-grid">
            {MODULES.map((module) => <label key={module.id}>
              <input
                type="checkbox"
                checked={newUser.module_permissions.includes(module.id)}
                onChange={(event) => setNewUser((current) => ({
                  ...current,
                  module_permissions: event.target.checked
                    ? [...current.module_permissions, module.id]
                    : current.module_permissions.filter((id) => id !== module.id),
                }))}
              />
              {module.label}
            </label>)}
          </div>
          <small>Data Import stays in the operational workspace; it is not part of Admin Power.</small>
        </div>
        <button className="primary-button" type="submit" disabled={busy}>{busy ? "Creating user…" : "Create user"}</button>
      </form>
    </section>

    <section className="panel team-panel">
      <PanelHeader title="Users and module access" eyebrow="ACCESS MATRIX" trailing={<span className="count-badge">{members.length} USERS</span>} />
      <p className="muted team-help">Role and module changes are checked by the API as well as the sidebar. Access updates take effect on the next request.</p>
      <div className="admin-access-list">
        {members.map((member) => {
          const canManage = member.role !== "owner" && (member.role !== "admin" || isOwner);
          return <article className="admin-access-card" key={member.user_id}>
            <div className="admin-access-user">
              <div className="avatar">{member.full_name.slice(0, 2).toUpperCase()}</div>
              <div className="team-member-meta"><b>{member.full_name}</b><span>{member.username} · {member.email}</span></div>
              <label className="admin-role-control">Role
                <select disabled={!canManage} value={member.role} onChange={(event) => updateMember(member, { role: event.target.value })}>
                  <option value="viewer">Viewer</option><option value="analyst">Analyst</option>{isOwner && <option value="admin">Administrator</option>}
                </select>
              </label>
              <label className="admin-active-control"><input type="checkbox" checked={member.is_active} disabled={!canManage} onChange={(event) => updateMember(member, { is_active: event.target.checked })} /> Active</label>
            </div>
            <div className="permission-check-grid member-permission-grid">
              {MODULES.map((module) => <label key={module.id}>
                <input
                  type="checkbox"
                  checked={member.module_permissions.includes(module.id)}
                  disabled={!canManage || member.role === "admin"}
                  onChange={(event) => updateMember(member, {
                    module_permissions: event.target.checked
                      ? [...member.module_permissions, module.id]
                      : member.module_permissions.filter((id) => id !== module.id),
                  })}
                />
                {module.label}
              </label>)}
            </div>
            {!canManage && <small className="muted">{member.role === "owner" ? "Workspace owner" : "Only the owner can manage administrators"}</small>}
          </article>;
        })}
        {!members.length && <EmptyState icon={UsersRound} title="No members found" text="Organization access will appear here." />}
      </div>
    </section>

    <section className="panel team-panel">
      <PanelHeader title="System settings" eyebrow="WORKSPACE CONFIGURATION" />
      <form className="admin-settings-form" onSubmit={saveSettings}>
        <label>Workspace name<input value={settings.workspace_name} onChange={(event) => setSettings((current) => ({ ...current, workspace_name: event.target.value }))} minLength={1} maxLength={100} required /></label>
        <label>Default currency<input value={settings.default_currency} onChange={(event) => setSettings((current) => ({ ...current, default_currency: event.target.value.toUpperCase() }))} minLength={3} maxLength={3} required /></label>
        <label>Timezone<input value={settings.timezone} onChange={(event) => setSettings((current) => ({ ...current, timezone: event.target.value }))} maxLength={64} required /></label>
        <button className="primary-button" type="submit" disabled={savingSettings}>{savingSettings ? "Saving…" : "Save settings"}</button>
      </form>
    </section>

    <section className="panel team-panel">
      <PanelHeader title="Administrative audit log" eyebrow="GOVERNANCE" trailing={<span className="count-badge">{auditLogs.length} EVENTS</span>} />
      {auditLogs.length ? <div className="admin-audit-list">{auditLogs.map((entry) => <div className="admin-audit-row" key={entry.id}>
        <div><b>{entry.action.replaceAll(".", " ")}</b><span>{entry.actor} · {entry.actor_username}</span></div>
        <code>{JSON.stringify(entry.details)}</code>
        <time>{new Date(entry.created_at).toLocaleString()}</time>
      </div>)}</div> : <EmptyState icon={Activity} title="No administrative changes yet" text="User, permission, invitation, and settings changes will be recorded here." />}
    </section>

    <section className="panel team-panel">
      <PanelHeader title="Invite by link" eyebrow="ALTERNATIVE ONBOARDING" />
      <p className="muted team-help">Invitation links expire after seven days and grant access only to this organization. Use direct creation above when you want to set the initial password.</p>
      <form className="team-invite-form" onSubmit={invite}>
        <label>Email address<input type="email" value={inviteEmail} onChange={(event) => setInviteEmail(event.target.value)} required /></label>
        <label>Organization role
          <select value={inviteRole} onChange={(event) => setInviteRole(event.target.value)}>
            <option value="viewer">Viewer</option>
            <option value="analyst">Analyst</option>
            {isOwner && <option value="admin">Administrator</option>}
          </select>
        </label>
        <button className="primary-button" type="submit" disabled={busy}>{busy ? "Creating invite…" : "Create invitation link"}</button>
      </form>
      {invitationUrl && <div className="invitation-result">
        <b>Invitation link ready</b>
        <input aria-label="Invitation link" readOnly value={invitationUrl} onFocus={(event) => event.target.select()} />
        <button className="text-button" onClick={() => navigator.clipboard?.writeText(invitationUrl).then(() => {})}>Copy link</button>
      </div>}
      <p className="team-help muted">Only the owner can grant administrator access.</p>
    </section>

    {currentRole === "owner" && <section className="panel team-panel team-company-panel">
      <PanelHeader title="Create an organization" eyebrow="OWNER CONTROL" />
      <p className="muted team-help">Create a company workspace for any ERP or industry. Connect its operational records through governed imports; no ERP-specific master lists need to be maintained here.</p>
      {organizationError && <div className="error-banner"><ShieldAlert size={16} /><span>{organizationError}</span></div>}
      <form className="team-company-form" onSubmit={createOrganization}>
        <label>Organization name<input value={organizationName} onChange={(event) => setOrganizationName(event.target.value)} required /></label>
        <label>Industry / business domain<input value={industryType} onChange={(event) => setIndustryType(event.target.value)} placeholder="e.g. Retail, Manufacturing, Healthcare" required /></label>
        <button className="primary-button" type="submit" disabled={organizationBusy}>{organizationBusy ? "Creating organization…" : "Create organization"}</button>
      </form>
    </section>}
  </div>;
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
    await patch(`/exceptions/${exc.id}?org_id=${encodeURIComponent(orgId)}`, { status: "RESOLVED" });
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

function ImportView({ imports = [], orgId, flash, load }) {
  const [file, setFile] = useState(null);
  const [mapping, setMapping] = useState({});
  const [headers, setHeaders] = useState([]);
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [dragging, setDragging] = useState(false);
  const requiredFields = IMPORT_FIELDS.filter((field) => field.required).map((field) => field.id);
  const mappedFields = new Set(Object.values(mapping));
  const missingFields = requiredFields.filter((field) => !mappedFields.has(field));
  const selectFile = async (nextFile) => {
    if (!nextFile) return;
    if (!/\.(csv|xlsx)$/i.test(nextFile.name)) {
      setError("Choose a .csv or .xlsx file.");
      return;
    }
    if (nextFile.size > 10 * 1024 * 1024) {
      setError("Files must be 10 MiB or smaller.");
      return;
    }
    setFile(nextFile);
    setMapping({});
    setHeaders([]);
    setPreview(null);
    setError("");
    setBusy(true);
    const form = new FormData();
    form.append("org_id", orgId);
    form.append("file", nextFile);
    try {
      const suggestion = await api("/connectors/files/suggest-mapping", { method: "POST", body: form });
      setHeaders(suggestion.headers);
      setMapping(suggestion.mapping);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };
  const submit = async (mode) => {
    if (!file) { setError("Choose a CSV or XLSX file to continue."); return; }
    if (missingFields.length) { setError(`Map all required fields first: ${missingFields.map((field) => IMPORT_FIELDS.find((item) => item.id === field)?.label).join(", ")}.`); return; }
    const form = new FormData(); form.append("org_id", orgId); form.append("file", file); form.append("mapping", JSON.stringify(mapping));
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
      setPreview(null); setFile(null); setMapping({}); setHeaders([]); await load();
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };
  return <div className="content-grid import-grid"><section className="panel import-wizard"><PanelHeader title="CSV upload wizard" eyebrow="DATA CONNECTOR" />
    <div className="wizard-steps"><span className="wizard-current"><i>1</i> Upload file</span><span><i>2</i> Review suggested mapping</span><span><i>3</i> Validate & ingest</span></div>
    <label className={`upload-zone ${dragging ? "upload-zone-active" : ""}`}
      onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
      onDragLeave={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) setDragging(false); }}
      onDrop={(event) => {
        event.preventDefault();
        setDragging(false);
        void selectFile(event.dataTransfer.files?.[0]);
      }}>{file ? <><div className="upload-icon"><Check size={20} /></div><b>{file.name}</b><span>{(file.size / 1024).toFixed(1)} KB · CSV or Excel workbook</span></> : <><div className="upload-icon"><UploadCloud size={21} /></div><b>Drop an ERP export here, or choose a file</b><span>CSV or XLSX · maximum 10 MiB · no template required</span></>}<input type="file" accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" onChange={(event) => { void selectFile(event.target.files?.[0]); event.target.value = ""; }} /></label>
    {headers.length > 0 && <div className="mapping-editor"><div className="mapping-editor-heading"><b>Suggested column mapping</b><span>Review matches and adjust any unfamiliar headers.</span></div>
      {headers.map((header) => <label className="mapping-row" key={header}><span>{header}</span><select value={mapping[header] || ""} onChange={(event) => {
        const target = event.target.value;
        setMapping((current) => {
          const next = { ...current };
          delete next[header];
          if (target) {
            for (const [source, field] of Object.entries(next)) if (field === target) delete next[source];
            next[header] = target;
          }
          return next;
        });
        setPreview(null);
      }}><option value="">Do not import</option>{IMPORT_FIELDS.map((field) => <option key={field.id} value={field.id}>{field.label}{field.required ? " · required" : ""}</option>)}</select></label>)}
      {missingFields.length > 0 && <p className="mapping-warning">Still required: {missingFields.map((field) => IMPORT_FIELDS.find((item) => item.id === field)?.label).join(", ")}</p>}
    </div>}
    {error && <div className="inline-error">{error}</div>}
    {preview && <div className={`preview-result ${preview.errors.length ? "preview-result-invalid" : ""}`}><b>{preview.errors.length ? <ShieldAlert size={15} /> : <Check size={15} />} {preview.errors.length ? "Fix validation issues before importing" : "Preview complete"}</b><span>{preview.valid_rows} valid rows · {preview.errors.length} validation issues</span>{preview.errors.slice(0, 5).map((item, index) => <small key={index}>Row {item.row ?? "—"}: {item.error}</small>)}{preview.sample.length > 0 && <pre>{JSON.stringify(preview.sample[0], null, 2)}</pre>}</div>}
    <div className="upload-actions"><button className="secondary-button" onClick={() => submit("preview")} disabled={busy || !file || missingFields.length > 0}>{busy ? <LoaderCircle size={15} className="spin" /> : <Search size={15} />} Preview & validate</button><button className="primary-button" onClick={() => submit("ingest")} disabled={busy || !preview || preview.errors.length > 0 || !preview.valid_rows}><Download size={15} /> Ingest records</button></div>
    <div className="import-footnote"><LockKeyhole size={13} /> Duplicate PO numbers update existing tenant records. All imports are audit logged.</div>
  </section>
    <section className="panel import-guidance"><PanelHeader title="Import guidance" eyebrow="BUILT FOR ERP DATA" /><div className="guidance-list"><GuidanceItem number="01" title="No template required" text="Upload a CSV or Excel export. Common header names and synonyms are matched automatically." /><GuidanceItem number="02" title="Review before loading" text="Confirm the suggested field mapping, then inspect row-level validation issues. Invalid files are never partially ingested." /><GuidanceItem number="03" title="Tenant-safe upsert" text="Only locations and departments belonging to this organization are accepted. Existing PO numbers are updated." /></div><div className="sample-callout"><FileUp size={17} /><div><b>Supported data</b><span>Purchase order exports in CSV and XLSX formats · up to 10 MiB per file.</span></div></div></section>
    <section className="panel import-history"><SectionTitle title="Import audit history" detail="Tenant data-load log" count={imports.length} /><DataTable columns={["FILE", "SOURCE", "IMPORTED", "RECORDS", "STATUS", "IMPORTED BY"]} rows={imports} empty="Completed data imports will be recorded here." renderRow={(item) => <tr key={item.id}><td><b>{item.file_name}</b></td><td>{item.source_type}</td><td>{dateLabel(item.created_at)}</td><td>{item.records_processed}</td><td><span className={`status-pill ${item.status === "COMPLETED" ? "status-active" : "status-open"}`}>{item.status}</span></td><td>{item.imported_by || "—"}</td></tr>} /></section>
  </div>;
}
function GuidanceItem({ number, title, text }) {
  return <div className="guidance-item"><span>{number}</span><div><b>{title}</b><p>{text}</p></div></div>;
}

export default App;
