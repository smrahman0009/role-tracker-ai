/**
 * App — router setup + auth provider + global Toaster.
 *
 * Route structure:
 *   /login                  → LoginPage (unprotected)
 *   /                       → JobListPage (protected, inside Layout)
 *   /jobs/:jobId            → JobDetailPage (protected)
 *   /settings               → SettingsPage (protected)
 *   *                       → NotFoundPage
 *
 * Protected routes are wrapped in <RequireAuth><Layout /></RequireAuth>:
 * RequireAuth bounces unauthenticated users to /login (preserving the
 * destination); Layout renders the top header + <Outlet /> for the page.
 */

import { BrowserRouter, Route, Routes } from "react-router";

import { AuthProvider } from "@/auth/AuthContext";
import { RequireAuth } from "@/auth/RequireAuth";
import { Layout } from "@/components/Layout";
import { Toaster } from "@/components/ui/Toaster";
import JobDetailPage from "@/pages/JobDetailPage";
import JobListPage from "@/pages/JobListPage";
import LoginPage from "@/pages/LoginPage";
import NotFoundPage from "@/pages/NotFoundPage";
import SettingsPage from "@/pages/SettingsPage";

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            element={
              <RequireAuth>
                <Layout />
              </RequireAuth>
            }
          >
            <Route path="/" element={<JobListPage />} />
            <Route path="/jobs/:jobId" element={<JobDetailPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Route>
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </BrowserRouter>
      <Toaster />
    </AuthProvider>
  );
}
