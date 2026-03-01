import { useAuth } from "../../contexts/AuthContext";
import "./Navbar.css";

export default function Navbar() {
  const { user, handleLogout } = useAuth();

  return (
    <nav className="navbar">
      <span className="navbar-brand">Neutramart</span>
      <div className="navbar-right">
        <img src={user.picture} alt="" className="navbar-avatar" />
        <span className="navbar-name">{user.firstName}</span>
        <button className="navbar-logout" onClick={handleLogout}>
          Logout
        </button>
      </div>
    </nav>
  );
}
