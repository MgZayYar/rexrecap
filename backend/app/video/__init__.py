"""Video-processing boundary.

All direct FFmpeg invocations and video-file operations live here so that
API routes, workers, and AI adapters share one implementation instead of
scattering subprocess calls across the application.
"""
