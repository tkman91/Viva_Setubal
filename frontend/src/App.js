import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { ThemeProvider } from "@/context/ThemeContext";
import { Toaster } from "@/components/ui/sonner";
import Layout from "@/components/Layout";
import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";
import Stock from "@/pages/Stock";
import Picagem from "@/pages/Picagem";
import Staff from "@/pages/Staff";
import Consumo from "@/pages/Consumo";
import Faturacao from "@/pages/Faturacao";
import Settings from "@/pages/Settings";

function Protected({ children, module }) {
  const { user, loading, can, isManager } = useAuth();
  if (loading) return <div className="min-h-screen flex items-center justify-center text-muted-foreground">A carregar...</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (module) {
    const managerOnly = ["staff", "faturacao", "settings"];
    const allowed = managerOnly.includes(module) ? isManager || can(module) : can(module);
    if (!allowed) return <Navigate to="/" replace />;
  }
  return <Layout>{children}</Layout>;
}

function LoginRoute() {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (user) return <Navigate to="/" replace />;
  return <Login />;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginRoute />} />
      <Route path="/" element={<Protected><Dashboard /></Protected>} />
      <Route path="/picagem" element={<Protected module="picagem"><Picagem /></Protected>} />
      <Route path="/stock" element={<Protected module="stock"><Stock /></Protected>} />
      <Route path="/consumo" element={<Protected module="consumo"><Consumo /></Protected>} />
      <Route path="/staff" element={<Protected module="staff"><Staff /></Protected>} />
      <Route path="/faturacao" element={<Protected module="faturacao"><Faturacao /></Protected>} />
      <Route path="/definicoes" element={<Protected module="settings"><Settings /></Protected>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <div className="App">
      <ThemeProvider>
        <AuthProvider>
          <BrowserRouter>
            <AppRoutes />
            <Toaster position="top-right" />
          </BrowserRouter>
        </AuthProvider>
      </ThemeProvider>
    </div>
  );
}

export default App;
