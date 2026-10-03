from functools import lru_cache
from typing import Tuple
from facefusion.types import Fps, InferencePool, DownloadSet, VisionFrame

STREAM_COUNTER = 0

def get_inference_pool() -> InferencePool:
    return {}

def clear_inference_pool() -> None:
    pass

def collect_model_downloads() -> Tuple[DownloadSet, DownloadSet]:
    return {}, {}

def pre_check() -> bool:
    return True

def analyse_stream(vision_frame : VisionFrame, video_fps : Fps) -> bool:
    return False

def analyse_frame(vision_frame : VisionFrame) -> bool:
    return False

@lru_cache()
def analyse_image(image_path : str) -> bool:
    return False

@lru_cache()
def analyse_video(video_path : str, trim_frame_start : int, trim_frame_end : int) -> bool:
    return False

def detect_nsfw(vision_frame : VisionFrame) -> bool:
    return False
