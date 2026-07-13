import { Navigate, createBrowserRouter } from "react-router-dom";

import Layout from "../components/Layout";
import ProtectedRoute from "../components/ProtectedRoute";
import AgentPage from "../pages/AgentPage";
import ChatPage from "../pages/ChatPage";
import DashboardPage from "../pages/DashboardPage";
import DetectionHistoryPage from "../pages/DetectionHistoryPage";
import DetectionPage from "../pages/DetectionPage";
import LoginPage from "../pages/LoginPage";
import ProfilePage from "../pages/ProfilePage";
import RegisterPage from "../pages/RegisterPage";
import UserManagementPage from "../pages/admin/UserManagementPage";

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
            path: "/detections/history",
            element: <DetectionHistoryPage />,
          },
          {
            path: "/profile",
            element: <ProfilePage />,
          },
          {
            path: "/chat",
            element: <ChatPage />,
          },
          {
            path: "/agent",
            element: <AgentPage />,
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
