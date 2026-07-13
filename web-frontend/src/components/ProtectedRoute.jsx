import { Navigate, Outlet } from "react-router-dom";
import { useEffect, useState } from "react";

import authService from "../services/authService";

export default function ProtectedRoute({ requireAdmin = false }) {
  const [state, setState] = useState({
    loading: true,
    user: authService.getCurrentUser(),
  });

  useEffect(() => {
    let mounted = true;

    async function verifySession() {
      if (!authService.getAccessToken()) {
        if (mounted) {
          setState({ loading: false, user: null });
        }
        return;
      }

      try {
        const user = await authService.fetchCurrentUser();
        if (mounted) {
          setState({ loading: false, user });
        }
      } catch {
        authService.clearSession();
        if (mounted) {
          setState({ loading: false, user: null });
        }
      }
    }

    verifySession();

    return () => {
      mounted = false;
    };
  }, []);

  if (state.loading) {
    return (
      <div className="page-shell">
        <div className="panel panel-narrow">
          <h2>驗證登入狀態</h2>
          <p className="muted">正在確認目前 session。</p>
        </div>
      </div>
    );
  }

  if (!state.user) {
    return <Navigate to="/login" replace />;
  }

  if (requireAdmin && !state.user.is_admin) {
    return <Navigate to="/" replace />;
  }

  return <Outlet />;
}
