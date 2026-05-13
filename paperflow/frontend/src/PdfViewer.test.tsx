import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PdfViewer } from "./PdfViewer";

const pdfPage = {
  getViewport: ({ scale }: { scale: number }) => ({
    width: 600 * scale,
    height: 800 * scale,
  }),
  getTextContent: vi.fn(async () => ({ items: [] as unknown[] })),
  render: vi.fn(() => ({ promise: Promise.resolve(), cancel: vi.fn() })),
};

const pdfDocument = {
  numPages: 3,
  destroy: vi.fn(),
  getPage: vi.fn(async () => pdfPage),
};

vi.mock("pdfjs-dist", () => ({
  GlobalWorkerOptions: {},
  getDocument: vi.fn(() => ({ promise: Promise.resolve(pdfDocument) })),
  renderTextLayer: vi.fn(),
}));

vi.mock("pdfjs-dist/build/pdf.worker.min.mjs?url", () => ({
  default: "pdf.worker.js",
}));

describe("PdfViewer", () => {
  beforeEach(() => {
    pdfDocument.numPages = 3;
    pdfDocument.destroy.mockClear();
    pdfDocument.getPage.mockReset();
    pdfDocument.getPage.mockResolvedValue(pdfPage);
    pdfPage.getTextContent.mockReset();
    pdfPage.getTextContent.mockResolvedValue({ items: [] as unknown[] });
    pdfPage.render.mockReset();
    pdfPage.render.mockReturnValue({ promise: Promise.resolve(), cancel: vi.fn() });
    vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
      callback(0);
      return 1;
    });
    vi.stubGlobal("cancelAnimationFrame", vi.fn());
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockImplementation(
      () => ({}) as CanvasRenderingContext2D,
    );
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("lets users jump to a page and choose a zoom level", async () => {
    const user = userEvent.setup();
    const onPageChange = vi.fn();

    render(
      <PdfViewer
        pdfUrl="http://127.0.0.1:8000/paper.pdf"
        page={2}
        onPageChange={onPageChange}
      />,
    );

    expect(await screen.findByText("Page 1")).toBeInTheDocument();
    expect(screen.getByLabelText(/PDF pages/i)).toBeInTheDocument();

    await user.clear(screen.getByLabelText(/^PDF page$/i));
    await user.type(screen.getByLabelText(/^PDF page$/i), "7");
    await user.click(screen.getByRole("button", { name: /Go/i }));

    expect(onPageChange).toHaveBeenCalledWith(3);

    await user.selectOptions(screen.getByLabelText(/^PDF zoom$/i), "200");

    expect(screen.getByLabelText(/^PDF zoom$/i)).toHaveValue("200");
  });

  it("steps zoom up and down with − / + buttons", async () => {
    const user = userEvent.setup();

    render(<PdfViewer pdfUrl="http://127.0.0.1:8000/paper.pdf" page={1} />);

    await screen.findByText("Page 1");

    expect(screen.getByLabelText(/^PDF zoom$/i)).toHaveValue("fit");
    expect(screen.getByRole("button", { name: /Slightly shrink PDF/i })).toBeDisabled();

    await user.click(screen.getByRole("button", { name: /Slightly enlarge PDF/i }));
    expect(screen.getByLabelText(/^PDF zoom$/i)).toHaveValue("110");

    await user.click(screen.getByRole("button", { name: /Slightly enlarge PDF/i }));
    expect(screen.getByLabelText(/^PDF zoom$/i)).toHaveValue("125");

    await user.click(screen.getByRole("button", { name: /Slightly enlarge PDF/i }));
    expect(screen.getByLabelText(/^PDF zoom$/i)).toHaveValue("150");

    await user.click(screen.getByRole("button", { name: /Slightly enlarge PDF/i }));
    expect(screen.getByLabelText(/^PDF zoom$/i)).toHaveValue("175");

    await user.click(screen.getByRole("button", { name: /Slightly enlarge PDF/i }));
    expect(screen.getByLabelText(/^PDF zoom$/i)).toHaveValue("200");

    expect(screen.getByRole("button", { name: /Slightly enlarge PDF/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Slightly shrink PDF/i })).not.toBeDisabled();

    await user.click(screen.getByRole("button", { name: /Slightly shrink PDF/i }));
    expect(screen.getByLabelText(/^PDF zoom$/i)).toHaveValue("175");

    await user.click(screen.getByRole("button", { name: /Slightly shrink PDF/i }));
    expect(screen.getByLabelText(/^PDF zoom$/i)).toHaveValue("150");

    await user.click(screen.getByRole("button", { name: /Slightly shrink PDF/i }));
    expect(screen.getByLabelText(/^PDF zoom$/i)).toHaveValue("125");

    await user.click(screen.getByRole("button", { name: /Slightly shrink PDF/i }));
    expect(screen.getByLabelText(/^PDF zoom$/i)).toHaveValue("110");

    await user.click(screen.getByRole("button", { name: /Slightly shrink PDF/i }));
    expect(screen.getByLabelText(/^PDF zoom$/i)).toHaveValue("fit");

    expect(screen.getByRole("button", { name: /Slightly shrink PDF/i })).toBeDisabled();
  });

  it("cancels an in-flight canvas render before repainting the same page", async () => {
    const user = userEvent.setup();
    const firstRender = deferred<void>();
    const cancelFirstRender = vi.fn(() => firstRender.resolve());
    pdfDocument.numPages = 1;
    pdfPage.render.mockReset();
    pdfPage.render
      .mockReturnValueOnce({ promise: firstRender.promise, cancel: cancelFirstRender })
      .mockReturnValue({ promise: Promise.resolve(), cancel: vi.fn() });

    render(<PdfViewer pdfUrl="http://127.0.0.1:8000/paper.pdf" page={1} />);

    await waitFor(() => expect(pdfPage.render).toHaveBeenCalledTimes(1));
    await user.selectOptions(screen.getByLabelText(/^PDF zoom$/i), "150");

    await waitFor(() => expect(cancelFirstRender).toHaveBeenCalledTimes(1));
  });

  it("jumps pages by scrolling the explicit viewer container", async () => {
    const user = userEvent.setup();
    const onPageChange = vi.fn();

    render(
      <PdfViewer
        pdfUrl="http://127.0.0.1:8000/paper.pdf"
        page={1}
        onPageChange={onPageChange}
      />,
    );

    const pages = screen.getByLabelText(/PDF pages/i) as HTMLDivElement;
    const viewer = pages.parentElement as HTMLDivElement;
    const page3 = await findPageArticle(3);
    const scrollTo = mockScrollableViewer(viewer);
    mockRect(viewer, { top: 0, bottom: 800, left: 0, right: 600, width: 600, height: 800 });
    mockRect(page3, { top: 1400, bottom: 2200, left: 40, right: 640, width: 600, height: 800 });

    await user.clear(screen.getByLabelText(/^PDF page$/i));
    await user.type(screen.getByLabelText(/^PDF page$/i), "3");
    await user.click(screen.getByRole("button", { name: /Go/i }));

    expect(onPageChange).toHaveBeenCalledWith(3);
    expect(scrollTo).toHaveBeenCalledWith(
      expect.objectContaining({ behavior: "smooth", top: expect.any(Number) }),
    );
    expect(viewer.scrollTop).toBeGreaterThan(0);
  });

  it("centers evidence highlights through the viewer container", async () => {
    const { rerender } = render(
      <PdfViewer pdfUrl="http://127.0.0.1:8000/paper.pdf" page={1} />,
    );

    const pages = screen.getByLabelText(/PDF pages/i) as HTMLDivElement;
    const viewer = pages.parentElement as HTMLDivElement;
    const scrollTo = mockScrollableViewer(viewer);
    mockRect(viewer, { top: 0, bottom: 800, left: 0, right: 600, width: 600, height: 800 });
    const originalRect = HTMLElement.prototype.getBoundingClientRect;
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function rect(
      this: HTMLElement,
    ) {
      const element = this as HTMLElement;
      if (element.classList.contains("pdf-viewer-highlight")) {
        return domRect({ top: 1200, bottom: 1260, left: 220, right: 340, width: 120, height: 60 });
      }
      if (element.classList.contains("pdf-viewer")) {
        return domRect({ top: 0, bottom: 800, left: 0, right: 600, width: 600, height: 800 });
      }
      return originalRect.call(this);
    });

    await screen.findByText("Page 2");
    rerender(
      <PdfViewer
        pdfUrl="http://127.0.0.1:8000/paper.pdf"
        page={1}
        highlight={{ page: 2, bbox: [10, 20, 160, 80] }}
      />,
    );

    await waitFor(() =>
      expect(scrollTo).toHaveBeenCalledWith(
        expect.objectContaining({ behavior: "smooth", top: expect.any(Number) }),
      ),
    );
    expect(viewer.scrollTop).toBeGreaterThan(0);
  });

  it("matches evidence quotes to PDF text when no bbox is available", async () => {
    pdfDocument.numPages = 1;
    pdfPage.getTextContent.mockResolvedValue({
      items: [
        { str: "structured ", transform: [1, 0, 0, 10, 10, 20], width: 80, height: 10 },
        { str: "reading report", transform: [1, 0, 0, 10, 90, 20], width: 110, height: 10 },
      ],
    });

    const { container } = render(
      <PdfViewer
        pdfUrl="http://127.0.0.1:8000/paper.pdf"
        page={1}
        highlight={{ page: 1, quote: "structured reading report" }}
      />,
    );

    await waitFor(() => {
      const highlight = container.querySelector(".pdf-viewer-highlight") as HTMLElement | null;
      expect(highlight).toBeInTheDocument();
      expect(highlight?.style.left).toBe("8px");
      expect(highlight?.style.top).toBe("18px");
      expect(highlight?.style.width).toBe("194px");
    });
  });

  it("does not pin scrolling back to the same evidence highlight after page changes", async () => {
    function ControlledViewer() {
      const [page, setPage] = useState(1);
      return (
        <PdfViewer
          pdfUrl="http://127.0.0.1:8000/paper.pdf"
          page={page}
          onPageChange={setPage}
          highlight={{ page: 2, bbox: [10, 20, 160, 80] }}
        />
      );
    }

    render(
      <ControlledViewer />,
    );

    const pages = screen.getByLabelText(/PDF pages/i) as HTMLDivElement;
    const viewer = pages.parentElement as HTMLDivElement;
    const scrollTo = mockScrollableViewer(viewer);
    const page1 = await findPageArticle(1);
    const page2 = await findPageArticle(2);
    const page3 = await findPageArticle(3);
    const originalRect = HTMLElement.prototype.getBoundingClientRect;
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function rect(
      this: HTMLElement,
    ) {
      const element = this as HTMLElement;
      if (element.classList.contains("pdf-viewer-highlight")) {
        return domRect({ top: 1200, bottom: 1260, left: 220, right: 340, width: 120, height: 60 });
      }
      if (element === page1) {
        return domRect({ top: -1800, bottom: -1000, left: 0, right: 600, width: 600, height: 800 });
      }
      if (element === page2) {
        return domRect({ top: -900, bottom: -100, left: 0, right: 600, width: 600, height: 800 });
      }
      if (element === page3) {
        return domRect({ top: 60, bottom: 860, left: 0, right: 600, width: 600, height: 800 });
      }
      if (element.classList.contains("pdf-viewer")) {
        return domRect({ top: 0, bottom: 800, left: 0, right: 600, width: 600, height: 800 });
      }
      return originalRect.call(this);
    });

    await waitFor(() =>
      expect(scrollTo).toHaveBeenCalledWith(
        expect.objectContaining({ behavior: "smooth", top: expect.any(Number) }),
      ),
    );
    const callsAfterEvidenceJump = scrollTo.mock.calls.length;

    fireEvent.scroll(viewer);

    await waitFor(() => expect(screen.getByLabelText(/^PDF page$/i)).toHaveValue("3"));

    expect(scrollTo).toHaveBeenCalledTimes(callsAfterEvidenceJump);
  });

  it("scrolls when the requested page changes externally", async () => {
    const { rerender } = render(
      <PdfViewer
        pdfUrl="http://127.0.0.1:8000/paper.pdf"
        page={1}
        highlight={{ page: 2, bbox: [10, 20, 160, 80] }}
      />,
    );

    const pages = screen.getByLabelText(/PDF pages/i) as HTMLDivElement;
    const viewer = pages.parentElement as HTMLDivElement;
    const scrollTo = mockScrollableViewer(viewer);
    const originalRect = HTMLElement.prototype.getBoundingClientRect;
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function rect(
      this: HTMLElement,
    ) {
      const element = this as HTMLElement;
      if (element.classList.contains("pdf-viewer-highlight")) {
        return domRect({ top: 1200, bottom: 1260, left: 220, right: 340, width: 120, height: 60 });
      }
      if (element.classList.contains("pdf-viewer")) {
        return domRect({ top: 0, bottom: 800, left: 0, right: 600, width: 600, height: 800 });
      }
      return originalRect.call(this);
    });

    await waitFor(() =>
      expect(scrollTo).toHaveBeenCalledWith(
        expect.objectContaining({ behavior: "smooth", top: expect.any(Number) }),
      ),
    );
    const callsAfterEvidenceJump = scrollTo.mock.calls.length;

    rerender(
      <PdfViewer
        pdfUrl="http://127.0.0.1:8000/paper.pdf"
        page={3}
        highlight={{ page: 2, bbox: [10, 20, 160, 80] }}
      />,
    );

    await Promise.resolve();

    expect(scrollTo.mock.calls.length).toBeGreaterThan(callsAfterEvidenceJump);
  });

  it("updates the current page from continuous viewer scrolling", async () => {
    const onPageChange = vi.fn();

    render(
      <PdfViewer
        pdfUrl="http://127.0.0.1:8000/paper.pdf"
        page={1}
        onPageChange={onPageChange}
      />,
    );

    const pages = screen.getByLabelText(/PDF pages/i) as HTMLDivElement;
    const viewer = pages.parentElement as HTMLDivElement;
    const page1 = await findPageArticle(1);
    const page2 = await findPageArticle(2);
    mockScrollableViewer(viewer);
    mockRect(viewer, { top: 0, bottom: 800, left: 0, right: 600, width: 600, height: 800 });
    mockRect(page1, { top: -900, bottom: -100, left: 0, right: 600, width: 600, height: 800 });
    mockRect(page2, { top: 60, bottom: 860, left: 0, right: 600, width: 600, height: 800 });

    fireEvent.scroll(viewer);

    await waitFor(() => expect(onPageChange).toHaveBeenCalledWith(2));
    expect(screen.getByLabelText(/^PDF page$/i)).toHaveValue("2");
  });
});

