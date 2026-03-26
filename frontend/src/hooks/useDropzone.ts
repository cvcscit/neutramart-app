import { useState } from "react";

export default function useDropzone(onFilesDrop: (files: File[]) => void) {
  const [dragging, setDragging] = useState<boolean>(false);

  function onDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragging(false);

    const dropped = Array.from(e.dataTransfer.files || []);
    if (dropped.length) onFilesDrop(dropped);
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
