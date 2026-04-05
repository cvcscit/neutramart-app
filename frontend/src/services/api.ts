import { API_URL } from "../config/api";

/* ---------- Helpers ---------- */

async function jsonOrText(res: Response): Promise<any> {
  const ct = res.headers.get("content-type") ?? "";
  if (ct.includes("application/json")) return res.json();
  const text = await res.text();
  try { return JSON.parse(text); } catch { return { detail: text || res.statusText }; }
}

/* ---------- Types ---------- */

type PresignRequest = {
  filename: string;
  contentType: string;
  email: string;
};

type PresignResponse = {
  url: string;
  key: string;
};

type AnalyzeImageItem = {
  key: string;
  contentType: string;
};

type ChatRequest = {
  message: string;
  history: any[]; // replace later with proper type
};

/* ---------- API ---------- */

export async function getPresignedUrl(
  token: string,
  { filename, contentType, email }: PresignRequest,
): Promise<PresignResponse> {
  const res = await fetch(`${API_URL}/upload/presign`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      filename,
      content_type: contentType,
      email,
    }),
  });

  if (!res.ok) {
    const err = await jsonOrText(res);
    throw new Error(err.detail || "Failed to get upload URL");
  }

  return res.json();
}

export function uploadToS3(
  url: string,
  file: File,
  onProgress: (progress: number) => void,
): Promise<void> {
  return new Promise<void>((resolve, reject) => {
    const xhr = new XMLHttpRequest();

    xhr.open("PUT", url);
    xhr.setRequestHeader("Content-Type", file.type);

    xhr.upload.onprogress = (e: ProgressEvent<EventTarget>) => {
      if (e.lengthComputable) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve();
      } else {
        reject(new Error("Upload to S3 failed"));
      }
    };

    xhr.onerror = () => reject(new Error("Network error during upload"));

    xhr.send(file);
  });
}

export async function analyzeFood(
  token: string,
  images: AnalyzeImageItem[],
): Promise<any> {
  const res = await fetch(`${API_URL}/analyze`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      images: images.map(({ key, contentType }) => ({ key, content_type: contentType })),
    }),
  });

  if (!res.ok) {
    const err = await jsonOrText(res);
    throw new Error(err.detail || "Food analysis failed");
  }

  return res.json();
}

export async function sendChatMessage(
  token: string,
  { message, history }: ChatRequest,
): Promise<any> {
  const res = await fetch(`${API_URL}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ message, history }),
  });

  if (!res.ok) {
    const err = await jsonOrText(res);
    throw new Error(err.detail || "Chat failed");
  }

  return res.json();
}

export async function getWeeklySummary(token: string): Promise<any> {
  const res = await fetch(`${API_URL}/weekly-summary`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!res.ok) {
    const err = await jsonOrText(res);
    throw new Error(err.detail || "Failed to fetch weekly summary");
  }

  return res.json();
}
