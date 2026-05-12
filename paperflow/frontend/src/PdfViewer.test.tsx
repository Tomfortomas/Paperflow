import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { PdfViewer } from "./PdfViewer";

describe("PdfViewer", () => {
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

    expect(screen.getByLabelText(/PDF pages/i)).toBeInTheDocument();

    await user.clear(screen.getByLabelText(/^PDF page$/i));
    await user.type(screen.getByLabelText(/^PDF page$/i), "7");
    await user.click(screen.getByRole("button", { name: /Go/i }));

    expect(onPageChange).toHaveBeenCalledWith(7);

    await user.selectOptions(screen.getByLabelText(/^PDF zoom$/i), "150");

    expect(screen.getByLabelText(/^PDF zoom$/i)).toHaveValue("150");
  });

  it("routes wheel gestures over the viewer into the PDF page scroller", () => {
    render(<PdfViewer pdfUrl="http://127.0.0.1:8000/paper.pdf" page={1} />);

    const pages = screen.getByLabelText(/PDF pages/i) as HTMLDivElement;
    const viewer = pages.parentElement;
    expect(viewer).not.toBeNull();

    Object.defineProperty(pages, "clientHeight", { configurable: true, value: 400 });
    Object.defineProperty(pages, "scrollHeight", { configurable: true, value: 1200 });
    pages.scrollTop = 0;

    fireEvent.wheel(viewer as HTMLElement, { deltaY: 240 });

    expect(pages.scrollTop).toBe(240);
  });
});
