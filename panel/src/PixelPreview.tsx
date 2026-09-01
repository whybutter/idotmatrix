import { useEffect, useRef } from "react";

/**
 * WYSIWYG preview of what the panel will actually show.
 *
 * A plain <img> is misleading: the panel is only 16-64 pixels square, so fine
 * detail, thin strokes and small text simply vanish. This renders the real
 * downscale — the same fit-to-square the backend does before upload — and
 * scales it back up with hard pixel edges.
 *
 * Deliberately does NOT apply the panel's gamma / white-balance correction.
 * That correction exists to make the panel reproduce sRGB faithfully, so
 * applying it here — on an already-sRGB monitor — would double-correct and show
 * a dark, yellow-shifted image that looks nothing like the panel. Resolution is
 * the honest difference to preview; colour is meant to come out unchanged.
 *
 * Animated GIFs are decoded frame by frame with WebCodecs' ImageDecoder.
 * Canvas drawImage() on an animated <img> always yields the FIRST frame in
 * Chrome (verified), so there is no cheaper way to animate the preview.
 * Where ImageDecoder is unavailable it falls back to a still first frame.
 */
export function PixelPreview({
  src,
  size,
  display = 140,
  className,
}: {
  src: string;
  /** Panel resolution the image will be sent at. */
  size: 16 | 32 | 64;
  /** On-screen size in CSS pixels. */
  display?: number;
  className?: string;
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !src) return;

    // Integer upscale keeps every panel pixel the same size on screen.
    const zoom = Math.max(1, Math.round(display / size));
    canvas.width = canvas.height = size * zoom;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Offscreen buffer at the true panel resolution — this is where the detail
    // is actually lost, exactly as it will be on the device.
    const small = document.createElement("canvas");
    small.width = small.height = size;
    const sctx = small.getContext("2d");
    if (!sctx) return;

    let cancelled = false;
    let timer: number | undefined;

    // Match the backend's resampling: GIF frames go through _fit_rgb with
    // pixel_art=True (NEAREST, hard edges); stills use LANCZOS (smooth). Canvas
    // smooths by default, so nearest has to be asked for explicitly.
    const paint = (frame: CanvasImageSource, w: number, h: number, nearest = false) => {
      sctx.imageSmoothingEnabled = !nearest;
      // Fit to square on black, matching the backend's _fit_rgb.
      const scale = Math.min(size / w, size / h) || 1;
      const dw = Math.max(1, Math.round(w * scale));
      const dh = Math.max(1, Math.round(h * scale));
      sctx.fillStyle = "#000";
      sctx.fillRect(0, 0, size, size);
      sctx.drawImage(frame, ((size - dw) / 2) | 0, ((size - dh) / 2) | 0, dw, dh);

      ctx.imageSmoothingEnabled = false;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(small, 0, 0, size, size, 0, 0, canvas.width, canvas.height);
    };

    const still = () => {
      const img = new Image();
      img.crossOrigin = "anonymous";
      img.onload = () => {
        if (!cancelled) paint(img, img.width, img.height);
      };
      img.src = src;
    };

    (async () => {
      const AnyWin = window as unknown as { ImageDecoder?: new (i: object) => any };
      if (!AnyWin.ImageDecoder) return still();
      let decoder: { decode: Function; close: Function; tracks: any; completed: Promise<void> };
      try {
        const res = await fetch(src);
        const data = await res.arrayBuffer();
        if (cancelled) return;
        const type = res.headers.get("content-type") || "image/gif";
        decoder = new AnyWin.ImageDecoder({ data, type });
        await decoder.tracks.ready;
        await decoder.completed;
      } catch {
        return still(); // not decodable (CORS, unsupported type) — show a still
      }
      if (cancelled) return decoder!.close();

      const track = decoder.tracks.selectedTrack;
      if (!track?.animated || track.frameCount < 2) {
        decoder.close();
        return still();
      }

      let i = 0;
      const play = async () => {
        if (cancelled) return;
        try {
          const { image } = await decoder.decode({ frameIndex: i % track.frameCount });
          if (cancelled) return image.close();
          paint(image, image.displayWidth, image.displayHeight, true);
          // VideoFrame.duration is microseconds; clamp so a 0-delay GIF can't
          // spin the event loop.
          const ms = Math.max(30, (image.duration ?? 100000) / 1000);
          image.close();
          i++;
          timer = window.setTimeout(play, ms);
        } catch {
          /* decoder closed mid-flight */
        }
      };
      play();
    })();

    return () => {
      cancelled = true;
      if (timer !== undefined) clearTimeout(timer);
    };
  }, [src, size, display]);

  return (
    <canvas
      ref={canvasRef}
      className={className ?? "idot-pixel-preview"}
      style={{ width: display, height: display }}
    />
  );
}
