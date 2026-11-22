import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { ProjectProvider } from './context/ProjectContext';
import ProtectedRoute from './components/auth/ProtectedRoute';
import PublicOnlyRoute from './components/auth/PublicOnlyRoute';
import Layout from './components/layout/Layout';

// Authentication UI Pages
import LoginPage from './pages/LoginPage';
import SignupPage from './pages/SignupPage';
import ForgotPasswordPage from './pages/ForgotPasswordPage';
import ResetPasswordPage from './pages/ResetPasswordPage';

// Pages
import DashboardPage from './pages/DashboardPage';
import RequirementsPage from './pages/RequirementsPage';
import SrsPage from './pages/SrsPage';
import ArchitecturePage from './pages/ArchitecturePage';
import DatabaseSchemaPage from './pages/DatabaseSchemaPage';
import ApiDocumentationPage from './pages/ApiDocumentationPage';
import BackendSkeletonPage from './pages/BackendSkeletonPage';
import TestCasesPage from './pages/TestCasesPage';
import KnowledgeGraphPage from './pages/KnowledgeGraphPage';
import AssistantPage from './pages/AssistantPage';
import SettingsPage from './pages/SettingsPage';

export default function App() {
  return (
    <AuthProvider>
      <ProjectProvider>
        <BrowserRouter>
          <Routes>
            {/* Authentication UI Routes (Redirect away if already signed in) */}
            <Route path="/login" element={<PublicOnlyRoute><LoginPage /></PublicOnlyRoute>} />
            <Route path="/signup" element={<PublicOnlyRoute><SignupPage /></PublicOnlyRoute>} />
            <Route path="/forgot-password" element={<ForgotPasswordPage />} />
            <Route path="/reset-password" element={<ResetPasswordPage />} />

            {/* Protected Workspace Routes (Redirect to /login if unauthenticated) */}
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <Layout />
                </ProtectedRoute>
              }
            >
              <Route index element={<DashboardPage />} />
              <Route path="requirements" element={<RequirementsPage />} />
              <Route path="srs" element={<SrsPage />} />
              <Route path="architecture" element={<ArchitecturePage />} />
              <Route path="database-schema" element={<DatabaseSchemaPage />} />
              <Route path="api-documentation" element={<ApiDocumentationPage />} />
              <Route path="backend-code" element={<BackendSkeletonPage />} />
              <Route path="test-cases" element={<TestCasesPage />} />
              <Route path="knowledge-graph" element={<KnowledgeGraphPage />} />
              <Route path="query-assistant" element={<AssistantPage />} />
              <Route path="settings" element={<SettingsPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </ProjectProvider>
    </AuthProvider>
  );
}
