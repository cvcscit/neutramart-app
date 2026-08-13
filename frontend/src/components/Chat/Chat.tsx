import { useState, useRef, useEffect } from "react";
import { useAuth } from "../../contexts/AuthContext";
import {
  sendChatMessage,
  getPresignedUrl,
  uploadToS3,
  analyzeFood,
} from "../../services/api";
import "./Chat.css";

type Message = {
  role: "user" | "assistant" | "system";
  content: string;
};

function summarizeAnalysis(analysis: any): string {
  let payload = analysis;

  if (Array.isArray(payload)) payload = payload[0];
  if (payload?.analyses && Array.isArray(payload.analyses)) payload = payload.analyses[0];
  if (payload?.results && Array.isArray(payload.results)) payload = payload.results[0];

  const item = payload ?? {};
  const description = item.description || item.name || "this meal";
  const total = item.totalNutrition ?? item.nutrition ?? {};
  const calories = total.calories ?? item.calories ?? item.nf_calories;
  const protein = total.protein ?? item.protein;
  const carbs = total.carbs ?? item.carbs;
  const fat = total.fat ?? item.fat;
  const allergens = Array.isArray(item.allergens) ? item.allergens.slice(0, 3).join(", ") : "none noted";
  const objects = Array.isArray(item.objects) ? item.objects.slice(0, 4).join(", ") : "no major objects";

  return `I analyzed ${description}. ${calories ? `Estimated ${calories} kcal` : ""}${protein ? `, ${protein}g protein` : ""}${carbs ? `, ${carbs}g carbs` : ""}${fat ? `, ${fat}g fat` : ""}. Allergens: ${allergens}. Foods identified: ${objects}.`;
}

export default function Chat() {
  const { token, user } = useAuth();
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content:
        "Hi! I'm your NutraSmart AI assistant. Ask me anything about your eating habits, nutrition, or diet recommendations.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSend(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMessage = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    setLoading(true);

    try {
      const history = messages
        .filter((m) => m.role !== "system")
        .map((m) => ({ role: m.role, content: m.content }));

      if (!token) return;
      const { reply } = await sendChatMessage(token, {
        message: userMessage,
        history,
      });

      setMessages((prev) => [...prev, { role: "assistant", content: reply }]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Sorry, something went wrong. Please try again.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  async function handleImageUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files || []);
    if (!files.length || !token || !user) {
      if (fileInputRef.current) fileInputRef.current.value = "";
      return;
    }

    const selected = files.filter((file) => file.type.startsWith("image/"));
    if (!selected.length) {
      if (fileInputRef.current) fileInputRef.current.value = "";
      return;
    }

    const imageLabel = selected.length === 1 ? selected[0].name : `${selected.length} images`;
    setMessages((prev) => [...prev, { role: "user", content: `Uploaded ${imageLabel}` }]);
    setLoading(true);

    try {
      const uploaded = await Promise.all(
        selected.map(async (file) => {
          const { url, key } = await getPresignedUrl(token, {
            filename: file.name,
            contentType: file.type,
            email: user.email,
          });

          await uploadToS3(url, file, () => undefined);
          return { key, contentType: file.type };
        })
      );

      const analysis = await analyzeFood(token, uploaded);
      const summary = summarizeAnalysis(analysis);

      setMessages((prev) => [...prev, { role: "assistant", content: summary }]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "I couldn't analyze that image yet. Please try a clear food photo again.",
        },
      ]);
    } finally {
      setLoading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  if (!open) {
    return (
      <button
        className="chat-fab"
        onClick={() => setOpen(true)}
        title="Chat with NutraSmart AI"
      >
        <svg
          className="chat-fab-icon"
          viewBox="0 0 24 24"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            d="M20 2H4C2.9 2 2 2.9 2 4V22L6 18H20C21.1 18 22 17.1 22 16V4C22 2.9 21.1 2 20 2Z"
            fill="white"
          />
          <circle cx="8" cy="10" r="1.5" fill="#3498db" />
          <circle cx="12" cy="10" r="1.5" fill="#3498db" />
          <circle cx="16" cy="10" r="1.5" fill="#3498db" />
        </svg>
      </button>
    );
  }

  return (
    <div className="chat-panel">
      <div className="chat-header">
        <h3 className="chat-title">NutraSmart AI</h3>
        <button className="chat-close" onClick={() => setOpen(false)}>
          ✕
        </button>
      </div>

      <div className="chat-messages">
        {messages.map((msg, i) => (
          <div key={i} className={`chat-bubble chat-bubble--${msg.role}`}>
            {msg.content}
          </div>
        ))}
        {loading && (
          <div className="chat-bubble chat-bubble--assistant chat-bubble--typing">
            <span className="typing-dot" />
            <span className="typing-dot" />
            <span className="typing-dot" />
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <form className="chat-input-bar" onSubmit={handleSend}>
        <button
          type="button"
          className="chat-upload"
          onClick={() => fileInputRef.current?.click()}
          disabled={loading}
        >
          Image
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          multiple
          hidden
          onChange={handleImageUpload}
        />
        <input
          className="chat-input"
          type="text"
          placeholder="Ask about your diet..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={loading}
        />
        <button
          className="chat-send"
          type="submit"
          disabled={loading || !input.trim()}
        >
          Send
        </button>
      </form>
    </div>
  );
}
