import { GoogleLogin } from "@react-oauth/google";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";
import "./Login.css";

export default function Login() {
  const { handleLoginSuccess } = useAuth();
  const navigate = useNavigate();

  function onSuccess(credentialResponse: any) {
    handleLoginSuccess(credentialResponse);
    navigate("/dashboard");
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-header">
          <h1>nutrasmart</h1>
          <p>Sign in with your Google account to continue</p>
        </div>
        <div className="login-action">
          <GoogleLogin
            onSuccess={onSuccess}
            onError={() => console.error("Login failed")}
            shape="rectangular"
            size="large"
            width="300"
          />
        </div>
      </div>
    </div>
  );
}
