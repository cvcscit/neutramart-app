import ImageUpload from "./ImageUpload";
import Chat from "./Chat/Chat";

export default function Upload() {
  return (
    <div className="home-page">
      <main className="home-layout">
        <ImageUpload />
      </main>
      <Chat />
    </div>
  );
}
