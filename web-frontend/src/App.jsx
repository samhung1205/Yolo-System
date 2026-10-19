import { Suspense } from "react";
import { RouterProvider } from "react-router/dom";

import router from "./router";

export default function App() {
  return <Suspense fallback={<div className="page-shell" role="status">載入頁面中…</div>}><RouterProvider router={router} /></Suspense>;
}
