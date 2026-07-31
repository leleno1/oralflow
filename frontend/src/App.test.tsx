import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { App } from "./App";

describe("M0 application shell", () => {
  it("shows the milestone and external-model boundary", () => {
    render(<App />);

    expect(
      screen.getByRole("heading", { name: "Engineering Harness" }),
    ).toBeInTheDocument();
    expect(screen.getByText("External models disabled")).toBeInTheDocument();
    expect(screen.getByText("No workflow runtime")).toBeInTheDocument();
  });
});
