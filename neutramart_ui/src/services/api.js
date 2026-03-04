import { API_URL } from "../config/api";

export function getPresignedUrl(token, { filename, contentType, email }) {
  return fetch(`${API_URL}/upload/presign`, {
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
  }).then(async (res) => {
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Failed to get upload URL");
    }
    return res.json();
  });
}

export function uploadToS3(url, file, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", url);
    xhr.setRequestHeader("Content-Type", file.type);

    xhr.upload.onprogress = (e) => {
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

export function analyzeFood(token, { key, contentType }) {
  return fetch(`${API_URL}/analyze`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ key, content_type: contentType }),
  }).then(async (res) => {
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Food analysis failed");
    }
    return res.json();
  });
}