async function findPageArticle(pageNumber: number): Promise<HTMLElement> {
  await screen.findByText(`Page ${pageNumber}`);
  const article = screen
    .getAllByText(`Page ${pageNumber}`)
    .map((label) => label.closest(".pdf-viewer-page"))
    .find((node): node is HTMLElement => node instanceof HTMLElement);
  if (!(article instanceof HTMLElement)) {
    throw new Error(`Page ${pageNumber} article not found`);
  }
  return article;
}

function mockScrollableViewer(viewer: HTMLDivElement) {
  Object.defineProperty(viewer, "clientHeight", { configurable: true, value: 800 });
  Object.defineProperty(viewer, "clientWidth", { configurable: true, value: 600 });
  Object.defineProperty(viewer, "scrollHeight", { configurable: true, value: 2600 });
  Object.defineProperty(viewer, "scrollWidth", { configurable: true, value: 900 });
  viewer.scrollTop = 0;
  viewer.scrollLeft = 0;
  const scrollTo = vi.fn((options: ScrollToOptions) => {
    viewer.scrollTop = Number(options.top ?? 0);
    viewer.scrollLeft = Number(options.left ?? 0);
  });
  Object.defineProperty(viewer, "scrollTo", { configurable: true, value: scrollTo });
  return scrollTo;
}

function mockRect(element: HTMLElement, rect: RectInit) {
  vi.spyOn(element, "getBoundingClientRect").mockReturnValue(domRect(rect));
}

function domRect(rect: RectInit): DOMRect {
  return {
    x: rect.left,
    y: rect.top,
    top: rect.top,
    bottom: rect.bottom,
    left: rect.left,
    right: rect.right,
    width: rect.width,
    height: rect.height,
    toJSON: () => rect,
  } as DOMRect;
}

interface RectInit {
  top: number;
  bottom: number;
  left: number;
  right: number;
  width: number;
  height: number;
}

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((promiseResolve, promiseReject) => {
    resolve = promiseResolve;
    reject = promiseReject;
  });
  return { promise, resolve, reject };
}
