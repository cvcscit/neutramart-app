import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { GoogleOAuthProvider } from "@react-oauth/google";
import { AuthProvider } from "./contexts/AuthContext.js";
import { ReactLenis } from "lenis/react";
import Navbar from "./components/Navbar";
import Footer from "./components/Footer.js";
import ScrollToTop from "./components/ScrollToTop.js";
import App from "./App.js";
import "./index.css";

const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID;

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <ScrollToTop />
      <GoogleOAuthProvider clientId={clientId}>
        <AuthProvider>
          <ReactLenis root>
            <Navbar />
            <App />
            <Footer />
          </ReactLenis>
        </AuthProvider>
      </GoogleOAuthProvider>
    </BrowserRouter>
  </StrictMode>,
);
