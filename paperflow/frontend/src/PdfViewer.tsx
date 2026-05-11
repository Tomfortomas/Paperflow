/**
 * Lightweight PDF.js viewer with page jump, bbox highlight, and select-to-ask.
 *
 * The component is intentionally minimal — it renders one page at a time on a
 * <canvas> with a transparent text layer above it so the user can select text
 * with the mouse. The selection is bubbled up via `onSelection` and Paperflow
 * sends it to the backend's `/ask-selection` endpoint.
 *
 * PDF.js is loaded with a dynamic import so that:
 *   1. SSR / jsdom test environments don't choke on its worker setup.
 *   2. Vite can code-split the heavy worker bundle.
 */

import { useEffect, useRef, useState } from "react";

export interface PdfBboxHighlight {
  page: number;
  bbox: [number, number, number, number]; // [x0, y0, x1, y1] in PDF points
}

interface PdfViewerProps {
  pdfUrl: string;
  page: number;
  highlight?: PdfBboxHighlight | null;
  pageSizes?: number[][]; // optional [[w, h], ...] in PDF points
  scale?: number;
  onSelection?: (quote: string, page: number) => void;
  onPageChange?: (page: number) => void;
}

export function PdfViewer({
  pdfUrl,
  page,
  highlight,
  pageSizes,
  scale = 1.25,
  onSelection,
  onPageChange,
}: PdfViewerProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const textLayerRef = useRef<HTMLDivElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [pdfModule, setPdfModule] = useState<typeof import("pdfjs-dist") | null>(null);
  const [pdfDoc, setPdfDoc] = useState<import("pdfjs-dist").PDFDocumentProxy | null>(null);
  const [numPages, setNumPages] = useState(0);
  const [renderedSize, setRenderedSize] = useState<{ width: number; height: number } | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Load PDF.js + the document once per pdfUrl.
  useEffect(() => {
    let cancelled = false;
    setError(null);
    setPdfDoc(null);
    setNumPages(0);

    (async () => {
      try {
        const lib = await import("pdfjs-dist");
        if (cancelled) return;
        const workerUrl = await import("pdfjs-dist/build/pdf.worker.min.mjs?url").then(
          (m) => m.default,
        );
        lib.GlobalWorkerOptions.workerSrc = workerUrl;
        setPdfModule(lib);

        const task = lib.getDocument({ url: pdfUrl, withCredentials: false });
        const doc = await task.promise;
        if (cancelled) {
          doc.destroy();
          return;
        }
        setPdfDoc(doc);
        setNumPages(doc.numPages);
      } catch (caught) {
        if (!cancelled) {
          setError(caught instanceof Error ? caught.message : "Failed to load PDF");
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [pdfUrl]);

  // Render the active page whenever pdfDoc or `page` changes.
  useEffect(() => {
    if (!pdfDoc || !pdfModule || !canvasRef.current) {
      return;
    }
    const safePage = Math.max(1, Math.min(page, numPages || page));
    let cancelled = false;

    (async () => {
      try {
        const pdfPage = await pdfDoc.getPage(safePage);
        if (cancelled) return;
        const viewport = pdfPage.getViewport({ scale });

        const canvas = canvasRef.current!;
        const context = canvas.getContext("2d");
        if (!context) return;
        canvas.width = Math.floor(viewport.width);
        canvas.height = Math.floor(viewport.height);
        canvas.style.width = `${viewport.width}px`;
        canvas.style.height = `${viewport.height}px`;
        setRenderedSize({ width: viewport.width, height: viewport.height });

        await pdfPage.render({ canvasContext: context, viewport }).promise;

        // Render the text layer so the user can select.
        const textLayer = textLayerRef.current;
        if (textLayer) {
          textLayer.innerHTML = "";
          textLayer.style.width = `${viewport.width}px`;
          textLayer.style.height = `${viewport.height}px`;
          const textContent = await pdfPage.getTextContent();
          // pdfjs-dist v4 exports renderTextLayer at runtime even though the
          // type stub is missing — cast to any to keep TypeScript happy.
          const renderTextLayer = (pdfModule as unknown as {
            renderTextLayer?: (params: Record<string, unknown>) => unknown;
          }).renderTextLayer;
          if (typeof renderTextLayer === "function") {
            renderTextLayer({
              textContentSource: textContent,
              container: textLayer,
              viewport,
              textDivs: [],
            });
          }
        }
      } catch (caught) {
        if (!cancelled) {
          setError(caught instanceof Error ? caught.message : "Failed to render page");
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [pdfDoc, pdfModule, page, scale, numPages]);

  // Highlight rectangle (PDF points → canvas px).
  const highlightStyle = (() => {
    if (!highlight || highlight.page !== page || !renderedSize) {
      return null;
    }
    const [, , , pageHeight] = effectivePageBbox(highlight, pageSizes, renderedSize, scale);
    const [x0, y0, x1, y1] = highlight.bbox;
    // PDF.js viewport y is already top-down in canvas space so we use bbox directly.
    return {
      left: x0 * scale,
      top: y0 * scale,
      width: Math.max(2, (x1 - x0) * scale),
      height: Math.max(2, (y1 - y0) * scale),
      maxHeight: pageHeight,
    };
  })();

  function handleMouseUp() {
    if (!onSelection) return;
    const selection = window.getSelection();
    const value = selection?.toString().trim();
    if (value && value.length > 2) {
      onSelection(value, page);
    }
  }

  return (
    <div className="pdf-viewer" ref={containerRef}>
      <div className="pdf-viewer-toolbar">
        <button
          type="button"
          onClick={() => onPageChange?.(Math.max(1, page - 1))}
          disabled={page <= 1}
        >
          ‹ Prev
        </button>
        <span className="pdf-viewer-page-indicator">
          Page {page}
          {numPages ? ` / ${numPages}` : ""}
        </span>
        <button
          type="button"
          onClick={() => onPageChange?.(Math.min(numPages || page + 1, page + 1))}
          disabled={numPages > 0 && page >= numPages}
        >
          Next ›
        </button>
      </div>
      {error ? (
        <p className="warning">{error}</p>
      ) : (
        <div className="pdf-viewer-canvas-wrap" onMouseUp={handleMouseUp}>
          <canvas ref={canvasRef} className="pdf-viewer-canvas" />
          <div ref={textLayerRef} className="pdf-viewer-text-layer" />
          {highlightStyle ? (
            <div className="pdf-viewer-highlight" style={highlightStyle} aria-hidden />
          ) : null}
        </div>
      )}
    </div>
  );
}

function effectivePageBbox(
  highlight: PdfBboxHighlight,
  _pageSizes: number[][] | undefined,
  renderedSize: { width: number; height: number },
  _scale: number,
): [number, number, number, number] {
  // Currently unused but reserved for non-uniform-page support: returns the
  // rendered page size so the highlight can be clipped to the visible canvas.
  return [0, 0, renderedSize.width, renderedSize.height];
}
