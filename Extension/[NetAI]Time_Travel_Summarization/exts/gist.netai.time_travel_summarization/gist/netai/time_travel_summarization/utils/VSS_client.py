import os
import json
from dataclasses import dataclass
from typing import Dict, Any, Optional
import json
import os
from datetime import datetime
from unittest import result

import requests


@dataclass
class PromptPreset:
    """프롬프트 프리셋 구조"""
    prompt: str
    system_prompt: Optional[str] = None


class VSSClient:
    """
    NVIDIA VSS (Video Search and Summarization) 서버와 통신하는 클라이언트.
    공개된 VSS API 문서를 기준으로 작성됨. (https://docs.nvidia.com/vss/latest/content/API_doc.html)
    """

    def __init__(
        self,
        base_url: str,
        default_chunk_duration: int = 2,
        default_chunk_overlap_duration: int = 0,
        prompt_presets: Optional[Dict[str, PromptPreset]] = None,
    ):
        """
        Args:
            base_url: VSS 서버 베이스 URL (예: "http://localhost:8000" 혹은 VIA_BACKEND 주소)
            default_chunk_duration: 별도 지정 없을 때 사용할 기본 chunk duration (초 단위)
            default_chunk_overlap_duration: 별도 지정 없을 때 사용할 기본 chunk overlap duration (초 단위)
            prompt_presets: 이름으로 불러 쓸 프롬프트 프리셋 딕셔너리
        """
        self.base_url = base_url.rstrip("/")
        self.default_chunk_duration = default_chunk_duration
        self.default_chunk_overlap_duration = default_chunk_overlap_duration
        self.prompt_presets: Dict[str, PromptPreset] = prompt_presets or {}

    # ------------------------------------------------------------------
    # 1. 비디오 업로드 / 삭제
    # ------------------------------------------------------------------
    def upload_video(
        self,
        file_path: str,
        purpose: str = "vision",
        media_type: str = "video",
    ) -> Dict[str, Any]:
        """
        VSS 서버에 비디오(또는 이미지)를 업로드.

        Args:
            file_path: 업로드할 파일 경로
            purpose: 서버에서 사용하는 목적 태그 
                기본: "vision". 그 이외에는 뭐가 있는지 VSS API 문서에 명시되어 있지 않음..
                참고: https://docs.nvidia.com/vss/latest/content/API_doc.html#files-files-post
            media_type: "video" 또는 "image"

        Returns:
            서버에서 반환한 JSON (보통 {id, filename, bytes, purpose, media_type} 등)
        """
        url = f"{self.base_url}/files"

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        files = {
            "file": open(file_path, "rb"),
            "purpose": (None, purpose),
            "media_type": (None, media_type),
        }

        try:
            resp = requests.post(url, files=files)
        finally:
            files["file"].close()

        self._raise_for_error(resp, "upload_video")
        return resp.json()

    def delete_video(self, file_id: str) -> Dict[str, Any]:
        """
        업로드된 비디오(파일)를 삭제.

        Args:
            file_id: VSS 서버에서 관리하는 파일 ID

        Returns:
            서버의 JSON 응답
        """
        url = f"{self.base_url}/files/{file_id}"
        resp = requests.delete(url)
        self._raise_for_error(resp, "delete_video")
        return resp.json()

    # ------------------------------------------------------------------
    # 2. generate_vlm_captions 기능
    # ------------------------------------------------------------------
    def generate_vlm_captions(
        self,
        video_id: str,
        model: str,
        preset_name: Optional[str] = None,
        prompt: Optional[str] = None,
        system_prompt: Optional[str] = None,
        chunk_duration: Optional[int] = None,
        chunk_overlap_duration: Optional[int] = None,
        response_format: str = "json_object",
        extra_params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        VLM 기반 캡션 생성 요청. 이 요청을 기반으로 timestamp와 object ID 추출이 이루어짐.

        Args:
            video_id: VSS에 등록된 비디오 ID
            model: 사용할 VLM 모델 이름 (예: "Qwen3-VL-8B-Instruct")
            preset_name: 내부에 저장된 프롬프트 프리셋 이름
            prompt: 직접 전달할 프롬프트 (preset보다 우선)
            system_prompt: 직접 전달할 시스템 프롬프트 (preset보다 우선)
            chunk_duration: 청크 길이(초). None이면 default_chunk_duration 사용
            chunk_overlap_duration: 청크 겹침 길이(초). None이면 default_chunk_overlap_duration 사용
            response_format: 서버에서 지원하는 응답 포맷 (예: "json_object" / "text")
            extra_params: temperature, top_p 등 추가 파라미터를 딕셔너리로 전달

        Returns:
            서버의 JSON 응답
        """
        url = f"{self.base_url}/generate_vlm_captions"

        # 3. 프리셋에서 prompt / system_prompt 가져오기
        preset_prompt = None
        preset_system_prompt = None
        if preset_name:
            preset = self.prompt_presets.get(preset_name)
            if preset is None:
                raise ValueError(f"Unknown prompt preset: {preset_name}")
            preset_prompt = preset.prompt
            preset_system_prompt = preset.system_prompt

        final_prompt = prompt if prompt is not None else preset_prompt
        final_system_prompt = system_prompt if system_prompt is not None else preset_system_prompt

        if final_prompt is None:
            raise ValueError(
                "No prompt provided. Set either prompt=... or preset_name referencing a stored prompt."
            )

        cd = chunk_duration if chunk_duration is not None else self.default_chunk_duration
        cod = chunk_overlap_duration if chunk_overlap_duration is not None else self.default_chunk_overlap_duration

        payload: Dict[str, Any] = {
            # 서버 스펙에 따라 "id"가 리스트인지 단일 값인지 다를 수 있음.
            # 여기서는 단일 ID 사용을 가정.
            "id": video_id,
            "model": model,
            "prompt": final_prompt,
            "system_prompt": final_system_prompt,
            "chunk_duration": cd,
            "chunk_overlap_duration": cod,
            "response_format": {"type": response_format}
        }

        # system_prompt가 필요할 경우 포함
        if final_system_prompt is not None:
            payload["system_prompt"] = final_system_prompt

        # 추가 파라미터 (temperature, top_p, max_tokens 등)
        if extra_params:
            payload.update(extra_params)

        headers = {"Content-Type": "application/json"}

        # resp = requests.post(url, data=json.dumps(payload), headers=headers)
        # self._raise_for_error(resp, "generate_vlm_captions")
        # return resp.json()


        resp = requests.post(url, data=json.dumps(payload), headers=headers)
        self._raise_for_error(resp, "generate_vlm_captions")
        result = resp.json()
        # 서버 응답에 execution_time이 있으면 사용, 없으면 클라이언트 측 측정값 사용
        if "execution_time" not in result:
            result["execution_time"] = resp.elapsed.total_seconds()
        return result
    
    # ------------------------------------------------------------------
    # 3. 프롬프트 프리셋 관리 기능
    # ------------------------------------------------------------------
    def add_preset(self, name: str, prompt: str, system_prompt: Optional[str] = None) -> None:
        """
        새로운 프롬프트 프리셋 등록.
        """
        self.prompt_presets[name] = PromptPreset(prompt=prompt, system_prompt=system_prompt)

    def remove_preset(self, name: str) -> None:
        """
        프롬프트 프리셋 삭제.
        """
        if name in self.prompt_presets:
            del self.prompt_presets[name]

    def get_preset(self, name: str) -> PromptPreset:
        """
        프리셋 조회.
        """
        preset = self.prompt_presets.get(name)
        if preset is None:
            raise ValueError(f"Unknown prompt preset: {name}")
        return preset

    def list_presets(self) -> Dict[str, PromptPreset]:
        """
        등록된 모든 프리셋 반환.
        """
        return dict(self.prompt_presets)
    
    @staticmethod
    def save_json(data: dict, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    # ------------------------------------------------------------------
    # 내부 유틸
    # ------------------------------------------------------------------
    @staticmethod
    def _raise_for_error(resp: requests.Response, context: str) -> None:
        """HTTP 에러 공통 처리."""
        try:
            resp.raise_for_status()
        except requests.HTTPError as e:
            try:
                err_json = resp.json()
                msg = err_json.get("message") or err_json
            except Exception:
                msg = resp.text
            raise RuntimeError(f"[VSSClient:{context}] HTTP {resp.status_code} - {msg}") from e


# ----------------------------------------------------------------------
# 사용 예시 (직접 실행 시)
# ----------------------------------------------------------------------
if __name__ == "__main__":
    # 예시: 환경변수나 하드코딩으로 VSS 서버 URL 지정
    base_url = os.environ.get("VIA_BACKEND", "http://localhost:8100")

    # 3. 내부 프롬프트 프리셋 정의
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
You are given a video generated from a digital twin simulation viewed from a bird’s-eye view (BEV).
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
"""
                           ),
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
  {"HH:MM:SS": [3, 5]},
  {"HH:MM:SS": [1, 2, 4]}
]
"""
            ),
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

"""
            ),
        )
    }

    client = VSSClient(
        base_url=base_url,
        default_chunk_duration=2,
        prompt_presets=presets,
    )
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    
    # 아래 코드는 실제로 돌릴 때 필요한 ID/모델 이름으로 바꿔서 사용
    # 0. 비디오 삭제 
    # delete_resp = client.delete_video("b4f6562c-f939-4b4d-a7a2-0ba0358e788b")
    # print(delete_resp)

    # 1. 비디오 업로드
    upload_resp = client.upload_video("../video/video_19.mp4")
    video_id = upload_resp["id"]
    print(f"Uploaded video ID: {video_id}")

    # # # # 2. VLM 캡션 생성 요청
    # result = client.generate_vlm_captions(
    #     video_id="b4f6562c-f939-4b4d-a7a2-0ba0358e788b",
    #     # model="Qwen3-VL-8B-Instruct",
    #     model="gpt-4o",
    #     preset_name="simple_view"
    #     # preset_name="twin_view"
    # )
    # save_path = f"../outputs/gpt_video_18_{timestamp}.json"
    # client.save_json(result, save_path)
    # print(json.dumps(result, indent=2, ensure_ascii=False))
