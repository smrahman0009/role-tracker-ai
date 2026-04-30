/**
 * Layout — top header + main content area, used for every authenticated route.
 *
 * Wraps the route's <Outlet /> so the header stays put while page content
 * changes. Matches the wireframe: brand on the left, settings link +
 * user_id + sign out on the right.
 */

import { Link, NavLink, Outlet, useNavigate } from "react-router";

import { useAuth } from "@/auth/AuthContext";

export function Layout() {
  const { userId, signOut } = useAuth();
  const navigate = useNavigate();

  const handleSignOut = () => {
    signOut();
    navigate("/login", { replace: true });
  };

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-white border-b border-slate-200">
        <div className="max-w-5xl mx-auto px-6 h-14 flex items-center justify-between">
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
          <nav className="flex items-center gap-3">
            <NavLink
              to="/applications"
              className={({ isActive }) =>
                isActive
                  ? "text-xs font-medium text-slate-900"
                  : "text-xs text-slate-500 hover:text-slate-700 transition-colors"
              }
            >
              My applications
            </NavLink>
            <NavLink
              to="/settings"
              className={({ isActive }) =>
                isActive
                  ? "text-xs font-medium text-slate-900"
                  : "text-xs text-slate-500 hover:text-slate-700 transition-colors"
              }
            >
              Settings
            </NavLink>
            <span className="text-slate-300">·</span>
            <span className="text-xs text-slate-500">{userId}</span>
            <button
              onClick={handleSignOut}
              className="text-xs text-slate-500 hover:text-slate-700 transition-colors"
            >
              Sign out
            </button>
          </nav>
        </div>
      </header>

      <main>
        <Outlet />
      </main>
    </div>
  );
}
