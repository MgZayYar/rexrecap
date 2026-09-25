"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { defaultSubtitleStyle, makeCues, toAss, toSrt, type SubtitleCue, type SubtitleStyle } from "@/lib/subtitle";
import type { Transcript } from "@/lib/transcript";

type DragState = { id: string; edge: "start" | "end" } | null;

function download(filename: string, content: string, type: string) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export function SubtitleEditor({ videoId }: { videoId: number }) {
  const [cues, setCues] = useState<SubtitleCue[]>([]);
  const [history, setHistory] = useState<SubtitleCue[][]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [style, setStyle] = useState<SubtitleStyle>(defaultSubtitleStyle);
  const [error, setError] = useState<string | null>(null);
  const [drag, setDrag] = useState<DragState>(null);
  const timeline = useRef<HTMLDivElement>(null);

  const commit = useCallback((next: SubtitleCue[]) => {
    const snapshot = next.map((cue) => ({ ...cue }));
    setCues(snapshot);
    setHistory((previous) => {
      const branch = previous.slice(0, historyIndex + 1);
      return [...branch, snapshot];
    });
    setHistoryIndex((index) => index + 1);
  }, [historyIndex]);

  useEffect(() => {
    async function load() {
      const response = await fetch(`/api/transcripts/${videoId}`, { cache: "no-store" });
      if (!response.ok) {
        setError(response.status === 404 ? "Generate a transcript before opening the subtitle editor." : "Unable to load the transcript.");
        return;
      }
      const transcript = (await response.json()) as Transcript;
      const initial = makeCues(transcript.segments);
      setCues(initial);
      setHistory([initial]);
      setHistoryIndex(0);
      setSelectedId(initial[0]?.id ?? null);
    }
    void load();
  }, [videoId]);

  const undo = useCallback(() => {
    if (historyIndex <= 0) return;
    const index = historyIndex - 1;
    setHistoryIndex(index);
    setCues(history[index].map((cue) => ({ ...cue })));
  }, [history, historyIndex]);
  const redo = useCallback(() => {
    if (historyIndex >= history.length - 1) return;
    const index = historyIndex + 1;
    setHistoryIndex(index);
    setCues(history[index].map((cue) => ({ ...cue })));
  }, [history, historyIndex]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") { event.preventDefault(); if (event.shiftKey) redo(); else undo(); }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "y") { event.preventDefault(); redo(); }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "f") { event.preventDefault(); document.getElementById("subtitle-search")?.focus(); }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [redo, undo]);

  const duration = Math.max(1, ...cues.map((cue) => cue.end));
  const selectedIndex = cues.findIndex((cue) => cue.id === selectedId);
  const selected = selectedIndex >= 0 ? cues[selectedIndex] : null;
  const visibleCues = useMemo(() => cues.filter((cue) => cue.text.toLowerCase().includes(search.toLowerCase())), [cues, search]);

  function updateCue(id: string, changes: Partial<SubtitleCue>) { commit(cues.map((cue) => cue.id === id ? { ...cue, ...changes } : cue)); }
  function merge() {
    if (!selected || selectedIndex === cues.length - 1) return;
    const next = cues[selectedIndex + 1];
    const merged = { ...selected, end: next.end, text: `${selected.text.trim()} ${next.text.trim()}` };
    commit(cues.filter((cue) => cue.id !== next.id).map((cue) => cue.id === selected.id ? merged : cue));
  }
  function split() {
    if (!selected) return;
    const words = selected.text.trim().split(/\s+/);
    if (words.length < 2) return;
    const splitAt = Math.ceil(words.length / 2);
    const middle = (selected.start + selected.end) / 2;
    const second: SubtitleCue = { id: `${selected.id}-split-${Date.now()}`, start: middle, end: selected.end, text: words.slice(splitAt).join(" ") };
    const first: SubtitleCue = { ...selected, end: middle, text: words.slice(0, splitAt).join(" ") };
    const next = cues.flatMap((cue) => cue.id === selected.id ? [first, second] : [cue]);
    commit(next);
    setSelectedId(first.id);
  }

  useEffect(() => {
    if (!drag) return;
    const activeDrag = drag;
    function move(event: PointerEvent) {
      const bounds = timeline.current?.getBoundingClientRect();
      if (!bounds) return;
      const seconds = Math.max(0, Math.min(duration, ((event.clientX - bounds.left) / bounds.width) * duration));
      setCues((current) => current.map((cue) => {
        if (cue.id !== activeDrag.id) return cue;
        return activeDrag.edge === "start" ? { ...cue, start: Math.min(seconds, cue.end - 0.1) } : { ...cue, end: Math.max(seconds, cue.start + 0.1) };
      }));
    }
    function stop() { setCues((current) => { commit(current); return current; }); setDrag(null); }
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop, { once: true });
    return () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", stop); };
  }, [drag, duration, commit]);

  if (error) return <section className="rounded-lg border border-slate-200 bg-white p-6"><p className="text-slate-700">{error}</p></section>;
  if (!cues.length) return <section className="rounded-lg border border-slate-200 bg-white p-6"><p className="text-slate-600">Loading subtitle editor…</p></section>;

  const previewStyle = { fontFamily: style.fontFamily, fontSize: `${style.fontSize}px`, color: style.color, backgroundColor: style.background };
  const previewPosition = style.position === "top" ? "items-start" : style.position === "middle" ? "items-center" : "items-end";
  return <section className="space-y-5"><header className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-200 bg-white p-4 shadow-sm"><div><h2 className="text-xl font-semibold">Subtitle editor</h2><p className="mt-1 text-sm text-slate-600">{cues.length} cues · Ctrl/Cmd+Z undo · Ctrl/Cmd+Shift+Z redo · Ctrl/Cmd+F search</p></div><div className="flex flex-wrap gap-2"><Button variant="outline" size="sm" onClick={undo} disabled={historyIndex <= 0}>Undo</Button><Button variant="outline" size="sm" onClick={redo} disabled={historyIndex >= history.length - 1}>Redo</Button><Button variant="outline" size="sm" onClick={() => download("rexcrop-subtitles.srt", toSrt(cues), "text/plain;charset=utf-8")}>Export SRT</Button><Button size="sm" onClick={() => download("rexcrop-subtitles.ass", toAss(cues, style), "text/plain;charset=utf-8")}>Export ASS</Button></div></header><div className="rounded-lg border border-slate-200 bg-slate-950 p-4"><div ref={timeline} className="relative h-24 select-none overflow-hidden rounded bg-slate-900" aria-label="Subtitle timeline">{cues.map((cue) => <div key={cue.id} className={`absolute top-8 h-10 rounded border ${cue.id === selectedId ? "border-white bg-blue-500" : "border-blue-300 bg-blue-700"}`} style={{ left: `${(cue.start / duration) * 100}%`, width: `${Math.max(1, ((cue.end - cue.start) / duration) * 100)}%` }} onClick={() => setSelectedId(cue.id)}><button className="absolute -left-1 top-0 h-full w-2 cursor-ew-resize bg-white/70" aria-label="Drag subtitle start" onPointerDown={(event) => { event.preventDefault(); setDrag({ id: cue.id, edge: "start" }); }} /><span className="block truncate px-2 py-2 text-xs text-white">{cue.text}</span><button className="absolute -right-1 top-0 h-full w-2 cursor-ew-resize bg-white/70" aria-label="Drag subtitle end" onPointerDown={(event) => { event.preventDefault(); setDrag({ id: cue.id, edge: "end" }); }} /></div>)}</div><div className="mt-2 flex justify-between font-mono text-xs text-slate-400"><span>00:00</span><span>{Math.floor(duration / 60).toString().padStart(2, "0")}:{Math.floor(duration % 60).toString().padStart(2, "0")}</span></div></div><div className="grid gap-5 lg:grid-cols-[1fr_330px]"><div className="rounded-lg border border-slate-200 bg-white"><div className="border-b border-slate-200 p-4"><input id="subtitle-search" className="h-10 w-full rounded-md border border-slate-300 px-3 text-sm" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search subtitle text" /></div><ol className="max-h-[560px] overflow-y-auto divide-y divide-slate-200">{visibleCues.map((cue) => <li key={cue.id} className={`cursor-pointer p-4 ${cue.id === selectedId ? "bg-blue-50" : "hover:bg-slate-50"}`} onClick={() => setSelectedId(cue.id)}><div className="flex gap-3"><span className="w-28 shrink-0 font-mono text-xs text-slate-500">{cue.start.toFixed(2)} – {cue.end.toFixed(2)}</span><p className="text-sm text-slate-800">{cue.text}</p></div></li>)}</ol></div><aside className="space-y-5 rounded-lg border border-slate-200 bg-white p-5"><div><h3 className="font-semibold">Cue</h3>{selected ? <><textarea className="mt-3 min-h-28 w-full rounded-md border border-slate-300 p-3 text-sm" value={selected.text} onChange={(event) => updateCue(selected.id, { text: event.target.value })} /><div className="mt-3 grid grid-cols-2 gap-3"><label className="text-xs font-medium text-slate-600">Start<input className="mt-1 h-9 w-full rounded border border-slate-300 px-2 text-sm" type="number" min="0" step="0.01" value={selected.start} onChange={(event) => updateCue(selected.id, { start: Math.min(Number(event.target.value), selected.end - 0.1) })} /></label><label className="text-xs font-medium text-slate-600">End<input className="mt-1 h-9 w-full rounded border border-slate-300 px-2 text-sm" type="number" min="0" step="0.01" value={selected.end} onChange={(event) => updateCue(selected.id, { end: Math.max(Number(event.target.value), selected.start + 0.1) })} /></label></div><div className="mt-3 flex gap-2"><Button variant="outline" size="sm" onClick={merge} disabled={selectedIndex === cues.length - 1}>Merge next</Button><Button variant="outline" size="sm" onClick={split} disabled={selected.text.trim().split(/\s+/).length < 2}>Split</Button></div></> : <p className="mt-2 text-sm text-slate-500">Select a cue to edit it.</p>}</div><div className="border-t border-slate-200 pt-5"><h3 className="font-semibold">Style</h3><div className="mt-3 grid grid-cols-2 gap-3"><label className="text-xs font-medium text-slate-600">Font<select className="mt-1 h-9 w-full rounded border border-slate-300 px-2 text-sm" value={style.fontFamily} onChange={(event) => setStyle({ ...style, fontFamily: event.target.value })}><option>Arial</option><option>Helvetica</option><option>Verdana</option><option>Georgia</option></select></label><label className="text-xs font-medium text-slate-600">Size<input className="mt-1 h-9 w-full rounded border border-slate-300 px-2 text-sm" type="number" min="12" max="96" value={style.fontSize} onChange={(event) => setStyle({ ...style, fontSize: Number(event.target.value) })} /></label><label className="text-xs font-medium text-slate-600">Text<input className="mt-1 h-9 w-full rounded border border-slate-300 p-1" type="color" value={style.color} onChange={(event) => setStyle({ ...style, color: event.target.value })} /></label><label className="text-xs font-medium text-slate-600">Background<input className="mt-1 h-9 w-full rounded border border-slate-300 p-1" type="color" value={style.background} onChange={(event) => setStyle({ ...style, background: event.target.value })} /></label></div><label className="mt-3 block text-xs font-medium text-slate-600">Position<select className="mt-1 h-9 w-full rounded border border-slate-300 px-2 text-sm" value={style.position} onChange={(event) => setStyle({ ...style, position: event.target.value as SubtitleStyle["position"] })}><option value="bottom">Bottom</option><option value="middle">Middle</option><option value="top">Top</option></select></label><div className={`mt-4 flex h-32 ${previewPosition} justify-center rounded bg-slate-950 p-4 text-center`}><span className="px-2 py-1" style={previewStyle}>{selected?.text || "Subtitle preview"}</span></div></div></aside></div></section>;
}
