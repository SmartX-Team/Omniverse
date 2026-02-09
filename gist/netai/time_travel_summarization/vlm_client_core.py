"""
VLM 서버에 동영상을 업로드하고, VLM 분석을 요청하고, 결과를 저장하는 `VLM Client module` 의 core.
default_chunk_duration=2 초, default_chunk_overlap_duration=0 초로 설정됨.
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any
import carb
from datetime import datetime


class VLMClientCore:
    """Core logic for VLM Client."""
    
    def __init__(self):
        """Initialize VLM Client Core."""
        self._client = None
        self._current_video_id = None
        self._last_upload_response = None
        self._last_generation_response = None
        
        # Default paths
        self._videos_base_path = Path(__file__).parent / "video"
        self._outputs_base_path = Path(__file__).parent / "vlm_outputs"
        
        # Ensure directories exist
        self._videos_base_path.mkdir(exist_ok=True)
        self._outputs_base_path.mkdir(exist_ok=True)
        
        # Initialize client
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize VSS Client with presets."""
        try:
            from .utils.VSS_client import VSSClient, PromptPreset
            
            # Get base URL from environment or use default
            base_url = os.environ.get("VIA_BACKEND", "http://localhost:8100")
            
            # Define prompt presets
            presets = {
                "twin_view": PromptPreset(
                    prompt=("""
Analyze the provided BEV digital twin video.
Identify every frame or moment where two or more objects visually overlap or intersect.
For each overlapping event, extract:
- the timestamp shown on the video, and
- the numbers of all overlapping objects.

Return only a JSON list following this structure:
[
  {"HH:MM:SS": [3, 5]},
  {"HH:MM:SS": [1, 2, 4]}
]
"""),
                    system_prompt=("""
You are a vision-language reasoning model specialized in video understanding. 
You are given a video generated from a digital twin simulation viewed from a bird's-eye view (BEV).
In the video:
- Multiple numbered objects move freely in a shared space.
- Each object has a visible numeric label.
- A timestamp (date and time) is displayed at the bottom-right corner of the video.
- Occasionally, objects visually overlap or intersect.

Your task is to detect all frames or time periods where two or more numbered objects overlap (i.e., their bounding areas visually intersect). 

When an overlap occurs, extract and return:
1. The exact timestamp displayed on screen.
2. The list of object numbers involved in the overlap.

Format the final answer as a structured JSON array with this schema:
[
  {"HH:MM:SS": [object_number_1, object_number_2, ...]},
  {"HH:MM:SS": [object_number_1, object_number_2, ...]},
...
]

Be concise, accurate, and consistent. Only report actual overlaps (not near contacts).
If multiple overlaps occur at the same timestamp, list them all in the same entry.
Do not include any explanatory text or reasoning in the output.
"""),
                ),
                
                "simple_view": PromptPreset(
                    prompt=("""
Analyze the video showing moving numbered circles on a white background.

Identify every moment where two or more circles overlap visually.
For each overlap, extract:
- the datetime shown on the video
- the numeric labels of the overlapping circles

Return your answer **only** in the following JSON format:

[
  {"HH:MM:SS": [object_number_1, object_number_2, ...]},
  {"HH:MM:SS": [object_number_1, object_number_2, ...]},
...
]
"""),
                    system_prompt=("""
You are a vision-language model specialized in visual reasoning over video data.

You are given a video where:
- The background is plain white.
- Multiple black circular objects move freely across the screen.
- Each circle has a white numeric label written at its center.
- A timestamp is displayed in the bottom-right corner of the video.
- No other visual elements are present.

Your task is to detect every moment when two or more circles visually overlap.
Overlap is defined as their areas intersect, cover each other, or appear as a single object.

When an overlap occurs, extract and return:
1. The exact timestamp shown in the bottom-right corner of the video at that moment.
2. The numeric labels of the overlapping circles.

Return your results strictly in JSON format as follows:

[
  {"HH:MM:SS": [object_number_1, object_number_2, ...]},
  {"HH:MM:SS": [object_number_1, object_number_2, ...]},
...
]

Only include timestamps where the circles are overlapping — ignore moments when they are merely close or touching edges.
Do not include any reasoning or description; output **only** the JSON results.
"""),
                )
            }
            
            self._client = VSSClient(
                base_url=base_url,
                default_chunk_duration=2,
                default_chunk_overlap_duration=0,
                prompt_presets=presets,
            )
            
            carb.log_info(f"[VLMClient] Initialized with base_url: {base_url}")
            
        except Exception as e:
            carb.log_error(f"[VLMClient] Failed to initialize client: {e}")
            import traceback
            carb.log_error(traceback.format_exc())
            self._client = None
    
    def upload_video(self, video_filename: str) -> bool:
        """
        Upload video to VSS server.
        
        Args:
            video_filename: Video filename (relative to videos/ directory)
            
        Returns:
            True if successful, False otherwise
        """
        if not self._client:
            carb.log_error("[VLMClient] Client not initialized")
            return False
        
        try:
            # Construct full path
            video_path = self._videos_base_path / video_filename
            
            if not video_path.exists():
                carb.log_error(f"[VLMClient] Video file not found: {video_path}")
                return False
            
            carb.log_info(f"[VLMClient] Uploading video: {video_path}")
            
            # Upload video
            response = self._client.upload_video(str(video_path))
            
            # Store response and video ID
            self._last_upload_response = response
            self._current_video_id = response.get("id")
            
            carb.log_info(f"[VLMClient] Uploaded video ID: {self._current_video_id}")
            return True
            
        except Exception as e:
            carb.log_error(f"[VLMClient] Upload failed: {e}")
            import traceback
            carb.log_error(traceback.format_exc())
            return False
    
    def delete_video(self) -> bool:
        """
        Delete currently uploaded video.
        
        Returns:
            True if successful, False otherwise
        """
        if not self._client:
            carb.log_error("[VLMClient] Client not initialized")
            return False
        
        if not self._current_video_id:
            carb.log_error("[VLMClient] No video ID to delete")
            return False
        
        try:
            carb.log_info(f"[VLMClient] Deleting video ID: {self._current_video_id}")
            
            response = self._client.delete_video(self._current_video_id)
            
            carb.log_info(f"[VLMClient] Video deleted: {response}")
            
            # Clear current video ID
            self._current_video_id = None
            self._last_upload_response = None
            
            return True
            
        except Exception as e:
            carb.log_error(f"[VLMClient] Delete failed: {e}")
            import traceback
            carb.log_error(traceback.format_exc())
            return False
    
    def generate_captions(
        self,
        model: str = "Qwen3-VL-8B-Instruct",
        preset_name: str = "simple_view",
        video_filename: Optional[str] = None,
        chunk_overlap_duration: int = 0
    ) -> tuple[bool, Optional[str]]:
        """
        Generate VLM captions for current video.
        
        Args:
            model: VLM model name (default: "Qwen3-VL-8B-Instruct")
            preset_name: Prompt preset name (default: "simple_view")
            video_filename: Optional video filename for output naming
            chunk_overlap_duration: Chunk overlap duration in seconds (default: 0)
            
        Returns:
            Tuple of (success: bool, output_filename: Optional[str])
        """
        if not self._client:
            carb.log_error("[VLMClient] Client not initialized")
            return False, None
        
        if not self._current_video_id:
            carb.log_error("[VLMClient] No video uploaded")
            return False, None
        
        try:
            carb.log_info(f"[VLMClient] Generating captions for video ID: {self._current_video_id}")
            carb.log_info(f"[VLMClient] Model: {model}, Preset: {preset_name}")
            carb.log_info(f"[VLMClient] Chunk overlap duration: {chunk_overlap_duration}s")
            
            # Generate captions
            response = self._client.generate_vlm_captions(
                video_id=self._current_video_id,
                model=model,
                preset_name=preset_name,
                chunk_overlap_duration=chunk_overlap_duration
            )
            
            # Store response
            self._last_generation_response = response
            
            # Save to outputs directory
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            if video_filename:
                # Use video filename without extension
                video_stem = Path(video_filename).stem
                output_filename = f"{model}_{video_stem}_{timestamp}.json"
            else:
                output_filename = f"{model}_output_{timestamp}.json"
            
            output_path = self._outputs_base_path / output_filename
            
            # Save JSON
            self._client.save_json(response, str(output_path))
            
            carb.log_info(f"[VLMClient] Results saved to: {output_path}")
            
            # Log execution time
            exec_time = response.get("execution_time", 0)
            carb.log_info(f"[VLMClient] Execution time: {exec_time:.2f} seconds")
            
            return True, output_filename
            
        except Exception as e:
            carb.log_error(f"[VLMClient] Generation failed: {e}")
            carb.log_error(f"[VLMClient] Video ID: {self._current_video_id}")
            carb.log_error(f"[VLMClient] Model: {model}, Preset: {preset_name}")
            import traceback
            carb.log_error(traceback.format_exc())
            return False, None
    
    def get_current_video_id(self) -> Optional[str]:
        """Get current video ID."""
        return self._current_video_id
    
    def has_video_uploaded(self) -> bool:
        """Check if video is uploaded."""
        return self._current_video_id is not None
    
    def get_videos_path(self) -> str:
        """Get videos directory path."""
        return str(self._videos_base_path)
    
    def get_outputs_path(self) -> str:
        """Get outputs directory path."""
        return str(self._outputs_base_path)
