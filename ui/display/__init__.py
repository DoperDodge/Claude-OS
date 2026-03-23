"""
Claude-OS Display Module

Provides framebuffer and DRM rendering primitives for drawing to the
screen. This is the lowest layer of the visual OS — everything above
(compositor, widgets, UI shell) ultimately draws through here.

Two rendering backends:
  - Framebuffer (/dev/fb0): Legacy, simple mmap interface
  - DRM/KMS (/dev/dri/card0): Modern, supports page-flipping and vsync
"""
