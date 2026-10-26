import { useEffect, useRef, useState } from "react";
import { hasFiles } from "./chatUtils";

/**
 * Desktop: Excel files dragged anywhere onto the window are shared with the chat. Listens on the window while
 * `enabled` (Home on screen), so the whole page is the drop target, not just the ask box.
 */
export function useFileDrop(enabled: boolean, onFiles: (files: FileList) => void): boolean {
  const [dragging, setDragging] = useState(false);
  const latest = useRef(onFiles);
  latest.current = onFiles;

  useEffect(() => {
    if (!enabled) {
      setDragging(false);
      return;
    }
    // Drag events fire on every element the pointer crosses: count enters and leaves instead of trusting one leave.
    let depth = 0;
    const reset = () => {
      depth = 0;
      setDragging(false);
    };
    const onEnter = (event: DragEvent) => {
      if (!hasFiles(event)) return;
      event.preventDefault();
      depth += 1;
      setDragging(true);
    };
    const onOver = (event: DragEvent) => {
      if (hasFiles(event)) event.preventDefault();
    };
    const onLeave = (event: DragEvent) => {
      depth = Math.max(0, depth - 1);
      if (depth === 0 || !event.relatedTarget) reset();
    };
    const onDrop = (event: DragEvent) => {
      if (!hasFiles(event)) return reset();
      event.preventDefault();
      reset();
      if (event.dataTransfer?.files.length) latest.current(event.dataTransfer.files);
    };
    window.addEventListener("dragenter", onEnter);
    window.addEventListener("dragover", onOver);
    window.addEventListener("dragleave", onLeave);
    window.addEventListener("drop", onDrop);
    window.addEventListener("dragend", reset);
    return () => {
      window.removeEventListener("dragenter", onEnter);
      window.removeEventListener("dragover", onOver);
      window.removeEventListener("dragleave", onLeave);
      window.removeEventListener("drop", onDrop);
      window.removeEventListener("dragend", reset);
    };
  }, [enabled]);

  return dragging;
}
