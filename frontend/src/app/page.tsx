import Link from "next/link";
import { Button } from "../../components/ui/Button";

// ── Icons (inline SVG to avoid extra deps) ──────────────────────────────────

function CheckIcon() {
  return (
    <svg className="w-5 h-5 text-green-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
    </svg>
  );
}

function ArrowRightIcon() {
  return (
    <svg className="w-4 h-4 ml-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
    </svg>
  );
}

// ── Data ─────────────────────────────────────────────────────────────────────

const features = [
  {
    icon: "🛒",
    title: "Retail POS & Inventory",
    description:
      "Lightning-fast point-of-sale with real-time stock tracking, barcode scanning, and automatic reorder alerts across all branches.",
  },
  {
    icon: "⛽",
    title: "Fuel Station Management",
    description:
      "Pump-level reconciliation, tank dip readings, nozzle tracking, and automated variance reports for fuel stations of any size.",
  },
  {
    icon: "📊",
    title: "Financial Accounting",
    description:
      "Double-entry bookkeeping enforced automatically. Every sale, purchase, and payroll run generates accurate journal entries instantly.",
  },
  {
    icon: "👥",
    title: "HR & Payroll",
    description:
      "Manage employees, shifts, leave, and payroll across multiple branches with statutory deductions calculated automatically.",
  },
  {
    icon: "🏢",
    title: "Multi-Branch Control",
    description:
      "Centralised dashboard for all your locations. Compare performance, transfer stock, and enforce policies from one place.",
  },
  {
    icon: "🔒",
    title: "Security & Audit Trails",
    description:
      "Role-based permissions, immutable audit logs, and HTTPS encryption keep your data safe and every action accountable.",
  },
];

const stats = [
  { value: "99.9%", label: "Uptime SLA" },
  { value: "< 200ms", label: "API Response" },
  { value: "Multi-tenant", label: "Architecture" },
  { value: "Offline-first", label: "PWA Support" },
];

const plans = [
  {
    name: "Starter",
    price: "$49",
    period: "/mo",
    description: "Perfect for a single shop or fuel station.",
    features: [
      "1 branch",
      "Up to 5 users",
      "POS & Inventory",
      "Basic reporting",
      "Email support",
    ],
    cta: "Start free trial",
    highlight: false,
  },
  {
    name: "Business",
    price: "$149",
    period: "/mo",
    description: "For growing businesses with multiple locations.",
    features: [
      "Up to 5 branches",
      "Up to 25 users",
      "All core modules",
      "Advanced analytics",
      "Priority support",
      "Offline sync",
    ],
    cta: "Start free trial",
    highlight: true,
  },
  {
    name: "Enterprise",
    price: "Custom",
    period: "",
    description: "Tailored for large multi-branch enterprises.",
    features: [
      "Unlimited branches",
      "Unlimited users",
      "All modules + API access",
      "Dedicated account manager",
      "SLA guarantee",
      "Custom integrations",
    ],
    cta: "Contact sales",
    highlight: false,
  },
];

const testimonials = [
  {
    quote:
      "Nexus transformed how we manage our 12 fuel stations. Reconciliation that used to take a full day now takes minutes.",
    author: "James Mwangi",
    role: "Operations Director, PetroLink Kenya",
    avatar: "JM",
  },
  {
    quote:
      "The offline-first capability is a game-changer. Our rural branches keep selling even when the internet goes down.",
    author: "Amina Hassan",
    role: "CEO, Savannah Retail Group",
    avatar: "AH",
  },
  {
    quote:
      "Finally, an ERP that doesn't require a six-month implementation. We were live in two weeks.",
    author: "David Ochieng",
    role: "CFO, Horizon Supermarkets",
    avatar: "DO",
  },
];

// ── Page ─────────────────────────────────────────────────────────────────────

