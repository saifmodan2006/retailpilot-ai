import DataTable from "./components/DataTable";
import Landing from "./pages/Landing";
import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  Link,
  NavLink,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Legend,
} from "recharts";
import {
  Activity,
  ArrowDownToLine,
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  BookOpen,
  Boxes,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  ClipboardCheck,
  Clock3,
  FileSpreadsheet,
  Filter,
  LayoutDashboard,
  Loader2,
  Menu,
  Package,
  Plug,
  Plus,
  Settings2,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  UploadCloud,
  Wallet,
  X,
  Zap,
} from "lucide-react";
import {
  api,
  compactMoney,
  fileDownload,
  initialFilters,
  money,
  sampleUrl,
  num,
  params,
  type Filters,
  type Row,
} from "./api";

const navigation = [
  {
    label: "WORKSPACE",
    items: [
      ["overview", "Overview", LayoutDashboard],
      ["sales", "Sales analytics", BarChart3],
      ["inventory", "Inventory intelligence", Boxes],
      ["forecast", "Demand forecasting", TrendingUp],
    ],
  },
  {
    label: "OPERATIONS",
    items: [
      ["imports", "Data import center", UploadCloud],
      ["reports", "MIS report builder", FileSpreadsheet],
      ["workflows", "Automations", Zap],
      ["approvals", "Approval center", ClipboardCheck],
    ],
  },
  {
    label: "INTELLIGENCE",
    items: [["analyst", "AI business analyst", Sparkles]],
  },
  {
    label: "ADMINISTRATION",
    items: [
      ["audit", "Audit logs", Activity],
      ["integrations", "Integrations", Plug],
      ["settings", "Settings", Settings2],
    ],
  },
] as const;
const titles: Record<string, [string, string]> = {
  overview: [
    "Business overview",
    "A clear view of your retail business. Every number, connected.",
  ],
  sales: [
    "Sales analytics",
    "Understand what sells, where it sells, and what drives your margin.",
  ],
  inventory: [
    "Inventory intelligence",
    "Keep the right stock in the right place, at the right time.",
  ],
  forecast: [
    "Demand forecasting",
    "Plan ahead with transparent, backtested demand estimates.",
  ],
  imports: [
    "Data import center",
    "Turn your spreadsheets into dependable business data.",
  ],
  reports: [
    "MIS report builder",
    "From daily operations to the boardroom. Reports that add up.",
  ],
  analyst: [
    "AI business analyst",
    "Your business questions. Answers grounded in your data.",
  ],
  workflows: [
    "Automation workflows",
    "Less routine work. More time for the decisions that matter.",
  ],
  approvals: [
    "Approval center",
    "A human decision behind every purchasing action.",
  ],
  audit: ["Audit logs", "A traceable history of your workspace activity."],
  integrations: [
    "Integrations",
    "Connect your operations, one dependable source at a time.",
  ],
  settings: [
    "Workspace settings",
    "Your planning rules, your business context.",
  ],
};
const palette = [
  "#087f6d",
  "#6172a8",
  "#8aaf99",
  "#c68c38",
  "#7094af",
  "#ba7d70",
];
const reportTypes = [
  "Daily sales MIS",
  "Weekly store performance",
  "Monthly management summary",
  "Category sales analysis",
  "SKU inventory",
  "Low stock",
  "Dead stock and ageing",
  "Stock cover",
  "Working capital",
];
const questions = [
  "Which stores had the highest sales last month?",
  "Which products are likely to run out within 14 days?",
  "Which category has the most dead-stock value?",
  "What is our current inventory value?",
  "Which SKUs should management review for reordering?",
  "Why did revenue change compared with the previous month?",
];

function Brand({ small = false }: { small?: boolean }) {
  return (
    <div className="brand">
      <span className="brandmark">
        <BarChart3 size={small ? 19 : 23} />
      </span>
      <span>
        RetailPilot<span className="ai-mark">AI</span>
      </span>
    </div>
  );
}
function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: string;
}) {
  return <span className={`badge ${tone}`}>{children}</span>;
}
function Empty({
  title = "No data yet",
  text = "Load the synthetic dataset to explore calculated insights.",
  action,
}: {
  title?: string;
  text?: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <span className="empty-icon">
        <Boxes size={30} />
      </span>
      <h3>{title}</h3>
      <p>{text}</p>
      {action}
    </div>
  );
}
function Loading() {
  return (
    <div className="loading">
      <Loader2 className="spin" size={22} /> Calculating from your data…
    </div>
  );
}
function FocusDialog({
  children,
  onClose,
}: {
  children: ReactNode;
  onClose: () => void;
}) {
  const ref = useRef<HTMLElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const root = ref.current;
    if (!root) return;
    const targets = () =>
      Array.from(
        root.querySelectorAll<HTMLElement>(
          'button:not(:disabled),input:not(:disabled),select:not(:disabled),a[href],[tabindex="0"]',
        ),
      );
    targets()[0]?.focus();
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "Tab") {
        const elements = targets();
        const first = elements[0],
          last = elements.at(-1);
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last?.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first?.focus();
        }
      }
    };
    root.addEventListener("keydown", key);
    return () => {
      root.removeEventListener("keydown", key);
      previous?.focus();
    };
  }, [onClose]);
  return (
    <section
      ref={ref}
      role="dialog"
      aria-modal="true"
      aria-label="Recommendation details"
      className="modal"
      onClick={(e) => e.stopPropagation()}
    >
      {children}
    </section>
  );
}
function ErrorBox({ error }: { error: unknown }) {
  return (
    <div className="error" role="alert">
      {error instanceof Error
        ? error.message
        : "Something went wrong. Please retry."}
    </div>
  );
}
function Panel({
  title,
  sub,
  aside,
  children,
  className = "",
}: {
  title: string;
  sub?: string;
  aside?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel-head">
        <div>
          <h3>{title}</h3>
          {sub && <p>{sub}</p>}
        </div>
        {aside}
      </div>
      {children}
    </section>
  );
}

