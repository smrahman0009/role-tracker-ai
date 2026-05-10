/**
 * Layout — top header + main content area, used for every authenticated route.
 *
 * Wraps the route's <Outlet /> so the header stays put while page content
 * changes. Brand on the left; on desktop the full nav fits on the right;
 * on screens below the `md` breakpoint the nav collapses into a hamburger
 * that drops down a stacked menu.
 */

import { Menu, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router";

import { useAuth } from "@/auth/AuthContext";
import { DemoBanner } from "@/components/DemoBanner";

const NAV_LINKS = [
  { to: "/added-jobs", label: "My added jobs" },
  { to: "/applications", label: "My applications" },
  { to: "/usage", label: "Usage" },
  { to: "/settings", label: "Settings" },
];

export function Layout() {
  const { userId, signOut } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const handleSignOut = () => {
    signOut();
    navigate("/login", { replace: true });
  };

  // Close the mobile menu whenever the route changes — otherwise it
  // would stay open on top of the new page after a tap.
  useEffect(() => {
    setMenuOpen(false);
  }, [location.pathname]);

  // Click-outside + Escape to close. Listeners only attached while
  // open so we're not paying for them on every render.
  useEffect(() => {
    if (!menuOpen) return;
    const onPointer = (e: MouseEvent | TouchEvent) => {
      if (
        menuRef.current &&
        !menuRef.current.contains(e.target as Node)
      ) {
        setMenuOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMenuOpen(false);
    };
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("touchstart", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("touchstart", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [menuOpen]);

  return (
    <div className="min-h-screen bg-slate-50">
      <DemoBanner />
      <header className="bg-white border-b border-slate-200">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Link
              to="/"
              className="text-base font-semibold text-slate-900 tracking-tight hover:text-slate-700 transition-colors"
            >
              Role Tracker
            </Link>
            <span className="text-xs text-slate-400 font-medium tracking-wider uppercase">
              beta
            </span>
          </div>

          {/* Desktop nav — visible at md+ */}
          <nav className="hidden md:flex items-center gap-3">
            {NAV_LINKS.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                className={({ isActive }) =>
                  isActive
                    ? "text-xs font-medium text-slate-900"
                    : "text-xs text-slate-500 hover:text-slate-700 transition-colors"
                }
              >
                {link.label}
              </NavLink>
            ))}
            <span className="text-slate-300">·</span>
            <span className="text-xs text-slate-500">{userId}</span>
            <button
              onClick={handleSignOut}
              className="text-xs text-slate-500 hover:text-slate-700 transition-colors"
            >
              Sign out
            </button>
          </nav>

          {/* Hamburger toggle — visible below md */}
          <div ref={menuRef} className="md:hidden relative">
            <button
              type="button"
              onClick={() => setMenuOpen((v) => !v)}
              aria-label={menuOpen ? "Close menu" : "Open menu"}
              aria-expanded={menuOpen}
              aria-controls="mobile-nav"
              className="inline-flex items-center justify-center rounded-md p-2 text-slate-700 hover:bg-slate-100"
            >
              {menuOpen ? (
                <X className="h-5 w-5" />
              ) : (
                <Menu className="h-5 w-5" />
              )}
            </button>

            {menuOpen && (
              <div
                id="mobile-nav"
                className="absolute right-0 top-full mt-2 w-56 rounded-lg border border-slate-200 bg-white shadow-lg py-2 z-50"
              >
                {NAV_LINKS.map((link) => (
                  <NavLink
                    key={link.to}
                    to={link.to}
                    className={({ isActive }) =>
                      `block px-4 py-2 text-sm ${
                        isActive
                          ? "font-medium text-slate-900 bg-slate-50"
                          : "text-slate-600 hover:bg-slate-50"
                      }`
                    }
                  >
                    {link.label}
                  </NavLink>
                ))}
                <div className="border-t border-slate-100 my-2" />
                <div className="px-4 py-1.5 text-xs text-slate-400">
                  Signed in as <span className="text-slate-600">{userId}</span>
                </div>
                <button
                  type="button"
                  onClick={handleSignOut}
                  className="w-full text-left px-4 py-2 text-sm text-slate-600 hover:bg-slate-50"
                >
                  Sign out
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      <main>
        <Outlet />
      </main>
    </div>
  );
}
