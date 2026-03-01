import { createContext, useContext, useState } from "react";
import { jwtDecode } from "jwt-decode";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);

  function handleLoginSuccess(credentialResponse) {
    const decoded = jwtDecode(credentialResponse.credential);
    setUser({
      firstName: decoded.given_name,
      email: decoded.email,
      picture: decoded.picture,
    });
  }

  function handleLogout() {
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, handleLoginSuccess, handleLogout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