function RevenueChart({ data }: { data: Row[] }) {
  return (
    <div className="chart">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart
          data={data}
          margin={{ top: 15, right: 15, bottom: 0, left: 0 }}
        >
          <defs>
            <linearGradient id="revenueFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#2f8268" stopOpacity={0.19} />
              <stop offset="100%" stopColor="#2f8268" stopOpacity={0.01} />
            </linearGradient>
          </defs>
          <CartesianGrid
            vertical={false}
            stroke="#edf0eb"
            strokeDasharray="3 4"
          />
          <XAxis
            dataKey="date"
            tickFormatter={(d) =>
              new Date(d + "T00:00:00").toLocaleDateString("en-IN", {
                day: "numeric",
                month: "short",
              })
            }
            minTickGap={42}
            axisLine={false}
            tickLine={false}
            tick={{ fontSize: 11, fill: "#667085" }}
            dy={10}
          />
          <YAxis
            tickFormatter={compactMoney}
            axisLine={false}
            tickLine={false}
            tick={{ fontSize: 11, fill: "#667085" }}
            width={68}
          />
          <Tooltip
            formatter={(v) => money(Number(v))}
            labelStyle={{ color: "#223a30" }}
            contentStyle={{ borderRadius: 10, borderColor: "#e5e9e3" }}
          />
          <Area
 isAnimationActive={false}
            name="Net revenue"
            type="monotone"
            dataKey="revenue"
            stroke="#087f6d"
            strokeWidth={2.5}
            fill="url(#revenueFill)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function App() {
  const navigate = useNavigate();
  const location = useLocation();
  const qc = useQueryClient();
  const [active, setActive] = useState(
    Boolean(localStorage.getItem("rp-token")),
  );
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [failure, setFailure] = useState("");
  const [mobile, setMobile] = useState(false);
  const [filters, setFilters] = useState<Filters>(initialFilters);
  const start = async () => {
    setBusy(true);
    setFailure("");
    try {
      const data = await api("/demo/session", { method: "POST" });
      localStorage.setItem("rp-token", data.access_token);
      setActive(true);
      qc.clear();
      navigate("/app/overview");
    } catch (e) {
      setFailure((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const act = async (job: () => Promise<any>, message: string) => {
    setBusy(true);
    setFailure("");
    try {
      await job();
      await qc.invalidateQueries();
      setNotice(message);
    } catch (e) {
      setFailure((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const path = location.pathname.split("/")[2] ?? "overview";
  const me = useQuery({
    queryKey: ["me"],
    queryFn: () => api("/me"),
    enabled: active,
  });
  const cat = useQuery({
    queryKey: ["catalog"],
    queryFn: () => api("/catalog"),
    enabled: active,
  });
  const data = useQuery({
    queryKey: ["analytics", filters],
    queryFn: () => api("/analytics?" + params(filters)),
    enabled: active && ["overview", "sales"].includes(path),
  });
  const seedDemo = () =>
    act(
      () => api("/demo/seed", { method: "POST" }),
      "Synthetic data loaded. Your workspace is ready.",
    );
  if (!location.pathname.startsWith("/app"))
    return <Landing start={start} busy={busy} error={failure} brand={<Brand/>} />;
  if (!active)
    return (
      <div className="session-gate">
        <Brand />
        <Empty
          title="Start your retail workspace"
          text="Create an isolated demo session to explore RetailPilot."
          action={
            <button className="btn primary" onClick={start} disabled={busy}>
              Start demo
            </button>
          }
        />
        {failure && <ErrorBox error={new Error(failure)} />}
      </div>
    );
  const ready = Boolean(cat.data?.stores?.length);
  const section = titles[path] ?? titles.overview;
  return (
    <div className="app-shell"><a href="#main-content" className="skip-link">Skip to main content</a>
      <aside className={`sidebar ${mobile ? "open" : ""}`}>
        <Link to="/" className="brand-link">
          <Brand />
        </Link>
        <button
          className="workspace-selector"
          onClick={() => navigate("/app/settings")}
        >
          <span className="workspace-avatar">T</span>
          <span>
            <strong>Threadline Retail</strong>
            <small>Demo workspace</small>
          </span>
          <ChevronDown size={15} />
        </button>
        <nav>
          {navigation.map((group) => (
            <div className="nav-group" key={group.label}>
              <div className="nav-label">{group.label}</div>
              {group.items.map(([url, label, Icon]) => (
                <NavLink
                  key={url}
                  to={"/app/" + url}
                  onClick={() => setMobile(false)}
                  className={({ isActive }) =>
                    isActive ? "nav-item active" : "nav-item"
                  }
                >
                  <Icon size={18} />
                  <span>{label}</span>
                  {url === "analyst" && <span className="nav-new">NEW</span>}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        <div className="sidebar-help">
          <span className="help-icon">
            <BookOpen size={19} />
          </span>
          <strong>A little guidance?</strong>
          <p>Take the complete data-to-decision journey.</p>
          <button
            onClick={() => {
              setNotice(
                "Demo: load data → import sample → review inventory → submit approval → switch to demo manager → approve → generate MIS → ask the analyst.",
              );
              navigate("/app/overview");
            }}
          >
            View demo guide <ArrowUpRight size={14} />
          </button>
        </div>
        <div className="sidebar-bottom">
          <span className="live-dot" /> Fictional demo workspace <span>v1.0</span>
        </div>
      </aside>
      {mobile && (
        <button
          className="scrim"
          aria-label="Close navigation"
          onClick={() => setMobile(false)}
        />
      )}
      <div className="main-shell">
        <header className="topbar">
          <button
            className="icon-btn mobile-menu"
            aria-label="Open navigation"
            onClick={() => setMobile(true)}
          >
            <Menu size={20} />
          </button>
          <div className="breadcrumb">
            Workspace <ChevronRight size={14} />
            <strong>{path === "overview" ? "Overview" : section[0]}</strong>
          </div>
          <div className="top-actions">
            <span className="top-demo">
              <span className="live-dot" /> Synthetic data demo
            </span>
            <button
              className="icon-btn"
              aria-label="Demo help"
              onClick={() =>
                setNotice(
                  "All figures are calculated from fictional data. Reporting date: 18 October 2026. Your session has its own isolated workspace.",
                )
              }
            >
              <CircleHelp size={19} />
            </button>
            <Link to="/app/settings" aria-label="Profile and workspace settings" className="avatar">
              {me.data?.user.role === "manager" ? "DM" : "DA"}
            </Link>
          </div>
        </header>
        <main id="main-content" className="main-content">
          <div className="page-heading">
            <div>
              <div className="eyebrow">YOUR RETAIL COMMAND CENTER</div>
              <h1>
                {section[0]}
                {path === "overview" && <span className="heading-dot" />}
              </h1>
              <p>{section[1]}</p>
            </div>
            <div className="heading-actions">
              {!ready ? (
                <button
                  className="btn primary"
                  onClick={seedDemo}
                  disabled={busy}
                >
                  {busy ? (
                    <Loader2 className="spin" size={16} />
                  ) : (
                    <Plus size={16} />
                  )}{" "}
                  Load demo data
                </button>
              ) : (
                <>
                  <Link className="btn" to="/app/imports">
                    <UploadCloud size={16} /> Import data
                  </Link>
                  <Link className="btn primary" to="/app/reports">
                    <ArrowDownToLine size={16} /> Create report
                  </Link>
                </>
              )}
            </div>
          </div>
          {notice && (
            <div className="toast" role="status">
              <CheckCircle2 size={18} />
              <span>{notice}</span>
              <button
                aria-label="Dismiss notice"
                className="icon-btn"
                onClick={() => setNotice("")}
              >
                <X size={16} />
              </button>
            </div>
          )}
          {failure && <ErrorBox error={new Error(failure)} />}
          {me.isError && (
            <div className="error">
              Session unavailable.{" "}
              <button onClick={start}>Start a new session</button>
            </div>
          )}
          {["overview", "sales", "inventory", "forecast", "reports"].includes(
            path,
          ) && (
            <div className="filterbar">
              <div className="filter-label">
                <Filter size={15} />
                <span>Filters</span>
              </div>
              <label>
                <span className="sr-only">Start date</span>
                <input
                  aria-label="Start date"
                  type="date"
                  value={filters.start}
                  max={filters.end}
                  onChange={(e) =>
                    setFilters({ ...filters, start: e.target.value })
                  }
                />
              </label>
              <span className="muted">—</span>
              <label>
                <span className="sr-only">End date</span>
                <input
                  aria-label="End date"
                  type="date"
                  value={filters.end}
                  min={filters.start}
                  max="2026-10-18"
                  onChange={(e) =>
                    setFilters({ ...filters, end: e.target.value })
                  }
                />
              </label>
              <select
                aria-label="Store"
                value={filters.store_id ?? ""}
                onChange={(e) =>
                  setFilters({
                    ...filters,
                    store_id: Number(e.target.value) || undefined,
                  })
                }
              >
                <option value="">All stores</option>
                {cat.data?.stores.map((r: Row) => (
                  <option key={r.id} value={r.id}>
                    {r.name}
                  </option>
                ))}
              </select>
              <select
                aria-label="Category"
                value={filters.category_id ?? ""}
                onChange={(e) =>
                  setFilters({
                    ...filters,
                    category_id: Number(e.target.value) || undefined,
                  })
                }
              >
                <option value="">All categories</option>
                {cat.data?.categories.map((r: Row) => (
                  <option key={r.id} value={r.id}>
                    {r.name}
                  </option>
                ))}
              </select>
              <details className="extra-filters">
                <summary>
                  More <ChevronDown size={13} />
                </summary>
                <div>
                  <label>
                    Brand
                    <select
                      aria-label="Brand"
                      value={filters.brand_id ?? ""}
                      onChange={(e) =>
                        setFilters({
                          ...filters,
                          brand_id: Number(e.target.value) || undefined,
                        })
                      }
                    >
                      <option value="">All brands</option>
                      {cat.data?.brands.map((r: Row) => (
                        <option key={r.id} value={r.id}>
                          {r.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    SKU
                    <select
                      aria-label="SKU"
                      value={filters.sku_id ?? ""}
                      onChange={(e) =>
                        setFilters({
                          ...filters,
                          sku_id: Number(e.target.value) || undefined,
                        })
                      }
                    >
                      <option value="">All SKUs</option>
                      {cat.data?.skus.map((r: Row) => (
                        <option key={r.sku_id} value={r.sku_id}>
                          {r.sku} · {r.size}
                        </option>
                      ))}
                    </select>
                  </label>
                  <button
                    className="btn"
                    onClick={() => setFilters(initialFilters)}
                  >
                    Reset filters
                  </button>
                </div>
              </details>
              <span className="filter-fresh">
                <span className="live-dot" /> As of 18 Oct 2026
              </span>
            </div>
          )}
          {cat.isLoading ? (
            <Loading />
          ) : !ready ? (
            <Panel
              title="Your next clear decision starts here"
              sub="A complete retail business, ready to explore."
            >
              <Empty
                title="Meet your demo workspace"
                text="12 stores. 180 products. A year of fictional retail operations. Load the data to calculate your first insights."
                action={
                  <button
                    className="btn primary"
                    onClick={seedDemo}
                    disabled={busy}
                  >
                    {busy ? (
                      <Loader2 className="spin" size={16} />
                    ) : (
                      <Plus size={16} />
                    )}{" "}
                    Load demo data
                  </button>
                }
              />
            </Panel>
          ) : (
            <Routes>
              <Route
                path="/app/overview"
                element={
                  data.isFetching ? (
                    <Loading />
                  ) : data.isError ? (
                    <ErrorBox error={data.error} />
                  ) : (
                    <Overview data={data.data} filters={filters} />
                  )
                }
              />
              <Route
                path="/app/sales"
                element={
                  <Sales
                    data={data.data}
                    loading={data.isLoading}
                    error={data.error}
                  />
                }
              />
              <Route
                path="/app/inventory"
                element={<Inventory filters={filters} act={act} busy={busy} />}
              />
              <Route
                path="/app/forecast"
                element={<Forecast filters={filters} />}
              />
              <Route
                path="/app/imports"
                element={<Imports act={act} busy={busy} />}
              />
              <Route
                path="/app/reports"
                element={<Reports filters={filters} act={act} busy={busy} />}
              />
              <Route
                path="/app/analyst"
                element={<Analyst filters={filters} />}
              />
              <Route
                path="/app/workflows"
                element={<Workflows act={act} busy={busy} />}
              />
              <Route
                path="/app/approvals"
                element={
                  <Approvals
                    manager={me.data?.user.role === "manager"}
                    act={act}
                    busy={busy}
                  />
                }
              />
              <Route path="/app/audit" element={<Audit />} />
              <Route
                path="/app/integrations"
                element={<Integrations act={act} busy={busy} />}
              />
              <Route
                path="/app/settings"
                element={
                  <Settings
                    manager={me.data?.user.role === "manager"}
                    act={act}
                    busy={busy}
                    start={start}
                  />
                }
              />
              <Route
                path="*"
                element={
                  <Empty
                    title="Page not found"
                    action={
                      <Link to="/app/overview" className="btn">
                        Back to overview
                      </Link>
                    }
                  />
                }
              />
            </Routes>
          )}
          <footer className="app-footer">
            <span>
              <ShieldCheck size={13} /> Fictional data. Real calculations.
            </span>
            <span>
              RetailPilot AI <span className="footer-dot">·</span> Built for
              better retail decisions
            </span>
          </footer>
        </main>
      </div>
    </div>
  );
}

type Act = (job: () => Promise<any>, message: string) => Promise<void>;
type ActionProps = { act: Act; busy: boolean };
function KPI({
  label,
  value,
  note,
  icon,
  accent = false,
  definition,
}: {
  label: string;
  value: string;
  note: string;
  icon: ReactNode;
  accent?: boolean;
  definition: string;
}) {
  return (
    <div className={`kpi ${accent ? "accent" : ""}`}>
      <div className="kpi-label">
        <span>{label}</span>
        <span
          title={definition}
          className="kpi-help"
          tabIndex={0}
          aria-label={definition}
        >
          {icon}
        </span>
      </div>
      <strong>{value}</strong>
      <div className="kpi-note">
        {accent ? (
          <span className="small-dot" />
        ) : (
          <span className="small-line" />
        )}
        {note}
      </div>
    </div>
  );
}

function Overview({ data, filters }: { data: Row; filters: Filters }) {
  const activity = useQuery({
    queryKey: ["workflows"],
    queryFn: () => api<Row[]>("/workflows"),
  });
  if (!data) return <Loading />;
  const m = data.metrics;
  return (
    <>
      <div className="insight-strip">
        <span className="insight-icon">
          <Sparkles size={18} />
        </span>
        <div>
          <strong>A little clarity for your next move.</strong>
          <span>
            {num(m.low_stock)} store–SKU positions need stock attention.{" "}
            {compactMoney(m.dead_stock_value)} is tied up in inactive inventory.
          </span>
        </div>
        <Link to="/app/inventory">
          Review insights <ArrowRight size={15} />
        </Link>
      </div>
      <div className="kpi-grid">
        <KPI
          label="Net revenue"
          value={compactMoney(m.revenue)}
          note="After discounts & returns"
          icon={<Wallet size={18} />}
          accent
          definition="Sum of transaction revenue in the selected period, net of discounts and returns."
        />
        <KPI
          label="Gross profit"
          value={compactMoney(m.gross_profit)}
          note={`${num(m.margin)}% gross margin`}
          icon={<TrendingUp size={18} />}
          definition="Net revenue minus cost of goods sold; excludes operating expenses."
        />
        <KPI
          label="Units sold"
          value={num(m.units)}
          note="Net of returned units"
          icon={<Package size={18} />}
          definition="Sum of signed sales quantities for the selected period."
        />
        <KPI
          label="Inventory value"
          value={compactMoney(m.inventory_value)}
          note={`${num(m.stock)} units on hand`}
          icon={<Boxes size={18} />}
          definition="Latest stock quantity per store/SKU on or before the end date multiplied by purchase cost."
        />
      </div>
      <div className="overview-grid">
        <Panel
          title="Revenue performance"
          sub="The daily rhythm of your business"
          aside={
            <Badge>
              <span className="small-dot green-dot" /> Net revenue
            </Badge>
          }
        >
          <RevenueChart data={data.trend} />
          <div className="chart-footer">
            <span>NET SALES · INR</span>
            <span>
              {filters.start.split("-").reverse().join("/")} –{" "}
              {filters.end.split("-").reverse().join("/")}
            </span>
          </div>
        </Panel>
        <Panel title="Sales by category" sub="Where your revenue comes from">
          <div className="donut-wrap">
            <ResponsiveContainer width="100%" height={205}>
              <PieChart>
                <Pie
 isAnimationActive={false}
                  data={data.categories}
                  dataKey="revenue"
                  nameKey="category"
                  innerRadius={62}
                  outerRadius={84}
                  paddingAngle={3}
                  stroke="none"
                >
                  {data.categories.map((_: Row, i: number) => (
                    <Cell key={i} fill={palette[i % palette.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(v) => money(Number(v))} />
              </PieChart>
            </ResponsiveContainer>
            <div className="donut-center">
              <strong>{data.categories.length}</strong>
              <small>categories</small>
            </div>
          </div>
          <div className="category-legend">
            {data.categories.map((r: Row, i: number) => (
              <div key={r.category}>
                <span>
                  <i style={{ background: palette[i % palette.length] }} />
                  {r.category}
                </span>
                <strong>
                  {m.revenue ? Math.round((r.revenue / m.revenue) * 100) : 0}%
                </strong>
              </div>
            ))}
          </div>
        </Panel>
      </div>
      <div className="inventory-summary">
        <div>
          <span className="mini-icon amber">
            <Boxes size={19} />
          </span>
          <div>
            <small>Low-stock positions</small>
            <strong>
              {num(m.low_stock)} <Badge tone="amber">Needs attention</Badge>
            </strong>
          </div>
        </div>
        <div>
          <span className="mini-icon green">
            <Clock3 size={19} />
          </span>
          <div>
            <small>Stock cover</small>
            <strong>
              {m.cover_days === null
                ? "No demand"
                : `${num(m.cover_days)} days`}
            </strong>
          </div>
        </div>
        <div>
          <span className="mini-icon blue">
            <TrendingUp size={19} />
          </span>
          <div>
            <small>Sell-through</small>
            <strong>{num(m.sell_through)}%</strong>
          </div>
        </div>
        <div>
          <span className="mini-icon peach">
            <Wallet size={19} />
          </span>
          <div>
            <small>Dead-stock value</small>
            <strong>{compactMoney(m.dead_stock_value)}</strong>
          </div>
        </div>
        <Link
          to="/app/inventory"
          className="icon-btn"
          aria-label="View inventory details"
        >
          <ArrowUpRight size={19} />
        </Link>
      </div>
      <div className="bottom-grid">
        <Panel
          title="Store performance"
          sub="Your strongest locations, by net revenue"
          aside={
            <Link className="text-link" to="/app/sales">
              View analytics <ArrowUpRight size={14} />
            </Link>
          }
        >
          <DataTable
            rows={data.stores.slice(0, 5)}
            search={false}
            columns={[
              {
                key: "store",
                label: "Store",
                render: (v, r) => (
                  <div className="store-cell">
                    <span className="store-icon">
                      <LayoutDashboard size={15} />
                    </span>
                    <div>
                      <strong>{v}</strong>
                      <small>{r.units.toLocaleString("en-IN")} net units</small>
                    </div>
                  </div>
                ),
              },
              {
                key: "revenue",
                label: "Revenue",
                render: (v) => <strong>{money(v)}</strong>,
              },
              {
                key: "cogs",
                label: "Gross margin",
                render: (_, r) => (
                  <span className="margin-cell">
                    {num(
                      r.revenue ? ((r.revenue - r.cogs) / r.revenue) * 100 : 0,
                    )}
                    %{" "}
                    <span>
                      <i
                        style={{
                          width: `${Math.max(0, Math.min(100, ((r.revenue - r.cogs) / r.revenue) * 100))}%`,
                        }}
                      />
                    </span>
                  </span>
                ),
              },
            ]}
            pageSize={5}
          />
        </Panel>
        <Panel
          title="Operations, in motion"
          sub="Recent workflow activity"
          aside={<span className="live-dot" />}
        >
          {activity.data?.length ? (
            <div className="activity-list">
              {activity.data.slice(0, 4).map((r) => (
                <div key={r.id}>
                  <span className="activity-icon">
                    <Zap size={16} />
                  </span>
                  <div>
                    <strong>{r.kind.replaceAll("-", " ")}</strong>
                    <small>
                      {new Date(r.created_at).toLocaleString("en-IN")}
                    </small>
                  </div>
                  <Status value={r.status} />
                </div>
              ))}
            </div>
          ) : (
            <div className="activity-empty">
              <span className="mini-icon green">
                <Zap size={22} />
              </span>
              <h4>Your next automation starts here</h4>
              <p>Generate your daily MIS or run a stock check in one step.</p>
              <Link className="text-link" to="/app/workflows">
                Explore automations <ArrowRight size={14} />
              </Link>
            </div>
          )}
          <Link className="panel-bottom-link" to="/app/audit">
            View all workspace activity <ArrowRight size={14} />
          </Link>
        </Panel>
      </div>
      <details className="definitions">
        <summary>
          <CircleHelp size={15} /> How these numbers are calculated
        </summary>
        <p>
          Gross profit = net revenue − signed cost of goods sold. Stock cover =
          available stock ÷ trailing 30-day average positive unit sales.
          Sell-through = positive net units sold ÷ (positive net units sold +
          ending stock). Dead stock = positive stock with no sale for the
          configured inactivity period (default 90 days). Every low-stock count
          represents a store–SKU position. Snapshot:{" "}
          {data.inventory_as_of ?? "Unavailable"}.
        </p>
      </details>
    </>
  );
}

function Sales({
  data,
  loading,
  error,
}: {
  data?: Row;
  loading: boolean;
  error: unknown;
}) {
  if (loading) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  if (!data) return <Empty />;
  return (
    <>
      <div className="kpi-grid three">
        <KPI
          label="Net revenue"
          value={money(data.metrics.revenue)}
          note="Selected reporting period"
          icon={<Wallet size={18} />}
          accent
          definition="Sum of signed net transaction revenue."
        />
        <KPI
          label="Gross profit"
          value={money(data.metrics.gross_profit)}
          note={`${num(data.metrics.margin)}% gross margin`}
          icon={<TrendingUp size={18} />}
          definition="Revenue less cost of goods sold."
        />
        <KPI
          label="Net units sold"
          value={num(data.metrics.units)}
          note="Sales less returned units"
          icon={<Package size={18} />}
          definition="Signed quantity sum."
        />
      </div>
      <Panel title="Revenue over time" sub="Returns and discounts are included">
        <RevenueChart data={data.trend} />
      </Panel>
      <div className="two-col">
        <Panel title="Store comparison">
          <div className="chart">
            <ResponsiveContainer>
              <BarChart
                data={data.stores}
                layout="vertical"
                margin={{ left: 15, right: 20 }}
              >
                <CartesianGrid horizontal={false} stroke="#edf0eb" />
                <XAxis
                  type="number"
                  tickFormatter={compactMoney}
                  tick={{ fontSize: 10 }}
                />
                <YAxis
                  type="category"
                  dataKey="store"
                  width={130}
                  tick={{ fontSize: 10 }}
                />
                <Tooltip formatter={(v) => money(Number(v))} />
                <Bar isAnimationActive={false} dataKey="revenue" fill="#3e876e" radius={[0, 3, 3, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>
        <Panel title="Category performance">
          <DataTable
            rows={data.categories}
            columns={[
              { key: "category" },
              { key: "revenue", render: (v) => money(v) },
              { key: "units" },
            ]}
          />
        </Panel>
      </div>
      <Panel title="Top products" sub="Ranked by selected-period revenue">
        <DataTable
          rows={data.products}
          columns={[
            { key: "sku", label: "SKU" },
            { key: "product" },
            { key: "brand" },
            { key: "category" },
            { key: "units" },
            { key: "revenue", render: (v) => money(v) },
          ]}
        />
      </Panel>
    </>
  );
}

function Status({ value }: { value: string }) {
  return (
    <Badge
      tone={
        ["Completed", "Approved", "Healthy", "Imported"].includes(value)
          ? "green"
          : ["Failed", "Critical", "Rejected", "Dead stock"].includes(value)
            ? "red"
            : ["Awaiting Approval", "Low stock", "Review"].includes(value)
              ? "amber"
              : "neutral"
      }
    >
      {value}
    </Badge>
  );
}
function Inventory({ filters, act, busy }: { filters: Filters } & ActionProps) {
  const [tab, setTab] = useState("Recommendations");
  const [selected, setSelected] = useState<Row | null>(null);
  const inventory = useQuery({
    queryKey: ["inventory", filters],
    queryFn: () => api<Row[]>("/inventory?" + params(filters)),
  });
  const recs = useQuery({
    queryKey: ["recommendations"],
    queryFn: () => api<Row[]>("/recommendations"),
  });
  const rows =
    tab === "Recommendations"
      ? (recs.data ?? []).filter(
          (r) =>
            (!filters.store_id || r.store_id === filters.store_id) &&
            (!filters.category_id || r.category_id === filters.category_id) &&
            (!filters.brand_id || r.brand_id === filters.brand_id) &&
            (!filters.sku_id || r.sku_id === filters.sku_id),
        )
      : tab === "All stock"
        ? (inventory.data ?? [])
        : (inventory.data ?? []).filter((r) =>
            tab === "High demand"
              ? r.high_demand
              : tab === "Ageing"
                ? r.ageing
                : r.classification === tab,
          );
  return (
    <>
      <div className="info-banner">
        <ShieldCheck size={18} />
        <span>
          Explainable stock planning. Demand × lead time + safety stock −
          available stock − confirmed inbound, rounded to supplier packs.
          Purchase drafts require manager approval.
        </span>
      </div>
      <div className="tabs">
        {[
          "Recommendations",
          "All stock",
          "Low stock",
          "Dead stock",
          "Overstock",
          "Slow moving",
          "High demand",
          "Ageing",
        ].map((t) => (
          <button
            className={tab === t ? "active" : ""}
            onClick={() => setTab(t)}
            key={t}
          >
            {t}
          </button>
        ))}
      </div>
      <Panel
        title={tab}
        sub={
          tab === "Recommendations"
            ? "Suggestions based on 18 October 2026; your product and store filters apply. Open an item to inspect the calculation."
            : "Latest snapshot per store and SKU within your filters."
        }
        aside={<Badge>{num(rows.length)} positions</Badge>}
      >
        {inventory.isLoading || recs.isLoading ? (
          <Loading />
        ) : inventory.error || recs.error ? (
          <ErrorBox error={inventory.error || recs.error} />
        ) : (
          <DataTable
            rows={rows}
            columns={
              tab === "Recommendations"
                ? [
                    {
                      key: "sku",
                      label: "Product / SKU",
                      render: (v, r) => (
                        <div className="product-cell">
                          <strong>{r.product}</strong>
                          <small>{v}</small>
                        </div>
                      ),
                    },
                    { key: "store" },
                    { key: "severity", render: (v) => <Status value={v} /> },
                    { key: "quantity", label: "Reorder units" },
                    {
                      key: "cost",
                      label: "Est. purchase cost",
                      render: (v) => money(v),
                    },
                    { key: "status", render: (v) => <Status value={v} /> },
                    {
                      key: "id",
                      label: "",
                      render: (_, r) => (
                        <button
                          className="btn small"
                          onClick={() => setSelected(r)}
                        >
                          Review <ArrowUpRight size={13} />
                        </button>
                      ),
                    },
                  ]
                : [
                    { key: "sku", label: "SKU" },
                    { key: "store" },
                    { key: "quantity", label: "On hand" },
                    { key: "available" },
                    {
                      key: "cover_days",
                      render: (v) => (v === null ? "No demand" : `${num(v)} d`),
                    },
                    { key: "value", render: (v) => money(v) },
                    { key: "age_days", label: "Receipt age (days)" },
                    { key: "inactive_days", label: "Inactive days" },
                    {
                      key: "classification",
                      render: (v) => <Status value={v} />,
                    },
                  ]
            }
          />
        )}
      </Panel>
      {selected && (
        <div className="modal-backdrop" onClick={() => setSelected(null)}>
          <FocusDialog onClose={() => setSelected(null)}>
            <div className="modal-title">
              <span className="mini-icon green">
                <Boxes size={22} />
              </span>
              <button
                className="icon-btn"
                aria-label="Close details"
                onClick={() => setSelected(null)}
              >
                <X size={20} />
              </button>
            </div>
            <div className="eyebrow">CALCULATED REORDER RECOMMENDATION</div>
            <h2>{selected.product}</h2>
            <p className="muted">
              {selected.sku} · {selected.store}
            </p>
            <div className="decision-value">
              <strong>{selected.quantity} units</strong>
              <span>{money(selected.cost)} estimated cost</span>
            </div>
            <h4>Why this recommendation?</h4>
            <p className="rationale">{selected.rationale}</p>
            <DataTable
              search={false}
              rows={Object.entries(selected.evidence).map(
                ([metric, value]) => ({
                  metric: metric.replaceAll("_", " "),
                  value,
                }),
              )}
              pageSize={12}
            />
            <div className="modal-actions">
              <button className="btn" onClick={() => setSelected(null)}>
                Close
              </button>
              <button
                className="btn primary"
                disabled={busy || selected.status !== "Suggested"}
                onClick={() =>
                  act(async () => {
                    await api(`/recommendations/${selected.id}/submit`, {
                      method: "POST",
                    });
                    setSelected(null);
                  }, "Recommendation submitted for manager approval.")
                }
              >
                Submit for approval <ArrowRight size={15} />
              </button>
            </div>
          </FocusDialog>
        </div>
      )}
    </>
  );
}

function Forecast({ filters }: { filters: Filters }) {
  const [horizon, setHorizon] = useState(30);
  const f = { ...filters, start: "2025-10-19" };
  const query = useQuery({
    queryKey: ["forecast", f, horizon],
    queryFn: () => api("/forecasts?" + params(f) + "&horizon=" + horizon),
  });
  return (
    <>
      <div className="info-banner">
        <TrendingUp size={18} />
        <span>
          Four practical baselines. Three rolling holdouts. Selection by
          validation MAE. Full available history through your end date;
          zero-sale days remain in the series.
        </span>
      </div>
      <Panel
        title="A measured look ahead"
        sub="Daily demand · positive sales units"
        aside={
          <select
            aria-label="Forecast horizon"
            value={horizon}
            onChange={(e) => setHorizon(Number(e.target.value))}
          >
            <option value={7}>Next 7 days</option>
            <option value={30}>Next 30 days</option>
          </select>
        }
      >
        {query.isLoading ? (
          <Loading />
        ) : query.error ? (
          <ErrorBox error={query.error} />
        ) : (
          <>
            <div className="forecast-heading">
              <div>
                <span className="muted">Forecast demand</span>
                <h2>
                  {num(query.data.forecast_total)} <small>units</small>
                </h2>
              </div>
              <Badge tone="green">Selected: {query.data.model}</Badge>
            </div>
            <div className="chart tall">
              <ResponsiveContainer>
                <AreaChart
                  data={[...query.data.history, ...query.data.forecast]}
                >
                  <CartesianGrid vertical={false} stroke="#edf0eb" />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 10 }}
                    minTickGap={60}
                  />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Legend />
                  <Area
 isAnimationActive={false}
                    dataKey="actual"
                    name="Actual demand"
                    stroke="#6b8075"
                    fill="#eef2ee"
                  />
                  <Area
 isAnimationActive={false}
                    dataKey="selected"
                    name="Selected forecast"
                    stroke="#26795e"
                    fill="#e3f0e9"
                    strokeWidth={2}
                  />
                  <Area
 isAnimationActive={false}
                    dataKey="baseline"
                    name="Naive baseline"
                    stroke="#c39853"
                    strokeDasharray="5 4"
                    fill="transparent"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
            <p className="footnote">{query.data.uncertainty}</p>
          </>
        )}
      </Panel>
      {query.data && (
        <div className="two-col">
          <Panel
            title="Rolling backtest results"
            sub="MAE in units/day · WAPE in percent"
          >
            <DataTable rows={query.data.backtests} search={false} />
          </Panel>
          <Panel title="What the forecast means">
            <div className="prose">
              <Badge>Baselines v1</Badge>
              <p>{query.data.explanation}</p>
              <p>{query.data.validation}</p>
              <p>
                Sparse SKU/store demand can be volatile. Select a category or
                all stores for more stable aggregate planning. No probabilistic
                confidence interval is claimed.
              </p>
            </div>
          </Panel>
        </div>
      )}
    </>
  );
}

function Imports({ act, busy }: ActionProps) {
  const [batch, setBatch] = useState<Row | null>(null);
  const [kind, setKind] = useState("sales");
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const history = useQuery({
    queryKey: ["imports"],
    queryFn: () => api<Row[]>("/imports"),
  });
  const upload = (file: File) =>
    act(async () => {
      const form = new FormData();
      form.append("file", file);
      const b = await api("/imports/preview?kind=" + kind, {
        method: "POST",
        body: form,
      });
      setBatch(b);
      setMapping(b.mapping);
    }, "Spreadsheet preview ready. Review your mappings and validation results.");
  return (
    <>
      <ol className="import-stepper" aria-label="Import progress">
        {['Upload file', 'Map columns', 'Review validation', 'Import accepted rows'].map((label, index) => (
          <li key={label} className={(batch ? (batch.status === 'Imported' ? 3 : 2) : 0) >= index ? 'active' : ''}>
            <span>{index + 1}</span><strong>{label}</strong>
          </li>
        ))}
      </ol>
      <div className="two-col import-layout">
        <Panel
          title="Bring your data together"
          sub="Upload, inspect, then import. You're in control."
        >
          <div className="import-kind">
            <label>
              Dataset type
              <select
                aria-label="Dataset type"
                value={kind}
                onChange={(e) => setKind(e.target.value)}
              >
                <option value="sales">Sales transactions</option>
                <option value="inventory">Inventory snapshots</option>
              </select>
            </label>
            <Badge>XLSX · CSV</Badge>
          </div>
          <label
            className={`dropzone ${busy ? "disabled" : ""}`}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              if (!busy && e.dataTransfer.files[0])
                void upload(e.dataTransfer.files[0]);
            }}
          >
            <input
              type="file"
              aria-label="Upload spreadsheet"
              accept=".xlsx,.csv"
              disabled={busy}
              onChange={(e) => {
                if (e.target.files?.[0]) void upload(e.target.files[0]);
                e.target.value = "";
              }}
            />
            <span className="upload-icon">
              {busy ? (
                <Loader2 className="spin" size={28} />
              ) : (
                <UploadCloud size={28} />
              )}
            </span>
            <strong>Drop your spreadsheet here</strong>
            <span>
              or <em>browse files</em> to get started
            </span>
            <small>Up to 8 MB · 20,000 rows · multiple XLSX sheets</small>
          </label>
          <div className="import-assurance">
            <ShieldCheck size={16} />
            <span>
              Files stay in this workspace. Nothing is sent to an LLM.
            </span>
          </div>
        </Panel>
        <Panel title="A clean start" sub="Try the included sample files">
          <div className="template-list">
            <a href={sampleUrl("sales_import.xlsx")} download>
              <span className="mini-icon green">
                <FileSpreadsheet size={22} />
              </span>
              <div>
                <strong>Sales import sample</strong>
                <small>Valid rows + intentional validation examples</small>
              </div>
              <ArrowDownToLine size={17} />
            </a>
            <a href={sampleUrl("inventory_import.xlsx")} download>
              <span className="mini-icon blue">
                <Boxes size={22} />
              </span>
              <div>
                <strong>Inventory import sample</strong>
                <small>Stock, reservations & receipt dates</small>
              </div>
              <ArrowDownToLine size={17} />
            </a>
            <a href={sampleUrl("sales_template.csv")} download>
              <span className="mini-icon amber">
                <FileSpreadsheet size={22} />
              </span>
              <div>
                <strong>Sales CSV template</strong>
                <small>Canonical column names, ready to edit</small>
              </div>
              <ArrowDownToLine size={17} />
            </a>
          </div>
          <p className="footnote">
            Missing discount and reserved values become zero. Required dates,
            quantities, stores and SKUs are never guessed. Dates: YYYY-MM-DD or
            DD/MM/YYYY.
          </p>
        </Panel>
      </div>
      {batch && (
        <Panel
          title={`Review: ${batch.filename}`}
          sub="Only accepted rows will be committed. Rejected rows remain available for review."
          aside={
            <div className="inline">
              <Badge tone="green">{batch.accepted} accepted</Badge>
              <Badge tone={batch.rejected ? "red" : "neutral"}>
                {batch.rejected} rejected
              </Badge>
              <Status value={batch.status} />
            </div>
          }
        >
          <div className="mapping-grid">
            {batch.columns.map((column: string) => (
              <label key={column}>
                {column}
                <select
                  aria-label={`Map ${column}`}
                  value={mapping[column] ?? ""}
                  disabled={batch.status === "Imported"}
                  onChange={(e) =>
                    setMapping({ ...mapping, [column]: e.target.value })
                  }
                >
                  <option value="">Ignore column</option>
                  {(kind === "sales"
                    ? [
                        "transaction_id",
                        "date",
                        "store",
                        "sku",
                        "quantity",
                        "unit_price",
                        "discount",
                      ]
                    : [
                        "date",
                        "store",
                        "sku",
                        "quantity",
                        "reserved",
                        "received_date",
                      ]
                  ).map((v) => (
                    <option key={v} value={v}>
                      {v}
                    </option>
                  ))}
                </select>
              </label>
            ))}
          </div>
          <div className="toolbar">
            <button
              className="btn"
              disabled={busy || batch.status === "Imported"}
              onClick={() =>
                act(async () => {
                  setBatch(
                    await api(`/imports/${batch.id}/validate`, {
                      method: "POST",
                      body: JSON.stringify({ mapping }),
                    }),
                  );
                }, "Mappings validated.")
              }
            >
              Validate mappings
            </button>
            <button
              className="btn primary"
              disabled={busy || !batch.accepted || batch.status === "Imported"}
              onClick={() =>
                act(async () => {
                  const r = await api(`/imports/${batch.id}/commit`, {
                    method: "POST",
                  });
                  setBatch({ ...batch, ...r });
                }, "Accepted rows imported. Analytics refreshed and reporting workflow queued.")
              }
            >
              <Check size={16} /> Import accepted rows
            </button>
            <button
              className="btn ghost"
              onClick={() =>
                act(
                  () =>
                    fileDownload(
                      `/imports/${batch.id}/errors.xlsx`,
                      "validation-errors.xlsx",
                    ),
                  "Validation report downloaded.",
                )
              }
            >
              <ArrowDownToLine size={15} /> Error report
            </button>
          </div>
          <h4 className="inset-heading">Source preview</h4>
          <DataTable
            rows={batch.preview.map((r: Row) => ({
              sheet: r.sheet,
              row: r.row,
              ...r.values,
            }))}
            pageSize={5}
          />
          {batch.errors?.length > 0 && (
            <>
              <h4 className="inset-heading red-text">Validation feedback</h4>
              <DataTable
                rows={batch.errors}
                columns={[{ key: "sheet" }, { key: "row" }, { key: "message" }]}
              />
            </>
          )}
        </Panel>
      )}
      <Panel
        title="Import history"
        sub="Content fingerprints prevent repeated file imports"
      >
        {history.isLoading ? (
          <Loading />
        ) : (
          <DataTable
            rows={history.data ?? []}
            columns={[
              { key: "filename" },
              { key: "kind", label: "Dataset" },
              { key: "accepted" },
              { key: "rejected" },
              { key: "status", render: (v) => <Status value={v} /> },
              {
                key: "created_at",
                label: "Uploaded",
                render: (v) => new Date(v).toLocaleString("en-IN"),
              },
              {
                key: "id",
                label: "",
                render: (v) => (
                  <button
                    className="btn small"
                    onClick={() =>
                      act(async () => {
                        const b = await api("/imports/" + v);
                        setBatch(b);
                        setMapping(b.mapping);
                        setKind(b.kind);
                      }, "Import opened for review.")
                    }
                  >
                    Review batch
                  </button>
                ),
              },
            ]}
          />
        )}
      </Panel>
    </>
  );
}

function Reports({ filters, act, busy }: { filters: Filters } & ActionProps) {
  const [kind, setKind] = useState(reportTypes[0]);
  const history = useQuery({
    queryKey: ["reports"],
    queryFn: () => api<Row[]>("/reports"),
  });
  return (
    <>
      <div className="report-catalog" aria-label="Report catalog">
        {reportTypes.map((report) => <button key={report} className={`report-option ${kind === report ? 'selected' : ''}`} onClick={() => setKind(report)} aria-pressed={kind === report}>
          <FileSpreadsheet size={20}/><div><span>{report}</span><small>Excel & PDF ? saved to this workspace</small></div>
        </button>)}
      </div>
      <div className="two-col">
        <Panel
          title="Build a dependable MIS"
          sub="Every export uses the same calculation service as your dashboard."
        >
          <div className="report-builder">
            <label>
              Report type
              <select
                aria-label="Report type"
                value={kind}
                onChange={(e) => setKind(e.target.value)}
              >
                {reportTypes.map((t) => (
                  <option key={t}>{t}</option>
                ))}
              </select>
            </label>
            <div className="report-description">
              <FileSpreadsheet size={35} />
              <div>
                <h3>{kind}</h3>
                <p>
                  Period: {filters.start.split("-").reverse().join("/")} –{" "}
                  {filters.end.split("-").reverse().join("/")}
                  <br />
                  Your current store, category, brand and SKU filters apply.
                </p>
              </div>
            </div>
            <button
              className="btn primary"
              disabled={busy}
              onClick={() =>
                act(
                  () =>
                    api("/reports", {
                      method: "POST",
                      body: JSON.stringify({ kind, filters }),
                    }),
                  "MIS report generated and saved. Download Excel or PDF below.",
                )
              }
            >
              <Plus size={16} /> Generate report
            </button>
          </div>
        </Panel>
        <Panel title="Ready for the next conversation">
          <div className="prose report-benefits">
            <div>
              <CheckCircle2 />
              <span>
                <strong>Real database calculations</strong>
                <small>No hardcoded business figures.</small>
              </span>
            </div>
            <div>
              <CheckCircle2 />
              <span>
                <strong>Formatted Excel workbooks</strong>
                <small>
                  Filters, frozen headers, totals and metric summary.
                </small>
              </span>
            </div>
            <div>
              <CheckCircle2 />
              <span>
                <strong>Snapshot exports</strong>
                <small>
                  Saved results stay reproducible after new imports.
                </small>
              </span>
            </div>
            <div>
              <CheckCircle2 />
              <span>
                <strong>PDF management briefs</strong>
                <small>Key metrics and readable supporting tables.</small>
              </span>
            </div>
          </div>
        </Panel>
      </div>
      <Panel
        title="Generated reports"
        sub="Saved calculations, available in XLSX and PDF"
      >
        {history.isLoading ? (
          <Loading />
        ) : history.error ? (
          <ErrorBox error={history.error} />
        ) : (
          <DataTable
            rows={history.data ?? []}
            columns={[
              { key: "kind", label: "Report" },
              {
                key: "created_at",
                label: "Generated",
                render: (v) => new Date(v).toLocaleString("en-IN"),
              },
              {
                key: "filters",
                label: "Period",
                render: (v) => `${v.start} → ${v.end}`,
              },
              {
                key: "metrics",
                label: "Net revenue",
                render: (v) => money(v.revenue),
              },
              {
                key: "id",
                label: "Download",
                render: (v) => (
                  <div className="inline">
                    {["xlsx", "pdf"].map((format) => (
                      <button
                        className="btn small"
                        key={format}
                        onClick={() =>
                          act(
                            () =>
                              fileDownload(
                                `/reports/${v}/download?format=${format}`,
                                `retailpilot-${v}.${format}`,
                              ),
                            `${format.toUpperCase()} downloaded.`,
                          )
                        }
                      >
                        <ArrowDownToLine size={13} />
                        {format.toUpperCase()}
                      </button>
                    ))}
                  </div>
                ),
              },
            ]}
          />
        )}
      </Panel>
    </>
  );
}

function Analyst({ filters }: { filters: Filters }) {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<Row | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const ask = async (q: string) => {
    setQuestion(q);
    setBusy(true);
    setError("");
    try {
      setResult(
        await api("/analyst/query", {
          method: "POST",
          body: JSON.stringify({ question: q, filters }),
        }),
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <div className="analyst-hero">
        <span className="analyst-icon">
          <Sparkles size={29} />
        </span>
        <Badge tone="green">Deterministic analytics · no LLM required</Badge>
        <h2>Less searching. More understanding.</h2>
        <p>
          Ask a supported question. Get a calculated answer, with the evidence
          in view.
        </p>
        <form
          className="analyst-input"
          onSubmit={(e) => {
            e.preventDefault();
            void ask(question);
          }}
        >
          <input
            aria-label="Business question"
            placeholder="What would you like to understand about your business?"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            maxLength={500}
            required
            minLength={3}
          />
          <button
            aria-label="Ask analyst"
            disabled={busy}
            className="btn primary"
          >
            {busy ? (
              <Loader2 className="spin" size={18} />
            ) : (
              <ArrowRight size={18} />
            )}
          </button>
        </form>
        <div className="question-grid">
          {questions.map((q, i) => (
            <button disabled={busy} onClick={() => void ask(q)} key={q}>
              <span>{["01", "02", "03", "04", "05", "06"][i]}</span>
              {q}
              <ArrowUpRight size={15} />
            </button>
          ))}
        </div>
      </div>
      {error && <ErrorBox error={new Error(error)} />}
      {result && (
        <Panel
          title="Your answer, with the workings"
          sub={result.mode}
          aside={
            <Badge tone="green">
              <ShieldCheck size={12} /> Validated data tools
            </Badge>
          }
        >
          <div className="analyst-explanation">
            <h3>{question}</h3>
            <p>{result.explanation}</p>
            <span className="muted">
              Reporting period: {result.filters.start} → {result.filters.end} ·
              Tool: {result.tool} · {result.data_label}
            </span>
          </div>
          <DataTable rows={result.rows} />
          <div className="footnote">
            Read-only analysis. No unconstrained SQL. No purchasing or inventory
            changes are permitted through the analyst.
          </div>
        </Panel>
      )}
    </>
  );
}

function Workflows({ act, busy }: ActionProps) {
  const query = useQuery({
    queryKey: ["workflows"],
    queryFn: () => api<Row[]>("/workflows"),
    refetchInterval: 5000,
  });
  return (
    <>
      <div className="workflow-summary">
        {['Completed', 'Running', 'Queued', 'Failed'].map((status) => <div key={status}><span>{status}</span><strong>{query.data?.filter((row) => row.status === status).length ?? 0}</strong><small>Saved workflow runs</small></div>)}
      </div>
      <div className="workflow-grid">
        {[
          [
            "daily-report",
            "Daily sales reporting",
            "Calculate metrics → build MIS → save report",
            FileSpreadsheet,
          ],
          [
            "low-stock",
            "Low-stock detection",
            "Review stock cover → calculate → suggest reorder",
            Boxes,
          ],
          [
            "weekly-mis",
            "Weekly management MIS",
            "Compare periods → generate → save summary",
            BarChart3,
          ],
        ].map(([kind, title, text, Icon]) => {
          const I = Icon as typeof Boxes;
          return (
            <section className="workflow-card" key={String(kind)}>
              <span className="mini-icon green">
                <I size={22} />
              </span>
              <Badge>On demand / import trigger</Badge>
              <h3>{String(title)}</h3>
              <p>{String(text)}</p>
              <button
                className="btn"
                disabled={busy}
                onClick={() =>
                  act(
                    () =>
                      api("/workflows", {
                        method: "POST",
                        body: JSON.stringify({
                          kind,
                          key: `manual:${kind}:${crypto.randomUUID()}`,
                        }),
                      }),
                    "Workflow queued. Execution history updates automatically.",
                  )
                }
              >
                <Zap size={15} /> Run workflow
              </button>
            </section>
          );
        })}
      </div>
      <div className="info-banner">
        <Clock3 size={18} />
        <span>
          Import triggers run automatically. Scheduled runs can use the supplied
          CLI with your OS scheduler. Timestamps are stored in UTC and shown in
          your browser timezone. Failed jobs allow up to three attempts.
        </span>
      </div>
      <Panel
        title="Execution history"
        sub="Durable state changes, idempotency keys and error details"
      >
        {query.isLoading ? (
          <Loading />
        ) : query.error ? (
          <ErrorBox error={query.error} />
        ) : (
          <DataTable
            rows={query.data ?? []}
            columns={[
              { key: "id", label: "Run" },
              { key: "kind", label: "Workflow" },
              { key: "status", render: (v) => <Status value={v} /> },
              { key: "attempts" },
              { key: "result", render: (v) => JSON.stringify(v) },
              { key: "error" },
              {
                key: "id",
                label: "Recovery",
                render: (_, r) =>
                  r.status === "Failed" ? (
                    <div className="inline">
                      <button
                        className="btn small"
                        disabled={busy || r.attempts >= 3}
                        onClick={() =>
                          act(
                            () =>
                              api(`/workflows/${r.id}/retry`, {
                                method: "POST",
                              }),
                            "Retry queued.",
                          )
                        }
                      >
                        Retry
                      </button>
                      <button
                        className="btn small"
                        disabled={busy}
                        onClick={() =>
                          act(
                            () =>
                              api(`/workflows/${r.id}/cancel`, {
                                method: "POST",
                              }),
                            "Workflow cancelled.",
                          )
                        }
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    "—"
                  ),
              },
            ]}
          />
        )}
      </Panel>
    </>
  );
}

function Approvals({ manager, act, busy }: { manager: boolean } & ActionProps) {
  const query = useQuery({
    queryKey: ["approvals"],
    queryFn: () => api<Row[]>("/approvals"),
  });
  const orders = useQuery({
    queryKey: ["orders"],
    queryFn: () => api<Row[]>("/purchase-orders"),
  });
  const [reasons, setReasons] = useState<Record<number, string>>({});
  return (
    <>
      <div className="info-banner">
        <ShieldCheck size={19} />
        <span>
          {manager
            ? "You are reviewing as Demo manager."
            : "You are a Demo analyst. Switch to Demo manager to review a request."}{" "}
          All approved actions create simulated draft orders only.
        </span>
        {!manager && (
          <button
            className="btn small"
            disabled={busy}
            onClick={() =>
              act(async () => {
                const r = await api("/demo/role", { method: "POST" });
                localStorage.setItem("rp-token", r.access_token);
              }, "Switched to Demo manager.")
            }
          >
            Use demo manager
          </button>
        )}
      </div>
      {query.isLoading ? (
        <Loading />
      ) : query.error ? (
        <ErrorBox error={query.error} />
      ) : !query.data?.length ? (
        <Panel title="A considered decision starts with evidence">
          <Empty
            title="Nothing awaiting your review"
            text="Open Inventory Intelligence and submit a calculated reorder recommendation."
            action={
              <Link to="/app/inventory" className="btn primary">
                Review recommendations <ArrowRight size={15} />
              </Link>
            }
          />
        </Panel>
      ) : (
        <div className="approval-list">
          {query.data.map((r) => (
            <section className="panel approval-card" key={r.id}>
              <div className="panel-head">
                <div>
                  <span className="eyebrow">
                    SIMULATED PURCHASE REQUEST #{r.id}
                  </span>
                  <h3>
                    {r.sku} · {r.store}
                  </h3>
                  <p>
                    Requested by actor #{r.requested_by} ·{" "}
                    {new Date(r.created_at).toLocaleString("en-IN")}
                  </p>
                </div>
                <Status value={r.status} />
              </div>
              <div className="approval-body">
                <div className="approval-amount">
                  <strong>{r.recommendation.quantity} units</strong>
                  <span>{money(r.recommendation.cost)} estimated cost</span>
                  <small>
                    Expected impact: restore supplier lead-time coverage plus
                    configured safety stock.
                  </small>
                </div>
                <div>
                  <h4>Business reasoning</h4>
                  <p>{r.recommendation.rationale}</p>
                  <p className="muted">
                    Available: {r.recommendation.evidence.available} · Daily
                    demand: {num(r.recommendation.evidence.daily_demand)} ·
                    Safety stock: {r.recommendation.evidence.safety_stock}
                  </p>
                </div>
              </div>
              {r.status === "Awaiting Approval" ? (
                <div className="approval-actions">
                  <input
                    aria-label={`Decision reason ${r.id}`}
                    placeholder="Record the reason for your decision (required)"
                    value={reasons[r.id] ?? ""}
                    onChange={(e) =>
                      setReasons({ ...reasons, [r.id]: e.target.value })
                    }
                  />
                  {["reject", "approve"].map((decision) => (
                    <button
                      className={`btn ${decision === "approve" ? "primary" : ""}`}
                      disabled={
                        busy ||
                        !manager ||
                        (reasons[r.id] ?? "").trim().length < 3
                      }
                      key={decision}
                      onClick={() =>
                        act(
                          () =>
                            api(`/approvals/${r.id}/decision`, {
                              method: "POST",
                              body: JSON.stringify({
                                decision,
                                reason: reasons[r.id],
                              }),
                            }),
                          decision === "approve"
                            ? "Approved. A simulated purchase draft was created."
                            : "Request rejected and reason recorded.",
                        )
                      }
                    >
                      {decision === "approve" ? (
                        <Check size={15} />
                      ) : (
                        <X size={15} />
                      )}{" "}
                      {decision === "approve" ? "Approve draft" : "Reject"}
                    </button>
                  ))}
                </div>
              ) : (
                <div className="approval-history">
                  Reviewed by actor #{r.reviewed_by} ·{" "}
                  {new Date(r.reviewed_at).toLocaleString("en-IN")}
                  <br />
                  <strong>Reason: </strong>
                  {r.reason}
                </div>
              )}
            </section>
          ))}
        </div>
      )}
      <Panel
        title="Simulated purchase drafts"
        sub="These orders do not reach suppliers or affect confirmed inbound stock."
      >
        <DataTable
          rows={orders.data ?? []}
          columns={[
            { key: "id", label: "Draft order" },
            { key: "approval_id", label: "Approval reference" },
            { key: "quantity" },
            { key: "cost", render: (v) => money(v) },
            { key: "status", render: (v) => <Badge>{v}</Badge> },
          ]}
        />
      </Panel>
    </>
  );
}

function Audit() {
  const query = useQuery({
    queryKey: ["audit"],
    queryFn: () => api<Row[]>("/audit"),
  });
  return (
    <Panel
      title="Workspace audit trail"
      sub="Most recent 250 events · generated by backend actions"
      aside={
        <Badge>
          <ShieldCheck size={12} /> Tenant scoped
        </Badge>
      }
    >
      {query.isLoading ? (
        <Loading />
      ) : query.error ? (
        <ErrorBox error={query.error} />
      ) : (
        <DataTable
          rows={query.data ?? []}
          columns={[
            {
              key: "created_at",
              label: "Timestamp",
              render: (v) => new Date(v).toLocaleString("en-IN"),
            },
            { key: "actor" },
            { key: "action", render: (v) => <code>{v}</code> },
            { key: "entity", label: "Reference" },
            {
              key: "detail",
              label: "Evidence",
              render: (v) => (
                <span className="audit-detail" title={JSON.stringify(v)}>
                  {JSON.stringify(v)}
                </span>
              ),
            },
          ]}
        />
      )}
    </Panel>
  );
}

function Integrations({ act, busy }: ActionProps) {
  const query = useQuery({
    queryKey: ["erp"],
    queryFn: () => api("/integrations/erp/status"),
  });
  return (
    <>
      <div className="section-intro">
        <Badge tone="green">HONEST BY DESIGN</Badge>
        <h2>A connected workflow starts with a dependable source.</h2>
        <p>
          Local ERP simulation demonstrates authenticated HTTP, pagination,
          validation and safe synchronization.
        </p>
      </div>
      <div className="integration-grid">
        <Panel
          title="Local ERP simulator"
          sub="Independent FastAPI service · fictional catalog"
          aside={
            <span className="mini-icon green">
              <Plug size={21} />
            </span>
          }
        >
          <div className="prose">
            <Status
              value={query.data?.connected ? "Completed" : "Not connected"}
            />
            <p>
              Fetch products, inventory and sales over HTTP. A sync creates a
              spreadsheet-style review batch. Inspect the mapping before
              committing.
            </p>
            {query.data && <p className="muted">{query.data.message}</p>}
            <div className="inline">
              <button
                className="btn"
                disabled={busy}
                onClick={() => void query.refetch()}
              >
                Test connection
              </button>
              <button
                className="btn primary"
                disabled={busy || !query.data?.connected}
                onClick={() =>
                  act(
                    () => api("/integrations/erp/sync", { method: "POST" }),
                    "ERP sales fetched into a review batch. Open the Data Import Center to inspect it.",
                  )
                }
              >
                Preview sales sync <ArrowRight size={14} />
              </button>
            </div>
          </div>
        </Panel>
        {["Tally", "Zoho", "Notifications"].map((name) => (
          <Panel key={name} title={name} sub="Future adapter">
            <div className="prose">
              <Badge>Not configured</Badge>
              <p>
                {name === "Notifications"
                  ? "External sending is disabled. No email or WhatsApp messages are sent."
                  : "No commercial credentials or verified commercial API connection. The provider interface is ready for a separately validated adapter."}
              </p>
            </div>
          </Panel>
        ))}
      </div>
    </>
  );
}

const settingsSchema = z.object({
  safety_days: z.coerce.number().int().min(0).max(60),
  dead_days: z.coerce.number().int().min(30).max(365),
  cover_days: z.coerce.number().int().min(1).max(90),
});
function SupplierSettings({
  manager,
  act,
  busy,
}: { manager: boolean } & ActionProps) {
  const query = useQuery({
    queryKey: ["suppliers"],
    queryFn: () => api<Row[]>("/suppliers"),
  });
  const [selected, setSelected] = useState<Row | null>(null);
  return (
    <Panel
      title="Supplier planning assumptions"
      sub="Lead times, minimum quantities and pack sizes feed the reorder formula."
    >
      {query.error ? (
        <ErrorBox error={query.error} />
      ) : (
        <DataTable
          search={false}
          rows={query.data ?? []}
          columns={[
            { key: "name", label: "Supplier" },
            { key: "lead_days", label: "Lead time (days)" },
            { key: "moq", label: "Minimum order" },
            { key: "pack_size", label: "Pack size" },
            {
              key: "id",
              label: "",
              render: (_, r) => (
                <button
                  className="btn small"
                  disabled={!manager}
                  onClick={() => setSelected({ ...r })}
                >
                  Edit assumptions
                </button>
              ),
            },
          ]}
        />
      )}
      {selected && (
        <form
          className="supplier-form"
          onSubmit={(e) => {
            e.preventDefault();
            void act(async () => {
              await api(`/suppliers/${selected.id}`, {
                method: "PATCH",
                body: JSON.stringify({
                  lead_days: selected.lead_days,
                  moq: selected.moq,
                  pack_size: selected.pack_size,
                }),
              });
              setSelected(null);
            }, "Supplier assumptions updated. Suggested reorders recalculated.");
          }}
        >
          <h4>{selected.name}</h4>
          {[
            ["lead_days", "Lead time (days)", 180],
            ["moq", "Minimum order quantity", 10000],
            ["pack_size", "Pack size", 1000],
          ].map(([key, label, max]) => (
            <label key={key}>
              {label}
              <input
                aria-label={String(label)}
                type="number"
                min={1}
                max={Number(max)}
                required
                value={selected[String(key)]}
                onChange={(e) =>
                  setSelected({ ...selected, [key]: Number(e.target.value) })
                }
              />
            </label>
          ))}
          <button className="btn primary" disabled={busy || !manager}>
            Save supplier
          </button>
          <button
            className="btn"
            type="button"
            onClick={() => setSelected(null)}
          >
            Cancel
          </button>
        </form>
      )}
    </Panel>
  );
}
function Settings({
  manager,
  act,
  busy,
  start,
}: { manager: boolean; start: () => void } & ActionProps) {
  const query = useQuery({
    queryKey: ["settings"],
    queryFn: () => api("/settings"),
  });
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<
    z.input<typeof settingsSchema>,
    unknown,
    z.output<typeof settingsSchema>
  >({ resolver: zodResolver(settingsSchema), values: query.data?.planning });
  return (
    <>
      <div className="two-col">
        <Panel
          title="Inventory planning rules"
          sub="Manager permissions required to update"
        >
          <form
            className="settings-form"
            onSubmit={handleSubmit((values) =>
              act(
                () =>
                  api("/settings", {
                    method: "PATCH",
                    body: JSON.stringify(values),
                  }),
                "Planning assumptions updated and unsubmitted suggestions recalculated.",
              ),
            )}
          >
            {[
              [
                "safety_days",
                "Safety stock (days)",
                "Additional demand coverage above supplier lead time.",
              ],
              [
                "dead_days",
                "Dead-stock inactivity (days)",
                "No positive sale for this period, with stock on hand.",
              ],
              [
                "cover_days",
                "Low-stock threshold (days)",
                "Positions below this coverage need review.",
              ],
            ].map(([key, label, hint]) => (
              <label key={key}>
                {label}
                <small>{hint}</small>
                <input
                  aria-label={label}
                  type="number"
                  disabled={!manager}
                  {...register(key as keyof z.input<typeof settingsSchema>)}
                />
                {errors[key as keyof typeof errors] && (
                  <span className="red-text">
                    {String(errors[key as keyof typeof errors]?.message)}
                  </span>
                )}
              </label>
            ))}
            <button className="btn primary" disabled={busy || !manager}>
              <Check size={15} /> Save planning rules
            </button>
          </form>
        </Panel>
        <Panel
          title="Demo workspace"
          sub="An isolated environment for fictional business data"
        >
          <div className="prose">
            <dl className="settings-details">
              <div>
                <dt>Currency</dt>
                <dd>Indian rupee · INR</dd>
              </div>
              <div>
                <dt>Reporting date</dt>
                <dd>18 October 2026</dd>
              </div>
              <div>
                <dt>Schedule timezone</dt>
                <dd>Asia/Kolkata</dd>
              </div>
              <div>
                <dt>Current role</dt>
                <dd>
                  <Badge tone="green">
                    Demo {manager ? "manager" : "analyst"}
                  </Badge>
                </dd>
              </div>
              <div>
                <dt>Analyst mode</dt>
                <dd>
                  {query.data?.llm_enabled
                    ? "Configured LLM tool selector"
                    : "Deterministic · no LLM"}
                </dd>
              </div>
            </dl>
            <button
              className="btn"
              disabled={busy}
              onClick={() =>
                act(async () => {
                  const r = await api("/demo/role", { method: "POST" });
                  localStorage.setItem("rp-token", r.access_token);
                }, "Demo role changed.")
              }
            >
              Switch to demo {manager ? "analyst" : "manager"}
            </button>
            <hr />
            <h4>Start fresh</h4>
            <p>
              Create a new empty workspace. Your previous demo remains isolated
              and is no longer selected.
            </p>
            <button className="btn" disabled={busy} onClick={start}>
              Create fresh demo session <ArrowRight size={14} />
            </button>
          </div>
        </Panel>
      </div>
      <SupplierSettings manager={manager} act={act} busy={busy} />
    </>
  );
}
