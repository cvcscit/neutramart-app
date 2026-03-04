import { useState } from "react";

export default function useDropzone(onFileDrop) {
  const [dragging, setDragging] = useState(false);

  function onDrop(e) {
    e.preventDefault();
    setDragging(false);
    onFileDrop(e.dataTransfer.files[0]);
  }

  function onDragOver(e) {
    e.preventDefault();
    setDragging(true);
  }

  function onDragLeave() {
    setDragging(false);
  }

  return { dragging, onDrop, onDragOver, onDragLeave };
}
