import { render } from "@testing-library/react";
import RootLayout, { metadata } from "./layout";

describe("RootLayout", () => {
  it("exports the correct metadata", () => {
    expect(metadata).toEqual({
      title: "NexCode — AI Coding Assistant",
      description:
        "AI-powered coding assistant that works everywhere. Like Claude Code, but open and multi-model.",
    });
  });

  it("renders children inside html and body tags", () => {
    const { getByTestId } = render(
      <RootLayout>
        <div data-testid="test-child">Child Content</div>
      </RootLayout>
    );

    const renderedHtml = document.querySelector('html[lang="en"]');
    expect(renderedHtml).toBeInTheDocument();

    const renderedBody = renderedHtml?.querySelector('body');
    expect(renderedBody).toBeInTheDocument();

    const testChild = getByTestId("test-child");
    expect(testChild).toBeInTheDocument();
    expect(testChild).toHaveTextContent("Child Content");
  });
});
