import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from "react";
import { jwtDecode } from "jwt-decode";
import { useGoogleOneTapLogin } from "@react-oauth/google";

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

const TOKEN_REFRESH_BUFFER_MS = 5 * 60 * 1000; // refresh 5 min before expiry

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

function OneTapAutoRefresh({ onSuccess }: { onSuccess: (resp: any) => void }) {
  useGoogleOneTapLogin({
    onSuccess,
    onError: () => {},
  });
  return null;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const saved = loadSession();

  const [user, setUser] = useState<User | null>(saved.user);
  const [token, setToken] = useState<string | null>(saved.token);
  const [needsRefresh, setNeedsRefresh] = useState(false);

  const handleLoginSuccess = useCallback((credentialResponse: any) => {
    const decoded = jwtDecode<JwtPayload>(credentialResponse.credential);

    localStorage.setItem("auth_token", credentialResponse.credential);
    setToken(credentialResponse.credential);
    setNeedsRefresh(false);

    setUser({
      firstName: decoded.given_name,
      email: decoded.email,
      picture: decoded.picture,
    });
  }, []);

  function handleLogout() {
    localStorage.removeItem("auth_token");
    setUser(null);
    setToken(null);
    setNeedsRefresh(false);
  }

  // Periodically check token expiry and trigger refresh
  useEffect(() => {
    if (!token) return;

    function checkExpiry() {
      try {
        const decoded = jwtDecode<JwtPayload>(token!);
        const timeLeft = decoded.exp * 1000 - Date.now();

        if (timeLeft <= 0) {
          // Token already expired — log out
          handleLogout();
        } else if (timeLeft <= TOKEN_REFRESH_BUFFER_MS) {
          // About to expire — trigger One Tap refresh
          setNeedsRefresh(true);
        }
      } catch {
        handleLogout();
      }
    }

    checkExpiry();
    const interval = setInterval(checkExpiry, 60 * 1000); // check every minute
    return () => clearInterval(interval);
  }, [token]);

  return (
    <AuthContext.Provider
      value={{ user, token, handleLoginSuccess, handleLogout }}
    >
      {needsRefresh && <OneTapAutoRefresh onSuccess={handleLoginSuccess} />}
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
