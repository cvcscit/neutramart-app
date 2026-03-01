import { useAuth } from "../../contexts/AuthContext";
import Navbar from "../Navbar/Navbar";
import ImageUpload from "../ImageUpload/ImageUpload";
import "./Home.css";

export default function Home() {
  const { user } = useAuth();

  return (
    <div className="home-page">
      <Navbar />
      <main className="home-content">
        <h2>Hello, {user.firstName}</h2>
        <p className="home-subtitle">Upload an image to get started</p>
        <ImageUpload />
      </main>
    </div>
  );
}
