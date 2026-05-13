/**
 * Lightweight PDF.js viewer with continuous scrolling, page jump, bbox
 * highlight, and select-to-ask.
 *
 * PDF.js is loaded with a dynamic import so that:
 *   1. SSR / jsdom test environments don't choke on its worker setup.
 *   2. Vite can code-split the heavy worker bundle.
 */

import {
  type FormEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

export interface PdfBboxHighlight {
  page: number;
  bbox?: [number, number, number, number] | null; // [x0, y0, x1, y1] in PDF points
  quote?: string | null;
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
type PdfRenderTask = {
  promise: Promise<unknown>;
  cancel?: () => void;
};
type HighlightStyle = {
  left: number;
  top: number;
  width: number;
  height: number;
  maxHeight?: number;
};

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
  const toolbarRef = useRef<HTMLDivElement | null>(null);
  const pagesRef = useRef<HTMLDivElement | null>(null);
  const pageRefs = useRef(new Map<number, HTMLElement>());
  const observedPageRef = useRef(page);
  const scrollRafRef = useRef<number | null>(null);
  const skipNextPageScrollRef = useRef<number | null>(null);
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
    if (skipNextPageScrollRef.current === safePage) {
      skipNextPageScrollRef.current = null;
      observedPageRef.current = safePage;
      return;
    }
    observedPageRef.current = safePage;
    scrollToPage(safePage, "auto");
  }, [safePage, numPages, zoom]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const handleScroll = () => {
      if (scrollRafRef.current !== null) {
        window.cancelAnimationFrame(scrollRafRef.current);
      }
      scrollRafRef.current = window.requestAnimationFrame(() => {
        scrollRafRef.current = null;
        const visiblePage = getVisiblePage(
          container,
          pageRefs.current,
          toolbarRef.current?.offsetHeight ?? 0,
        );
        if (!visiblePage || visiblePage === observedPageRef.current) {
          return;
        }
        observedPageRef.current = visiblePage;
        skipNextPageScrollRef.current = visiblePage;
        setPageInput(String(visiblePage));
        onPageChange?.(visiblePage);
      });
    };

    container.addEventListener("scroll", handleScroll, { passive: true });
    return () => {
      container.removeEventListener("scroll", handleScroll);
      if (scrollRafRef.current !== null) {
        window.cancelAnimationFrame(scrollRafRef.current);
        scrollRafRef.current = null;
      }
    };
  }, [onPageChange, numPages]);

  function scrollToPage(targetPage: number, behavior: ScrollBehavior = "smooth") {
    const container = containerRef.current;
    const element = pageRefs.current.get(targetPage);
    if (!container || !element) return;
    window.requestAnimationFrame(() => {
      scrollElementIntoContainer(container, element, {
        behavior,
        block: "start",
        inline: "center",
        topOffset: (toolbarRef.current?.offsetHeight ?? 0) + 8,
      });
    });
  }

  function scrollToHighlight(element: HTMLElement) {
    const container = containerRef.current;
    if (!container) return;
    window.requestAnimationFrame(() => {
      scrollElementIntoContainer(container, element, {
        behavior: "smooth",
        block: "center",
        inline: "center",
      });
    });
  }

  function goToPage(targetPage: number) {
    const nextPage = clampPage(targetPage, numPages || targetPage);
    setPageInput(String(nextPage));
    observedPageRef.current = nextPage;
    skipNextPageScrollRef.current = nextPage;
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

  function bumpZoomSlightly(current: string): string {
    if (current === "fit") return "110";
    const n = Number(current);
    if (!Number.isFinite(n)) return "110";
    if (n < 110) return "110";
    if (n < 125) return "125";
    if (n < 150) return "150";
    if (n < 175) return "175";
    if (n < 200) return "200";
    return "200";
  }

  function bumpZoomSmaller(current: string): string {
    if (current === "fit") return "fit";
    const n = Number(current);
    if (!Number.isFinite(n)) return "fit";
    if (n >= 200) return "175";
    if (n >= 175) return "150";
    if (n >= 150) return "125";
    if (n >= 125) return "110";
    if (n >= 110) return "fit";
    return "fit";
  }

  return (
    <div className="pdf-viewer" ref={containerRef}>
      <div className="pdf-viewer-toolbar" ref={toolbarRef}>
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
        <div className="pdf-viewer-zoom">
          <span>Zoom</span>
          <button
            type="button"
            className="pdf-viewer-zoom-step"
            aria-label="Slightly shrink PDF"
            disabled={zoom === "fit"}
            title="Step down zoom: 200% → … → Fit"
            onClick={() => setZoom((z) => bumpZoomSmaller(z))}
          >
            −
          </button>
          <button
            type="button"
            className="pdf-viewer-zoom-step"
            aria-label="Slightly enlarge PDF"
            disabled={zoom === "200"}
            title="Step up zoom: Fit → 110% → … → 200%"
            onClick={() => setZoom((z) => bumpZoomSlightly(z))}
          >
            +
          </button>
          <select
            aria-label="PDF zoom"
            value={zoom}
            onChange={(event) => setZoom(event.target.value)}
          >
            <option value="fit">Fit</option>
            <option value="100">100%</option>
            <option value="110">110%</option>
            <option value="125">125%</option>
            <option value="150">150%</option>
            <option value="175">175%</option>
            <option value="200">200%</option>
          </select>
        </div>
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
                onHighlightElement={scrollToHighlight}
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
  onHighlightElement,
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
  onHighlightElement: (element: HTMLElement) => void;
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
  const lastScrolledHighlightKeyRef = useRef<string | null>(null);
  const [renderedSize, setRenderedSize] = useState<{ width: number; height: number } | null>(null);
  const [renderedScale, setRenderedScale] = useState(1);
  const [textMatchStyle, setTextMatchStyle] = useState<HighlightStyle | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    onPageElement(pageRef.current);
    return () => onPageElement(null);
  }, [onPageElement]);

  useEffect(() => {
    if (!canvasRef.current) return;
    let cancelled = false;
    let renderTask: PdfRenderTask | null = null;

    (async () => {
      try {
        setError(null);
        setTextMatchStyle(null);
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

        renderTask = pdfPage.render({
          canvasContext: context,
          viewport,
          transform: outputScale === 1 ? undefined : [outputScale, 0, 0, outputScale, 0, 0],
        }) as PdfRenderTask;
        await renderTask.promise;
        renderTask = null;
        if (cancelled) return;

        const textLayer = textLayerRef.current;
        if (textLayer) {
          textLayer.innerHTML = "";
          textLayer.style.width = `${viewport.width}px`;
          textLayer.style.height = `${viewport.height}px`;
          const textContent = await pdfPage.getTextContent();
          if (cancelled) return;
          if (highlight?.page === pageNumber && !highlight.bbox && highlight.quote) {
            setTextMatchStyle(findTextHighlightStyle(textContent, highlight.quote, viewport));
          }
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
        if (!cancelled && !isPdfRenderCancelled(caught)) {
          setError(caught instanceof Error ? caught.message : "Failed to render page");
        }
      }
    })();

    return () => {
      cancelled = true;
      try {
        renderTask?.cancel?.();
      } catch {
        // PDF.js can throw if the task has already settled; cleanup should stay silent.
      }
    };
  }, [containerWidth, highlight, maxFitScale, pageNumber, pdfDoc, pdfModule, zoom]);

  const highlightStyle: HighlightStyle | null = (() => {
    if (!highlight || highlight.page !== pageNumber || !renderedSize) {
      return null;
    }
    if (!highlight.bbox) {
      return textMatchStyle;
    }
    const [, , , pageHeight] = effectivePageBbox(pageSizes, renderedSize);
    const [x0, y0, x1, y1] = highlight.bbox;
    return {
      left: x0 * renderedScale,
      top: y0 * renderedScale,
      width: Math.max(2, (x1 - x0) * renderedScale),
      height: Math.max(2, (y1 - y0) * renderedScale),
      maxHeight: pageHeight,
    };
  })();
  const highlightScrollKey =
    highlight && highlight.page === pageNumber && renderedSize && highlightStyle
      ? [
          highlight.page,
          highlight.bbox?.join(",") ?? normalizeTextForMatch(highlight.quote ?? "").slice(0, 80),
          renderedScale,
          renderedSize.width,
          renderedSize.height,
          Math.round(highlightStyle.left),
          Math.round(highlightStyle.top),
        ].join(":")
      : null;

  useEffect(() => {
    if (!highlightScrollKey || !highlightRef.current) {
      return;
    }
    if (lastScrolledHighlightKeyRef.current === highlightScrollKey) {
      return;
    }
    lastScrolledHighlightKeyRef.current = highlightScrollKey;
    onHighlightElement(highlightRef.current);
  }, [highlightScrollKey]);

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
        {highlightStyle && highlightScrollKey ? (
          <div
            key={highlightScrollKey}
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

function isPdfRenderCancelled(value: unknown): boolean {
  return (
    value instanceof Error &&
    (value.name === "RenderingCancelledException" ||
      value.message.toLowerCase().includes("cancelled"))
  );
}

function scrollableExtent(element: HTMLElement): { top: number; left: number } {
  return {
    top: Math.max(0, element.scrollHeight - element.clientHeight),
    left: Math.max(0, element.scrollWidth - element.clientWidth),
  };
}

function clampScroll(value: number, maxValue: number): number {
  return Math.max(0, Math.min(value, maxValue));
}

function scrollElementIntoContainer(
  container: HTMLElement,
  element: HTMLElement,
  {
    behavior,
    block,
    inline,
    topOffset = 0,
  }: {
    behavior: ScrollBehavior;
    block: "start" | "center";
    inline: "center";
    topOffset?: number;
  },
) {
  const containerRect = container.getBoundingClientRect();
  const elementRect = element.getBoundingClientRect();
  const extent = scrollableExtent(container);
  let top = container.scrollTop + elementRect.top - containerRect.top;
  if (block === "center") {
    top -= (container.clientHeight - elementRect.height) / 2;
  } else {
    top -= topOffset;
  }
  const left =
    container.scrollLeft +
    elementRect.left -
    containerRect.left -
    (container.clientWidth - elementRect.width) / 2;

  scrollContainerTo(container, {
    top: clampScroll(top, extent.top),
    left: clampScroll(left, extent.left),
    behavior,
  });
}

function scrollContainerTo(
  container: HTMLElement,
  options: { top: number; left: number; behavior: ScrollBehavior },
) {
  if (typeof container.scrollTo === "function") {
    container.scrollTo(options);
    return;
  }
  container.scrollTop = options.top;
  container.scrollLeft = options.left;
}

function getVisiblePage(
  container: HTMLElement,
  pageRefs: Map<number, HTMLElement>,
  toolbarHeight: number,
): number | null {
  const containerRect = container.getBoundingClientRect();
  const readingLine = containerRect.top + toolbarHeight + 12;
  const entries = Array.from(pageRefs.entries()).sort(([a], [b]) => a - b);
  let closest: { page: number; distance: number } | null = null;

  for (const [pageNumber, element] of entries) {
    const rect = element.getBoundingClientRect();
    if (rect.bottom >= readingLine && rect.top <= containerRect.bottom) {
      return pageNumber;
    }
    const distance = Math.abs(rect.top - readingLine);
    if (!closest || distance < closest.distance) {
      closest = { page: pageNumber, distance };
    }
  }

  return closest?.page ?? null;
}

function findTextHighlightStyle(
  textContent: unknown,
  quote: string,
  viewport: unknown,
): HighlightStyle | null {
  const needle = normalizeTextForMatch(quote).slice(0, 240);
  if (needle.length < 8) {
    return null;
  }

  const items = ((textContent as { items?: unknown[] })?.items ?? [])
    .map((item, index) => textItemRect(item, viewport, index))
    .filter((item): item is TextItemRect => item !== null);
  if (items.length === 0) {
    return null;
  }

  const haystack: string[] = [];
  const indexToItem: number[] = [];
  items.forEach((item, itemIndex) => {
    for (const char of normalizeTextForMatch(item.text)) {
      haystack.push(char);
      indexToItem.push(itemIndex);
    }
  });

  const start = haystack.join("").indexOf(needle);
  if (start < 0) {
    return null;
  }
  const end = start + needle.length - 1;
  const firstItem = indexToItem[start];
  const lastItem = indexToItem[end];
  if (firstItem === undefined || lastItem === undefined) {
    return null;
  }

  const matchedItems = items.slice(firstItem, lastItem + 1);
  const left = Math.min(...matchedItems.map((item) => item.left));
  const top = Math.min(...matchedItems.map((item) => item.top));
  const right = Math.max(...matchedItems.map((item) => item.left + item.width));
  const bottom = Math.max(...matchedItems.map((item) => item.top + item.height));
  return {
    left: Math.max(0, left - 2),
    top: Math.max(0, top - 2),
    width: Math.max(2, right - left + 4),
    height: Math.max(2, bottom - top + 4),
  };
}

function textItemRect(item: unknown, viewport: unknown, index: number): TextItemRect | null {
  const text = typeof (item as { str?: unknown }).str === "string" ? (item as { str: string }).str : "";
  const transform = (item as { transform?: unknown }).transform;
  if (!text.trim() || !Array.isArray(transform) || transform.length < 6) {
    return null;
  }

  const x = Number(transform[4]);
  const y = Number(transform[5]);
  const width = Number((item as { width?: unknown }).width ?? 0);
  const height = Math.abs(Number((item as { height?: unknown }).height ?? transform[3] ?? 10));
  if (![x, y, width, height].every(Number.isFinite)) {
    return null;
  }

  const rect = [x, y, x + Math.max(1, width), y + Math.max(1, height)];
  const converter = (viewport as {
    convertToViewportRectangle?: (rect: number[]) => number[];
  })?.convertToViewportRectangle;
  const converted = typeof converter === "function" ? converter.call(viewport, rect) : rect;
  const [x0, y0, x1, y1] = converted.map(Number);
  if (![x0, y0, x1, y1].every(Number.isFinite)) {
    return null;
  }

  return {
    text,
    index,
    left: Math.min(x0, x1),
    top: Math.min(y0, y1),
    width: Math.max(1, Math.abs(x1 - x0)),
    height: Math.max(1, Math.abs(y1 - y0)),
  };
}

function normalizeTextForMatch(value: string): string {
  return value.toLowerCase().replace(/\s+/g, "");
}

function effectivePageBbox(
  _pageSizes: number[][] | undefined,
  renderedSize: { width: number; height: number },
): [number, number, number, number] {
  return [0, 0, renderedSize.width, renderedSize.height];
}

interface TextItemRect {
  text: string;
  index: number;
  left: number;
  top: number;
  width: number;
  height: number;
}
