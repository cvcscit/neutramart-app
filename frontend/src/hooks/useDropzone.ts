import { useState } from "react";

export default function useDropzone(onFileDrop: (file: File) => void) {
  const [dragging, setDragging] = useState<boolean>(false);

  function onDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragging(false);

    const file = e.dataTransfer.files?.[0];
    if (file) onFileDrop(file);
  }

  function onDragOver(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragging(true);
  }

  function onDragLeave() {
    setDragging(false);
  }

  return { dragging, onDrop, onDragOver, onDragLeave };
}
