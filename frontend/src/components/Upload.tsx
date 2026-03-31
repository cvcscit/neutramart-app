import { useState } from "react";
import { useAuth } from "../contexts/AuthContext";
import Navbar from "./Navbar";
import ImageUpload from "./ImageUpload";
import WeeklySummary from "./WeeklySummary/WeeklySummary";
import Chat from "./Chat/Chat";

export default function Upload() {
  const { user } = useAuth();
  const [scanCount, setScanCount] = useState(0);

  return (
    <div className="home-page">
      <main className="home-layout">
        <ImageUpload onScanComplete={() => setScanCount((c) => c + 1)} />
        <div className="home-right">
          <WeeklySummary refreshTrigger={scanCount} />
        </div>
      </main>
      <Chat />
    </div>
  );
}