export default function HomePage() {
  return (
    <div className="min-h-screen bg-white text-gray-900 antialiased">

      {/* ── Navbar ── */}
      <header className="border-b sticky top-0 bg-white/80 backdrop-blur-md z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
          {/* Logo */}
          <div className="flex items-center space-x-2">
            <div className="w-9 h-9 bg-black rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-lg">N</span>
            </div>
            <span className="font-bold text-xl tracking-tight">Nexus ERP</span>
          </div>

          {/* Nav links – hidden on mobile */}
          <nav className="hidden md:flex items-center gap-8 text-sm font-medium text-gray-600">
            <a href="#features" className="hover:text-black transition-colors">Features</a>
            <a href="#how-it-works" className="hover:text-black transition-colors">How it works</a>
            <a href="#pricing" className="hover:text-black transition-colors">Pricing</a>
            <a href="#testimonials" className="hover:text-black transition-colors">Testimonials</a>
          </nav>

          {/* Auth buttons */}
          <div className="flex items-center gap-3">
            <Link href="/auth/login">
              <Button variant="ghost" className="text-gray-600 hover:text-black font-medium hidden sm:inline-flex">
                Log in
              </Button>
            </Link>
            <Link href="/auth/register">
              <Button className="bg-black text-white hover:bg-zinc-800 rounded-lg px-5 shadow-sm transition-all active:scale-95">
                Get Started
              </Button>
            </Link>
          </div>
        </div>
      </header>

      {/* ── Hero ── */}
      <section className="relative min-h-[92vh] flex items-center justify-center overflow-hidden">
        {/* Background image */}
        <div
          className="absolute inset-0 z-0"
          style={{
            backgroundImage: "url('/office.jpeg')",
            backgroundSize: "cover",
            backgroundPosition: "center",
          }}
        />
        {/* Overlay */}
        <div className="absolute inset-0 bg-gradient-to-b from-black/70 via-black/60 to-black/80 z-0" />

        <div className="relative z-10 max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 text-center py-24">
          {/* Badge */}
          <span className="inline-flex items-center gap-2 bg-white/10 border border-white/20 text-white text-xs font-semibold px-4 py-1.5 rounded-full mb-8 backdrop-blur-sm">
            <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
            Now with offline-first PWA support
          </span>

          <h1 className="text-5xl sm:text-6xl md:text-7xl font-extrabold text-white tracking-tight leading-tight mb-6">
            The ERP Built for{" "}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-cyan-300">
              Real Business
            </span>
          </h1>

          <p className="text-lg sm:text-xl text-gray-300 max-w-2xl mx-auto mb-10 leading-relaxed">
            Nexus ERP unifies your retail, fuel, finance, and HR operations into
            one cloud-synchronized platform — online or offline, single branch
            or enterprise-wide.
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center mb-16">
            <Link href="/auth/register">
              <Button
                size="lg"
                className="px-10 h-14 text-base bg-white text-black hover:bg-slate-100 rounded-xl font-bold shadow-xl transition-all hover:-translate-y-0.5 active:translate-y-0 inline-flex items-center"
              >
                Start for free
                <ArrowRightIcon />
              </Button>
            </Link>
            <Link href="/auth/login">
              <Button
                size="lg"
                variant="outline"
                className="px-10 h-14 text-base text-white border-white/40 hover:border-white hover:bg-white/10 bg-transparent rounded-xl backdrop-blur-sm transition-all"
              >
                Schedule a Demo
              </Button>
            </Link>
          </div>

          {/* Social proof strip */}
          <p className="text-gray-400 text-sm">
            Trusted by <span className="text-white font-semibold">500+</span> businesses across East Africa
          </p>
        </div>
      </section>

      {/* ── Stats ── */}
      <section className="bg-black text-white py-14">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
          {stats.map((s) => (
            <div key={s.label}>
              <p className="text-3xl font-extrabold text-white mb-1">{s.value}</p>
              <p className="text-gray-400 text-sm font-medium">{s.label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Features ── */}
      <section id="features" className="py-24 bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <span className="text-blue-600 font-semibold text-sm uppercase tracking-widest">Platform</span>
            <h2 className="mt-2 text-4xl font-extrabold tracking-tight">Everything your business needs</h2>
            <p className="mt-4 text-gray-500 max-w-xl mx-auto text-lg">
              Six powerful modules, one unified platform. No integrations to maintain, no data silos.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-8">
            {features.map((f) => (
              <div
                key={f.title}
                className="bg-white rounded-2xl p-8 border border-gray-100 shadow-sm hover:shadow-md transition-shadow group"
              >
                <div className="text-4xl mb-4">{f.icon}</div>
                <h3 className="text-lg font-bold mb-2 group-hover:text-blue-600 transition-colors">{f.title}</h3>
                <p className="text-gray-500 text-sm leading-relaxed">{f.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── How it works ── */}
      <section id="how-it-works" className="py-24 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <span className="text-blue-600 font-semibold text-sm uppercase tracking-widest">Process</span>
            <h2 className="mt-2 text-4xl font-extrabold tracking-tight">Up and running in minutes</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-10 relative">
            {/* Connector line */}
            <div className="hidden md:block absolute top-10 left-1/3 right-1/3 h-0.5 bg-gray-200" />

            {[
              {
                step: "01",
                title: "Create your account",
                desc: "Sign up, choose your plan, and configure your company profile in under 5 minutes.",
              },
              {
                step: "02",
                title: "Add branches & users",
                desc: "Invite your team, set roles, and connect all your locations to the central dashboard.",
              },
              {
                step: "03",
                title: "Go live",
                desc: "Start processing sales, tracking inventory, and generating financial reports immediately.",
              },
            ].map((item) => (
              <div key={item.step} className="flex flex-col items-center text-center">
                <div className="w-20 h-20 rounded-full bg-black text-white flex items-center justify-center text-2xl font-extrabold mb-6 shadow-lg">
                  {item.step}
                </div>
                <h3 className="text-xl font-bold mb-2">{item.title}</h3>
                <p className="text-gray-500 text-sm leading-relaxed max-w-xs">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Offline-first callout ── */}
      <section className="py-20 bg-gradient-to-br from-gray-900 to-black text-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col lg:flex-row items-center gap-12">
          <div className="flex-1">
            <span className="text-blue-400 font-semibold text-sm uppercase tracking-widest">Offline-first</span>
            <h2 className="mt-2 text-4xl font-extrabold tracking-tight leading-tight">
              Never lose a sale — even without internet
            </h2>
            <p className="mt-4 text-gray-400 text-lg leading-relaxed max-w-lg">
              Nexus ERP is built as a Progressive Web App with local-first storage. Transactions are
              queued locally and automatically synced the moment connectivity returns — with intelligent
              conflict resolution to prevent duplicates.
            </p>
            <ul className="mt-8 space-y-3">
              {[
                "Transactions stored in IndexedDB / SQLite",
                "Unique IDs and sync-status on every record",
                "Automatic background sync on reconnect",
                "Conflict resolution rules built-in",
              ].map((item) => (
                <li key={item} className="flex items-center gap-3 text-gray-300 text-sm">
                  <CheckIcon />
                  {item}
                </li>
              ))}
            </ul>
          </div>

          <div className="flex-1 flex justify-center">
            <div className="bg-white/5 border border-white/10 rounded-2xl p-8 w-full max-w-sm backdrop-blur-sm">
              <div className="flex items-center gap-3 mb-6">
                <div className="w-3 h-3 rounded-full bg-red-500" />
                <div className="w-3 h-3 rounded-full bg-yellow-500" />
                <div className="w-3 h-3 rounded-full bg-green-500" />
                <span className="ml-auto text-xs text-gray-500">sync status</span>
              </div>
              {[
                { id: "TXN-0041", status: "synced", color: "text-green-400" },
                { id: "TXN-0042", status: "synced", color: "text-green-400" },
                { id: "TXN-0043", status: "pending", color: "text-yellow-400" },
                { id: "TXN-0044", status: "pending", color: "text-yellow-400" },
                { id: "TXN-0045", status: "queued", color: "text-gray-400" },
              ].map((row) => (
                <div key={row.id} className="flex items-center justify-between py-2 border-b border-white/5 text-sm">
                  <span className="text-gray-300 font-mono">{row.id}</span>
                  <span className={`${row.color} font-medium`}>{row.status}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── Pricing ── */}
      <section id="pricing" className="py-24 bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <span className="text-blue-600 font-semibold text-sm uppercase tracking-widest">Pricing</span>
            <h2 className="mt-2 text-4xl font-extrabold tracking-tight">Simple, transparent pricing</h2>
            <p className="mt-4 text-gray-500 max-w-xl mx-auto text-lg">
              Start free for 14 days. No credit card required.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 items-stretch">
            {plans.map((plan) => (
              <div
                key={plan.name}
                className={`rounded-2xl p-8 flex flex-col border transition-shadow ${
                  plan.highlight
                    ? "bg-black text-white border-black shadow-2xl scale-105"
                    : "bg-white text-gray-900 border-gray-200 shadow-sm hover:shadow-md"
                }`}
              >
                {plan.highlight && (
                  <span className="self-start text-xs font-bold bg-blue-500 text-white px-3 py-1 rounded-full mb-4">
                    Most popular
                  </span>
                )}
                <h3 className="text-xl font-bold mb-1">{plan.name}</h3>
                <p className={`text-sm mb-6 ${plan.highlight ? "text-gray-400" : "text-gray-500"}`}>
                  {plan.description}
                </p>
                <div className="flex items-end gap-1 mb-8">
                  <span className="text-4xl font-extrabold">{plan.price}</span>
                  <span className={`text-sm mb-1 ${plan.highlight ? "text-gray-400" : "text-gray-500"}`}>
                    {plan.period}
                  </span>
                </div>
                <ul className="space-y-3 mb-8 flex-1">
                  {plan.features.map((f) => (
                    <li key={f} className="flex items-center gap-3 text-sm">
                      <CheckIcon />
                      <span className={plan.highlight ? "text-gray-300" : "text-gray-600"}>{f}</span>
                    </li>
                  ))}
                </ul>
                <Link href="/auth/register">
                  <Button
                    className={`w-full rounded-xl font-semibold ${
                      plan.highlight
                        ? "bg-white text-black hover:bg-gray-100"
                        : "bg-black text-white hover:bg-zinc-800"
                    }`}
                  >
                    {plan.cta}
                  </Button>
                </Link>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Testimonials ── */}
      <section id="testimonials" className="py-24 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <span className="text-blue-600 font-semibold text-sm uppercase tracking-widest">Testimonials</span>
            <h2 className="mt-2 text-4xl font-extrabold tracking-tight">Loved by operators across Africa</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {testimonials.map((t) => (
              <div key={t.author} className="bg-gray-50 rounded-2xl p-8 border border-gray-100">
                <p className="text-gray-700 text-sm leading-relaxed mb-6 italic">&ldquo;{t.quote}&rdquo;</p>
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-black text-white flex items-center justify-center text-sm font-bold flex-shrink-0">
                    {t.avatar}
                  </div>
                  <div>
                    <p className="font-semibold text-sm">{t.author}</p>
                    <p className="text-gray-500 text-xs">{t.role}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA Banner ── */}
      <section className="py-24 bg-black text-white">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-4xl sm:text-5xl font-extrabold tracking-tight mb-6">
            Ready to streamline your operations?
          </h2>
          <p className="text-gray-400 text-lg mb-10">
            Join hundreds of businesses already running on Nexus ERP. Get started in minutes.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link href="/auth/register">
              <Button
                size="lg"
                className="px-10 h-14 text-base bg-white text-black hover:bg-gray-100 rounded-xl font-bold shadow-xl transition-all hover:-translate-y-0.5 inline-flex items-center"
              >
                Create free account
                <ArrowRightIcon />
              </Button>
            </Link>
            <Link href="/auth/login">
              <Button
                size="lg"
                variant="outline"
                className="px-10 h-14 text-base text-white border-white/30 hover:border-white hover:bg-white/10 bg-transparent rounded-xl transition-all"
              >
                Sign in
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="bg-gray-950 text-gray-400 py-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-white rounded-md flex items-center justify-center">
              <span className="text-black font-bold text-sm">N</span>
            </div>
            <span className="text-white font-semibold">Nexus ERP</span>
          </div>
          <p className="text-sm text-center">
            © {new Date().getFullYear()} Nexus ERP. All rights reserved.
          </p>
          <div className="flex gap-6 text-sm">
            <a href="#" className="hover:text-white transition-colors">Privacy</a>
            <a href="#" className="hover:text-white transition-colors">Terms</a>
            <a href="#" className="hover:text-white transition-colors">Contact</a>
          </div>
        </div>
      </footer>

    </div>
  );
}
