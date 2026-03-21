import { createContext, useContext, useState } from "react";
import { jwtDecode } from "jwt-decode";

const AuthContext = createContext(null);

function loadSession() {
  try {
    const savedToken = localStorage.getItem("auth_token");
    if (!savedToken) return { user: null, token: null };
    const decoded = jwtDecode(savedToken);
    // Check if token is expired
    if (decoded.exp * 1000 < Date.now()) {
      localStorage.removeItem("auth_token");
      return { user: null, token: null };
    }
    return {
      user: {
        firstName: decoded.given_name,
        email: decoded.email,
        picture: decoded.picture,
      },
      token: savedToken,
    };
  } catch {
    localStorage.removeItem("auth_token");
    return { user: null, token: null };
  }
}

export function AuthProvider({ children }) {
  const saved = loadSession();
  const [user, setUser] = useState(saved.user);
  const [token, setToken] = useState(saved.token);

  function handleLoginSuccess(credentialResponse) {
    const decoded = jwtDecode(credentialResponse.credential);
    localStorage.setItem("auth_token", credentialResponse.credential);
    setToken(credentialResponse.credential);
    setUser({
      firstName: decoded.given_name,
      email: decoded.email,
      picture: decoded.picture,
    });
  }

  function handleLogout() {
    localStorage.removeItem("auth_token");
    setUser(null);
    setToken(null);
  }

  return (
    <AuthContext.Provider value={{ user, token, handleLoginSuccess, handleLogout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
