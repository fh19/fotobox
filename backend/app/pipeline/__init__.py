"""Image pipeline: overlay, chroma-key, AI segmentation, composition, caption, QR.

Order of implementation and processing follows docs/druck-layout.md.
"""

from app.pipeline.errors import PipelineError
from app.pipeline.geometry import detect_orientation
from app.pipeline.runner import PipelineOutputs, run_pipeline

__all__ = ["PipelineError", "PipelineOutputs", "detect_orientation", "run_pipeline"]
