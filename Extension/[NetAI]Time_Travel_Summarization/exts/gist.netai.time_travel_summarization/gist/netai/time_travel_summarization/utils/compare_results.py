"""
VLM Object Detection 결과 비교 스크립트

이 스크립트는 VLM 모델의 예측 결과를 정답(Ground Truth)과 비교하여
Precision, Recall, F1 Score를 계산합니다.

사용법:
    # 기본 사용 (Ground Truth 2 사용, outputs 폴더의 모든 JSON 파일 처리)
    python compare_results.py
    
    # 특정 Ground Truth 선택 (1, 2, 3, 4 중 선택)
    python compare_results.py -g 1
    python compare_results.py --ground-truth 3
    
    # 특정 JSON 파일만 처리
    python compare_results.py -f video_19.json
    python compare_results.py --file Qwen3-VL-8B-Instruct_video_19_20251201_123456.json
    
    # Ground Truth와 파일 모두 지정
    python compare_results.py -g 2 -f video_19.json
    
    # 도움말 보기
    python compare_results.py -h

출력:
    - 콘솔: 상세한 비교 결과 (완전 일치, 부분 일치, 누락, 추가 예측)
    - 파일: compare_outputs/{원본파일명}__comparison_result.json
            (Precision, Recall, F1 Score 및 상세 결과 포함)

Ground Truth:
    1: video_18.mp4 (12개 이벤트)
    2: video_19.mp4 (7개 이벤트)  <- 기본값
    3: video_30.mp4 (9개 이벤트)
    4: video_31.mp4 (4개 이벤트)
"""

import json
import re
import argparse
from typing import Dict, Set, List, Tuple
from pathlib import Path


def parse_ground_truth(gt_text: str) -> Dict[str, Set[int]]:
    """
    정답지 텍스트를 파싱하여 딕셔너리로 변환
    
    Args:
        gt_text: 정답지 텍스트 (예: "00:00:28 1,4")
    
    Returns:
        {timestamp: set of object ids}
    """
    ground_truth = {}
    for line in gt_text.strip().split('\n'):
        if not line.strip():
            continue
        parts = line.strip().split()
        if len(parts) >= 2:
            timestamp = parts[0]
            obj_ids = set(int(x.strip()) for x in parts[1].split(','))
            ground_truth[timestamp] = obj_ids
    return ground_truth


