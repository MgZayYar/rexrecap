"use client";

import { useCallback, useEffect, useState } from "react";

import { JobStatus } from "@/components/job-status";
import { VideoJobActions } from "@/components/video-job-actions";
import { VideoProjectAssign } from "@/components/video-project-assign";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/feedback";
import { apiGet } from "@/lib/api-client";
import type { ProcessingJob } from "@/lib/job";
import { formatFileSize, type Video } from "@/lib/video";

const POLL_INTERVAL_MS = 3000;

/** Dashboard video table with a single shared job poller.
 *
 * Previously every row ran its own 2s poller against /api/jobs/video/{id},
 * so N videos meant N requests every 2s forever. Now one request every 3s
 * covers all rows. */
export function DashboardVideos({ videos }: { videos: Video[] }) {
  const [latestByVideo, setLatestByVideo] = useState<Map<number, ProcessingJob>>(new Map());

  const refresh = useCallback(async () => {
    try {
      const jobs = await apiGet<ProcessingJob[]>("/api/jobs?limit=200");
      const latest = new Map<number, ProcessingJob>();
      for (const job of jobs) {
        if (!latest.has(job.video_id)) latest.set(job.video_id, job);
      }
      setLatestByVideo(latest);
    } catch {
      // Keep the last known state on transient failures.
    }
  }, []);

  useEffect(() => {
    void refresh();
    const interval = window.setInterval(() => void refresh(), POLL_INTERVAL_MS);
    return () => window.clearInterval(interval);
  }, [refresh]);

  if (videos.length === 0) {
    return <EmptyState>No videos uploaded yet. Upload your first video to get started.</EmptyState>;
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200">
      <table className="w-full min-w-[980px] text-left text-sm">
        <thead className="bg-slate-50 text-slate-600">
          <tr>
            <th className="px-4 py-3 font-medium">Filename</th>
            <th className="px-4 py-3 font-medium">Project</th>
            <th className="px-4 py-3 font-medium">Uploaded</th>
            <th className="px-4 py-3 font-medium">Upload status</th>
            <th className="px-4 py-3 font-medium">Processing</th>
            <th className="px-4 py-3 font-medium text-right">Workflows</th>
            <th className="px-4 py-3 font-medium text-right">Action</th>
          </tr>
        </thead>
        <tbody>
          {videos.map((video) => (
            <tr key={video.id} className="border-t border-slate-200">
              <td className="px-4 py-3">
                <p className="font-medium text-slate-900">{video.filename}</p>
                <p className="text-slate-500">{formatFileSize(video.size_bytes)}</p>
              </td>
              <td className="px-4 py-3"><VideoProjectAssign video={video} /></td>
              <td className="px-4 py-3 text-slate-600">
                {new Intl.DateTimeFormat("en", { dateStyle: "medium" }).format(new Date(video.created_at))}
              </td>
              <td className="px-4 py-3">
                <span className="rounded-full bg-green-50 px-2.5 py-1 text-xs font-medium text-green-700">
                  {video.status}
                </span>
              </td>
              <td className="px-4 py-3">
                <JobStatus job={latestByVideo.get(video.id) ?? null} onChanged={refresh} />
              </td>
              <td className="px-4 py-3">
                <VideoJobActions videoId={video.id} onJobStarted={refresh} />
              </td>
              <td className="px-4 py-3 text-right">
                <div className="flex justify-end gap-2">
                  <Button variant="outline" size="sm" asChild><a href={`/videos/${video.id}/subtitles`}>Edit subtitles</a></Button>
                  <Button variant="outline" size="sm" asChild><a href={`/videos/${video.id}/transcript`}>Transcript</a></Button>
                  <Button variant="outline" size="sm" asChild><a href={`/videos/${video.id}/dubbing`}>Dubbing</a></Button>
                  <Button variant="outline" size="sm" asChild><a href={`/videos/${video.id}/shorts`}>Shorts</a></Button>
                  <Button variant="outline" size="sm" asChild><a href={`/videos/${video.id}/thumbnails`}>Thumbnails</a></Button>
                  <Button variant="outline" size="sm" asChild><a href={`/videos/${video.id}/assistant`}>Assistant</a></Button>
                  <Button variant="outline" size="sm" asChild><a href={`/api/videos/${video.id}/download`}>Download</a></Button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
