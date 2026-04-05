import { Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "./contexts/AuthContext";
import Home from "./components/Home";
import Upload from "./components/Upload";
import Login from "./components/Login";
import Dashboard from "./components/Dashboard";
import Chat from "./components/Chat/Chat";
import "./index.css";

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  return user ? <>{children}</> : <Navigate to="/" replace />;
}

export default function App() {
  const { user } = useAuth();

  return (
    <>
      <Routes>
        <Route
          path="/"
          element={user ? <Navigate to="/dashboard" replace /> : <Home />}
        />
        <Route path="/login" element={<Login />} />
        <Route
          path="/upload"
          element={
            <ProtectedRoute>
              <Upload />
            </ProtectedRoute>
          }
        />
        <Route path="/dashboard" element={
          <ProtectedRoute><Dashboard/></ProtectedRoute>}
        />
        <Route
          path="*"
          element={<Navigate to={user ? "/dashboard" : "/login"} replace />}
        />
      </Routes>
      {user && <Chat />}
    </>
  );
}
