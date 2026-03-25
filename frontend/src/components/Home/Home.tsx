import { useState } from "react";
import { useAuth } from "../../contexts/AuthContext";
import Navbar from "../Navbar/Navbar";
import ImageUpload from "../ImageUpload/ImageUpload";
import WeeklySummary from "../WeeklySummary/WeeklySummary";
import Chat from "../Chat/Chat";

export default function Home() {
  const { user } = useAuth();
  const [scanCount, setScanCount] = useState(0);

  return (
    <div className="home-page">
      <Navbar />
      <main className="home-layout">
        <div className="home-left">
          <h2 className="flex text-4xl underline">Hello, {user?.firstName}</h2>
          <p className="home-subtitle">Upload an image to get started</p>
          <ImageUpload onScanComplete={() => setScanCount((c) => c + 1)} />
        </div>
        <div className="home-right">
          <WeeklySummary refreshTrigger={scanCount} />
        </div>
      </main>
      <Chat />
    </div>
  );
}
