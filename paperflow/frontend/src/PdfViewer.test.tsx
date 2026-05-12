import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PdfViewer } from "./PdfViewer";

const pdfPage = {
  getViewport: ({ scale }: { scale: number }) => ({
    width: 600 * scale,
    height: 800 * scale,
  }),
  getTextContent: vi.fn(async () => ({ items: [] })),
  render: vi.fn(() => ({ promise: Promise.resolve() })),
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

    await user.selectOptions(screen.getByLabelText(/^PDF zoom$/i), "150");

    expect(screen.getByLabelText(/^PDF zoom$/i)).toHaveValue("150");
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
