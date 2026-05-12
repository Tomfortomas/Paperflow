/**
 * Lightweight PDF.js viewer with continuous scrolling, page jump, bbox
 * highlight, and select-to-ask.
 *
 * PDF.js is loaded with a dynamic import so that:
 *   1. SSR / jsdom test environments don't choke on its worker setup.
 *   2. Vite can code-split the heavy worker bundle.
 */

import { type FormEvent, useEffect, useMemo, useRef, useState } from "react";

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

type PdfModule = typeof import("pdfjs-dist");
type PdfDocument = import("pdfjs-dist").PDFDocumentProxy;

export function PdfViewer({
  pdfUrl,
  page,
  highlight,
  pageSizes,
  scale = 1.4,
  onSelection,
  onPageChange,
}: PdfViewerProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const pagesRef = useRef<HTMLDivElement | null>(null);
  const pageRefs = useRef(new Map<number, HTMLElement>());
  const [pdfModule, setPdfModule] = useState<PdfModule | null>(null);
  const [pdfDoc, setPdfDoc] = useState<PdfDocument | null>(null);
  const [numPages, setNumPages] = useState(0);
  const [containerWidth, setContainerWidth] = useState(0);
  const [pageInput, setPageInput] = useState(String(page));
  const [zoom, setZoom] = useState("fit");
  const [error, setError] = useState<string | null>(null);

  const safePage = clampPage(page, numPages || page);
  const pageNumbers = useMemo(
    () => Array.from({ length: numPages }, (_, index) => index + 1),
    [numPages],
  );

  useEffect(() => {
    let cancelled = false;
    setError(null);
    setPdfDoc(null);
    setNumPages(0);
    pageRefs.current.clear();

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

  useEffect(() => {
    const element = containerRef.current;
    if (!element) return;

    const updateWidth = () => setContainerWidth(element.clientWidth);
    updateWidth();

    if (typeof ResizeObserver === "undefined") {
      window.addEventListener("resize", updateWidth);
      return () => window.removeEventListener("resize", updateWidth);
    }

    const observer = new ResizeObserver(updateWidth);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    setPageInput(String(safePage));
  }, [safePage]);

  useEffect(() => {
    scrollToPage(safePage, "auto");
  }, [safePage, numPages, zoom]);

  function scrollToPage(targetPage: number, behavior: ScrollBehavior = "smooth") {
    const element = pageRefs.current.get(targetPage);
    if (!element) return;
    window.requestAnimationFrame(() => {
      element.scrollIntoView({ block: "start", inline: "center", behavior });
    });
  }

  function goToPage(targetPage: number) {
    const nextPage = clampPage(targetPage, numPages || targetPage);
    setPageInput(String(nextPage));
    onPageChange?.(nextPage);
    scrollToPage(nextPage);
  }

  function handlePageSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parsed = Number.parseInt(pageInput, 10);
    if (!Number.isFinite(parsed)) {
      setPageInput(String(safePage));
      return;
    }
    goToPage(parsed);
  }

  return (
    <div className="pdf-viewer" ref={containerRef}>
      <div className="pdf-viewer-toolbar">
        <button
          type="button"
          onClick={() => goToPage(safePage - 1)}
          disabled={safePage <= 1}
        >
          ‹ Prev
        </button>
        <span className="pdf-viewer-page-indicator">
          Page {safePage}
          {numPages ? ` / ${numPages}` : ""}
        </span>
        <form className="pdf-viewer-page-form" onSubmit={handlePageSubmit}>
          <label>
            <span>PDF page</span>
            <input
              aria-label="PDF page"
              inputMode="numeric"
              min={1}
              max={numPages || undefined}
              value={pageInput}
              onChange={(event) => setPageInput(event.target.value)}
            />
          </label>
          <button type="submit">Go</button>
        </form>
        <button
          type="button"
          onClick={() => goToPage(safePage + 1)}
          disabled={numPages > 0 && safePage >= numPages}
        >
          Next ›
        </button>
        <label className="pdf-viewer-zoom">
          <span>Zoom</span>
          <select
            aria-label="PDF zoom"
            value={zoom}
            onChange={(event) => setZoom(event.target.value)}
          >
            <option value="fit">Fit</option>
            <option value="100">100%</option>
            <option value="125">125%</option>
            <option value="150">150%</option>
          </select>
        </label>
      </div>
      {error ? <p className="warning">{error}</p> : null}
      <div className="pdf-viewer-pages" ref={pagesRef} aria-label="PDF pages">
        {pdfDoc && pdfModule
          ? pageNumbers.map((pageNumber) => (
              <PdfPage
                containerWidth={containerWidth}
                highlight={highlight}
                key={pageNumber}
                maxFitScale={scale}
                onPageElement={(element) => {
                  if (element) {
                    pageRefs.current.set(pageNumber, element);
                  } else {
                    pageRefs.current.delete(pageNumber);
                  }
                }}
                onSelection={onSelection}
                pageNumber={pageNumber}
                pageSizes={pageSizes}
                pdfDoc={pdfDoc}
                pdfModule={pdfModule}
                zoom={zoom}
              />
            ))
          : null}
      </div>
    </div>
  );
}

function PdfPage({
  containerWidth,
  highlight,
  maxFitScale,
  onPageElement,
  onSelection,
  pageNumber,
  pageSizes,
  pdfDoc,
  pdfModule,
  zoom,
}: {
  containerWidth: number;
  highlight?: PdfBboxHighlight | null;
  maxFitScale: number;
  onPageElement: (element: HTMLElement | null) => void;
  onSelection?: (quote: string, page: number) => void;
  pageNumber: number;
  pageSizes?: number[][];
  pdfDoc: PdfDocument;
  pdfModule: PdfModule;
  zoom: string;
}) {
  const pageRef = useRef<HTMLDivElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const textLayerRef = useRef<HTMLDivElement | null>(null);
  const highlightRef = useRef<HTMLDivElement | null>(null);
  const [renderedSize, setRenderedSize] = useState<{ width: number; height: number } | null>(null);
  const [renderedScale, setRenderedScale] = useState(1);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    onPageElement(pageRef.current);
    return () => onPageElement(null);
  }, [onPageElement]);

  useEffect(() => {
    if (!canvasRef.current) return;
    let cancelled = false;

    (async () => {
      try {
        setError(null);
        const pdfPage = await pdfDoc.getPage(pageNumber);
        if (cancelled) return;
        const naturalViewport = pdfPage.getViewport({ scale: 1 });
        const requestedScale =
          zoom === "fit"
            ? scaleForContainer(containerWidth, naturalViewport.width)
            : Number(zoom) / 100;
        const fitScale = zoom === "fit" ? Math.min(maxFitScale, requestedScale) : requestedScale;
        const viewport = pdfPage.getViewport({ scale: fitScale });
        const outputScale = Math.max(1, window.devicePixelRatio || 1);

        const canvas = canvasRef.current;
        const context = canvas?.getContext("2d");
        if (!canvas || !context) return;
        canvas.width = Math.floor(viewport.width * outputScale);
        canvas.height = Math.floor(viewport.height * outputScale);
        canvas.style.width = `${viewport.width}px`;
        canvas.style.height = `${viewport.height}px`;
        setRenderedSize({ width: viewport.width, height: viewport.height });
        setRenderedScale(fitScale);

        await pdfPage.render({
          canvasContext: context,
          viewport,
          transform: outputScale === 1 ? undefined : [outputScale, 0, 0, outputScale, 0, 0],
        }).promise;

        const textLayer = textLayerRef.current;
        if (textLayer) {
          textLayer.innerHTML = "";
          textLayer.style.width = `${viewport.width}px`;
          textLayer.style.height = `${viewport.height}px`;
          const textContent = await pdfPage.getTextContent();
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
  }, [containerWidth, maxFitScale, pageNumber, pdfDoc, pdfModule, zoom]);

  const highlightStyle = (() => {
    if (!highlight || highlight.page !== pageNumber || !renderedSize) {
      return null;
    }
    const [, , , pageHeight] = effectivePageBbox(highlight, pageSizes, renderedSize);
    const [x0, y0, x1, y1] = highlight.bbox;
    return {
      left: x0 * renderedScale,
      top: y0 * renderedScale,
      width: Math.max(2, (x1 - x0) * renderedScale),
      height: Math.max(2, (y1 - y0) * renderedScale),
      maxHeight: pageHeight,
    };
  })();

  useEffect(() => {
    if (!highlightStyle || !highlightRef.current) return;
    window.requestAnimationFrame(() => {
      highlightRef.current?.scrollIntoView({ block: "center", inline: "center" });
    });
  }, [highlightStyle]);

  function handleMouseUp() {
    if (!onSelection) return;
    const selection = window.getSelection();
    const value = selection?.toString().trim();
    if (value && value.length > 2) {
      onSelection(value, pageNumber);
    }
  }

  return (
    <article className="pdf-viewer-page" data-page={pageNumber} ref={pageRef}>
      <div className="pdf-viewer-page-label">Page {pageNumber}</div>
      {error ? <p className="warning">{error}</p> : null}
      <div className="pdf-viewer-canvas-wrap" onMouseUp={handleMouseUp}>
        <canvas ref={canvasRef} className="pdf-viewer-canvas" />
        <div ref={textLayerRef} className="pdf-viewer-text-layer" />
        {highlightStyle ? (
          <div
            className="pdf-viewer-highlight"
            ref={highlightRef}
            style={highlightStyle}
            aria-hidden
          />
        ) : null}
      </div>
    </article>
  );
}

function scaleForContainer(containerWidth: number, pageWidth: number): number {
  if (containerWidth <= 0 || pageWidth <= 0) {
    return 1.4;
  }
  return Math.max(0.72, (containerWidth - 2) / pageWidth);
}

function clampPage(value: number, maxPage: number): number {
  return Math.max(1, Math.min(value, Math.max(1, maxPage)));
}

function effectivePageBbox(
  _highlight: PdfBboxHighlight,
  _pageSizes: number[][] | undefined,
  renderedSize: { width: number; height: number },
): [number, number, number, number] {
  return [0, 0, renderedSize.width, renderedSize.height];
}
