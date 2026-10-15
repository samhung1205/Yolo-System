import { lazy } from "react";
import { Navigate, createBrowserRouter } from "react-router-dom";

import Layout from "../components/Layout";
import AssistantWorkspace from "../components/AssistantWorkspace";
import ProtectedRoute from "../components/ProtectedRoute";
const AgentPage = lazy(() => import("../pages/AgentPage"));
const BatchDetectionPage = lazy(() => import("../pages/BatchDetectionPage"));
const ChatPage = lazy(() => import("../pages/ChatPage"));
const DashboardPage = lazy(() => import("../pages/DashboardPage"));
const DetectionHistoryPage = lazy(() => import("../pages/DetectionHistoryPage"));
const DetectionPage = lazy(() => import("../pages/DetectionPage"));
const LoginPage = lazy(() => import("../pages/LoginPage"));
const ProfilePage = lazy(() => import("../pages/ProfilePage"));
const RegisterPage = lazy(() => import("../pages/RegisterPage"));
const UserManagementPage = lazy(() => import("../pages/admin/UserManagementPage"));

const router = createBrowserRouter([
  {
    path: "/login",
    element: <LoginPage />,
  },
  {
    path: "/register",
    element: <RegisterPage />,
  },
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <Layout />,
        children: [
          {
            path: "/",
            element: <DashboardPage />,
          },
          {
            path: "/detections",
            element: <DetectionPage />,
          },
          {
            path: "/detections/batch",
            element: <BatchDetectionPage />,
          },
          {
            path: "/detections/history",
            element: <DetectionHistoryPage />,
          },
          {
            path: "/profile",
            element: <ProfilePage />,
          },
          {
            element: <AssistantWorkspace />,
            children: [
              { path: "/chat", element: <ChatPage /> },
              { path: "/agent", element: <AgentPage /> },
            ],
          },
          {
            element: <ProtectedRoute requireAdmin />,
            children: [
              {
                path: "/admin/users",
                element: <UserManagementPage />,
              },
            ],
          },
        ],
      },
    ],
  },
  {
    path: "*",
    element: <Navigate to="/" replace />,
  },
]);

export default router;
