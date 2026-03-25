import { createContext, useContext, useState, ReactNode } from "react";
import { jwtDecode } from "jwt-decode";

type User = {
  firstName: string;
  email: string;
  picture: string;
};

type AuthContextType = {
  user: User | null;
  token: string | null;
  handleLoginSuccess: (credentialResponse: any) => void;
  handleLogout: () => void;
};

const AuthContext = createContext<AuthContextType | null>(null);

type JwtPayload = {
  exp: number;
  given_name: string;
  email: string;
  picture: string;
};

function loadSession(): { user: User | null; token: string | null } {
  try {
    const savedToken = localStorage.getItem("auth_token");
    if (!savedToken) return { user: null, token: null };

    const decoded = jwtDecode<JwtPayload>(savedToken);

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

export function AuthProvider({ children }: { children: ReactNode }) {
  const saved = loadSession();

  const [user, setUser] = useState<User | null>(saved.user);
  const [token, setToken] = useState<string | null>(saved.token);

  function handleLoginSuccess(credentialResponse: any) {
    const decoded = jwtDecode<JwtPayload>(credentialResponse.credential);

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
    <AuthContext.Provider
      value={{ user, token, handleLoginSuccess, handleLogout }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
