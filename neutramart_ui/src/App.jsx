import { useAuth } from "./contexts/AuthContext";
import Login from "./components/Login/Login";
import Home from "./components/Home/Home";
import "./index.css";

export default function App() {
  const { user } = useAuth();
  return user ? <Home /> : <Login />;
}
