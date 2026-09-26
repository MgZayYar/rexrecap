import { describe, expect, it } from "vitest";

import { makeCues, srtTime, toSrt } from "@/lib/subtitle";
import { formatTimestamp } from "@/lib/transcript";

describe("formatTimestamp", () => {
  it("formats seconds as MM:SS", () => {
    expect(formatTimestamp(0)).toBe("00:00");
    expect(formatTimestamp(65)).toBe("01:05");
    expect(formatTimestamp(3599)).toBe("59:59");
  });
});

describe("subtitle helpers", () => {
  it("builds one cue per transcript segment", () => {
    const cues = makeCues([
      { start: 0, end: 1.5, text: "Hello" },
      { start: 1.5, end: 3, text: "world" },
    ]);
    expect(cues).toHaveLength(2);
    expect(cues[0]).toMatchObject({ start: 0, end: 1.5, text: "Hello" });
  });

  it("renders SRT time ranges", () => {
    expect(srtTime(65.5)).toBe("00:01:05,500");
  });

  it("exports cues as SRT", () => {
    const srt = toSrt([{ id: "a", start: 0, end: 1, text: "Hi" }]);
    expect(srt).toContain("1\n00:00:00,000 --> 00:00:01,000\nHi");
  });
});
