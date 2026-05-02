/**
 * App — router setup + auth provider + TanStack Query + Toaster.
 *
 * Provider nesting (outer → inner):
 *   QueryClientProvider     — server-state cache, available to every hook
 *     AuthProvider          — currently signed-in user
 *       BrowserRouter       — URL → Routes mapping
 *
 * Route structure:
 *   /login                  → LoginPage (unprotected)
 *   /                       → JobListPage (protected, inside Layout)
 *   /jobs/:jobId            → JobDetailPage (protected)
 *   /settings               → SettingsPage (protected)
 *   *                       → NotFoundPage
 */

import { QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { BrowserRouter, Route, Routes } from "react-router";

import { AuthProvider } from "@/auth/AuthContext";
import { RequireAuth } from "@/auth/RequireAuth";
import { Layout } from "@/components/Layout";
import { Toaster } from "@/components/ui/Toaster";
import { queryClient } from "@/lib/queryClient";
import ApplicationsPage from "@/pages/ApplicationsPage";
import JobDetailPage from "@/pages/JobDetailPage";
import JobListPage from "@/pages/JobListPage";
import LoginPage from "@/pages/LoginPage";
import ManualJobsPage from "@/pages/ManualJobsPage";
import NotFoundPage from "@/pages/NotFoundPage";
import SettingsPage from "@/pages/SettingsPage";
import UsagePage from "@/pages/UsagePage";

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
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
              <Route path="/applications" element={<ApplicationsPage />} />
              <Route path="/added-jobs" element={<ManualJobsPage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/usage" element={<UsagePage />} />
            </Route>
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </BrowserRouter>
        <Toaster />
        {import.meta.env.DEV && <ReactQueryDevtools initialIsOpen={false} />}
      </AuthProvider>
    </QueryClientProvider>
  );
}