def parse_prediction_json(json_path: str) -> Dict[str, List[Set[int]]]:
    """
    예측 결과 JSON 파일을 파싱
    - content가 코드블록(````json ... ````)인지
    - 일반 JSON 배열 문자열인지 둘 다 처리
    - 같은 timestamp에 대한 여러 예측을 List로 보존
    """
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    predictions = {}

    for chunk in data.get('chunk_responses', []):
        content = chunk.get('content', '').strip()

        # 1) 코드블록 JSON 처리
        json_match = re.search(r'```json\s*(\[.*?\])\s*```', content, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # 2) 일반 JSON 문자열일 경우
            # content 자체가 JSON 배열인지 확인
            if content.startswith('[') and content.endswith(']'):
                json_str = content
            else:
                # JSON이 아예 없으면 그냥 skip
                continue

        # JSON 로드 시도
        try:
            items = json.loads(json_str)
            for item in items:
                if isinstance(item, dict):
                    for timestamp, obj_ids in item.items():
                        obj_set = set(obj_ids)
                        # 같은 timestamp에 대해 중복된 예측은 제거하되,
                        # 다른 예측은 별도로 보존
                        if timestamp not in predictions:
                            predictions[timestamp] = []
                        # 동일한 예측이 아니면 추가 (set이므로 순서 무관 비교)
                        if obj_set not in predictions[timestamp]:
                            predictions[timestamp].append(obj_set)
        except json.JSONDecodeError as e:
            print(f"JSON 파싱 오류: {e}")
            print(f"문제 content:\n{content}")

    return predictions

def calculate_metrics(ground_truth: Dict[str, Set[int]], 
                     predictions: Dict[str, List[Set[int]]]) -> Tuple[float, float, float, Dict]:
    """
    Precision, Recall, F1 Score 계산
    완전 일치만 True Positive로 판정
    
    Args:
        ground_truth: 정답 데이터 {timestamp: set of object ids}
        predictions: 예측 데이터 {timestamp: list of sets of object ids}
    
    Returns:
        (precision, recall, f1, details)
    """
    true_positives = 0
    false_positives = 0
    false_negatives = 0
    
    details = {
        'correct': [],
        'missing_timestamps': [],
        'extra_timestamps': [],
        'incorrect_predictions': []
    }
    
    all_timestamps = set(ground_truth.keys()) | set(predictions.keys())
    
    for timestamp in sorted(all_timestamps):
        gt_objects = ground_truth.get(timestamp, set())
        pred_list = predictions.get(timestamp, [])
        
        if timestamp not in ground_truth:
            # 예측했지만 정답에 없는 타임스탬프 - 모두 FP
            for pred_objects in pred_list:
                details['extra_timestamps'].append({
                    'timestamp': timestamp,
                    'predicted': sorted(pred_objects)
                })
                false_positives += 1
                
        elif timestamp not in predictions or len(pred_list) == 0:
            # 정답에 있지만 예측하지 못한 타임스탬프 - FN
            details['missing_timestamps'].append({
                'timestamp': timestamp,
                'ground_truth': sorted(gt_objects)
            })
            false_negatives += 1
            
        else:
            # 둘 다 있는 경우 - 각 예측을 개별 판정
            for pred_objects in pred_list:
                if pred_objects == gt_objects:
                    # 완전 일치 - TP
                    true_positives += 1
                    details['correct'].append({
                        'timestamp': timestamp,
                        'objects': sorted(gt_objects)
                    })
                else:
                    # 불일치 - FP (틀린 예측)
                    false_positives += 1
                    details['incorrect_predictions'].append({
                        'timestamp': timestamp,
                        'ground_truth': sorted(gt_objects),
                        'predicted': sorted(pred_objects)
                    })
            
            # FN은 제거: 예측을 했으면 FN이 아님
    
    # Precision, Recall, F1 계산
    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    
    return precision, recall, f1, details


def print_comparison_report(precision: float, recall: float, f1: float, details: Dict):
    """비교 결과 리포트 출력"""
    print("=" * 80)
    print("Object Detection 비교 결과 (완전 일치만 정답)")
    print("=" * 80)
    print(f"\n📊 성능 지표:")
    print(f"  Precision: {precision:.2f} ({precision*100:.2f}%)")
    print(f"  Recall:    {recall:.2f} ({recall*100:.2f}%)")
    print(f"  F1 Score:  {f1:.2f} ({f1*100:.2f}%)")
    
    print(f"\n✅ 완전히 일치하는 예측: {len(details['correct'])}개")
    for item in details['correct']:
        print(f"  {item['timestamp']}: {item['objects']}")
    
    if details['incorrect_predictions']:
        print(f"\n❌ 틀린 예측: {len(details['incorrect_predictions'])}개")
        for item in details['incorrect_predictions']:
            print(f"  {item['timestamp']}:")
            print(f"    정답: {item['ground_truth']}")
            print(f"    예측: {item['predicted']}")
    
    if details['missing_timestamps']:
        print(f"\n⚠️  예측하지 못한 타임스탬프: {len(details['missing_timestamps'])}개")
        for item in details['missing_timestamps']:
            print(f"  {item['timestamp']}: {item['ground_truth']}")
    
    if details['extra_timestamps']:
        print(f"\n➕ 정답에 없는 타임스탬프 예측: {len(details['extra_timestamps'])}개")
        for item in details['extra_timestamps']:
            print(f"  {item['timestamp']}: {item['predicted']}")
    
    print("\n" + "=" * 80)


def get_ground_truth_texts():
    """모든 ground truth 데이터를 딕셔너리로 반환"""
    return {
        '1': """
00:00:00 2,4
00:00:28 1,4
00:00:30 2,4
00:00:31 2,4
00:00:33 3,4
00:00:39 1,4
00:00:40 1,4
00:00:41 1,3
00:00:42 1,3
00:00:51 2,4
00:00:54 2,3
00:00:56 1,2
00:00:57 1,2
        """,
        '2': """
00:00:01 1,2
00:00:02 1,2
00:00:31 2,3
00:00:41 1,3
00:00:48 1,2
00:00:54 3,4
00:00:55 3,4
        """,
        '3': """
00:00:06 1,4
00:00:15 1,3
00:00:19 3,4
00:00:21 2,4
00:00:23 2,3
00:00:24 2,3
00:00:43 1,3
00:00:45 2,4
00:00:57 3,4
        """,
        '4': """
00:00:18 2,3
00:00:30 2,3
00:00:42 1,2
00:00:46 2,4
        """
    }


def main():
    # 커맨드라인 인자 파싱
    parser = argparse.ArgumentParser(
        description="VLM 예측 결과를 정답과 비교하여 Precision, Recall, F1 Score를 계산합니다."
    )
    parser.add_argument(
        '-g', '--ground-truth',
        type=str,
        default='2',
        choices=['1', '2', '3', '4'],
        help='사용할 ground truth 번호 (기본값: 2)'
    )
    parser.add_argument(
        '-f', '--file',
        type=str,
        default=None,
        help='특정 JSON 파일만 처리 (파일명만 입력, 예: video_19.json)'
    )
    
    args = parser.parse_args()
    
    # Ground truth 데이터 가져오기
    ground_truth_texts = get_ground_truth_texts()
    selected_gt_text = ground_truth_texts[args.ground_truth]
    
    print(f"🎯 Ground Truth {args.ground_truth} 사용")
    print("=" * 80)
    
    # outputs 폴더 (utils와 같은 상위 디렉토리)
    outputs_dir = Path(__file__).parent.parent / "outputs"

    # compare_outputs 폴더 생성
    compare_outputs_dir = Path(__file__).parent.parent / "compare_outputs"
    compare_outputs_dir.mkdir(exist_ok=True)

    # JSON 파일 필터링
    if args.file:
        # 특정 파일만 처리
        json_files = [outputs_dir / args.file]
        if not json_files[0].exists():
            print(f"⚠️ 파일을 찾을 수 없습니다: {json_files[0]}")
            return
    else:
        # 모든 json 파일 순회
        json_files = sorted(outputs_dir.glob("*.json"))

    if not json_files:
        print("⚠️ outputs 폴더에 JSON 파일이 없습니다.")
        return

    for json_file in json_files:
        print(f"\n📄 처리 중: {json_file.name}")

        # 파싱
        ground_truth = parse_ground_truth(selected_gt_text)
        predictions = parse_prediction_json(str(json_file))

        # 메트릭 계산
        precision, recall, f1, details = calculate_metrics(ground_truth, predictions)

        # 결과 출력
        print_comparison_report(precision, recall, f1, details)

        # 결과 파일명: {json파일명}__comparison_result.json
        result_filename = f"{json_file.stem}__comparison_result.json"
        result_file = compare_outputs_dir / result_filename

        # JSON 저장 (소수점 둘째 자리로 반올림)
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump({
                'source_file': json_file.name,
                'metrics': {
                    'precision': round(precision, 2),
                    'recall': round(recall, 2),
                    'f1_score': round(f1, 2)
                },
                'details': details
            }, f, indent=2, ensure_ascii=False)

        print(f"📁 결과 저장 완료: {result_file}")

    print("\n🎉 모든 파일 처리 완료!")


if __name__ == "__main__":
    main()
