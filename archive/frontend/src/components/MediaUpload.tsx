/**
 * MediaUpload — drag/drop or pick-a-file uploader.
 *
 * Calls POST /api/v1/media with a multipart form. On success, invokes
 * onUploaded(asset) so the caller can attach it to a draft, render it
 * inline, etc.
 *
 * Used in:
 *   - Draft editor sidebar (attach to draft)
 *   - Encyclopedia edit forms (attach to civ/person/event/place)
 */

import { useRef, useState } from "react";
import { ApiError, apiUpload, MediaAsset } from "../api/client";
import { showToast } from "../hooks/useToast";

interface Props {
  onUploaded?: (asset: MediaAsset) => void;
  altPlaceholder?: string;
  disabled?: boolean;
}

export function MediaUpload({ onUploaded, altPlaceholder = "Describe the image…", disabled = false }: Props) {
  const fileRef = useRef<HTMLInputElement | null>(null);
  const [busy, setBusy] = useState(false);
  const [alt, setAlt] = useState("");
  const [preview, setPreview] = useState<MediaAsset | null>(null);

  const submit = async (file: File) => {
    if (disabled || busy) return;
    setBusy(true);
    try {
      const form = new FormData();
      form.append("file", file);
      if (alt.trim()) form.append("alt_text", alt.trim());
      const asset = await apiUpload<MediaAsset>("/media", form);
      setPreview(asset);
      setAlt("");
      onUploaded?.(asset);
      showToast("Uploaded");
    } catch (e) {
      const msg = e instanceof ApiError ? String(e.detail) : "upload failed";
      showToast(`Upload failed: ${msg}`);
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const onPick = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) submit(f);
  };

  const onDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (disabled || busy) return;
    const f = e.dataTransfer.files?.[0];
    if (f) submit(f);
  };

  return (
    <div className="ta-media-upload">
      <input
        ref={fileRef}
        type="file"
        accept="image/png,image/jpeg,image/webp,image/gif,image/svg+xml"
        onChange={onPick}
        disabled={disabled || busy}
        style={{ display: "none" }}
      />
      <div
        className="ta-media-upload-zone"
        onDragOver={(e) => e.preventDefault()}
        onDrop={onDrop}
        onClick={() => !disabled && !busy && fileRef.current?.click()}
        role="button"
        tabIndex={0}
      >
        {busy ? "Uploading…" : "Drop an image or click to pick"}
        <div className="ta-media-upload-hint">PNG, JPEG, WebP, GIF, SVG · up to 10 MB</div>
      </div>
      <input
        className="ta-form-input"
        value={alt}
        onChange={(e) => setAlt(e.target.value)}
        placeholder={altPlaceholder}
        disabled={disabled || busy}
        style={{ marginTop: 8 }}
      />
      {preview && (
        <div className="ta-media-upload-preview">
          <img src={preview.url} alt={preview.alt_text || preview.filename} />
          <div className="ta-media-upload-preview-meta">
            <div>{preview.filename}</div>
            <div style={{ color: "var(--ta-text-faint)", fontSize: 11 }}>
              {Math.round(preview.size_bytes / 1024)} KB
              {preview.uploaded_by_name ? ` · by ${preview.uploaded_by_name}` : ""}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
