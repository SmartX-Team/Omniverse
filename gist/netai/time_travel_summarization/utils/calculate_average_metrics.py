#!/usr/bin/env python3
"""
여러 JSON 비교 결과 파일에서 metrics의 평균을 계산하는 스크립트

사용법:
    python calculate_average_metrics.py <파일패턴>
    
예시:
    python calculate_average_metrics.py "../compare_outputs/video_18_*.json"
    python calculate_average_metrics.py "../compare_outputs/gpt_video_21_*.json"
"""

import json
import glob
import sys
import os
from typing import List, Dict


def load_metrics_from_files(file_pattern: str) -> List[Dict[str, float]]:
    """
    파일 패턴에 맞는 JSON 파일들을 읽어서 metrics 목록을 반환
    
    Args:
        file_pattern: glob 패턴 (예: "video_18_*.json")
        
    Returns:
        각 파일의 metrics 딕셔너리 리스트
    """
    files = sorted(glob.glob(file_pattern))
    
    if not files:
        print(f"❌ 패턴 '{file_pattern}'에 맞는 파일을 찾을 수 없습니다.")
        return []
    
    print(f"📂 {len(files)}개의 파일을 찾았습니다:")
    for f in files:
        print(f"   - {os.path.basename(f)}")
    print()
    
    metrics_list = []
    
    for file_path in files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            if 'metrics' not in data:
                print(f"⚠️  경고: {os.path.basename(file_path)}에 'metrics' 키가 없습니다. 건너뜁니다.")
                continue
                
            metrics = data['metrics']
            
            # 필요한 키가 있는지 확인
            required_keys = ['precision', 'recall', 'f1_score']
            if all(key in metrics for key in required_keys):
                metrics_list.append(metrics)
            else:
                missing = [key for key in required_keys if key not in metrics]
                print(f"⚠️  경고: {os.path.basename(file_path)}에 {missing} 키가 없습니다. 건너뜁니다.")
                
        except json.JSONDecodeError as e:
            print(f"❌ {os.path.basename(file_path)} JSON 파싱 오류: {e}")
        except Exception as e:
            print(f"❌ {os.path.basename(file_path)} 읽기 오류: {e}")
    
    return metrics_list


def calculate_average_metrics(metrics_list: List[Dict[str, float]]) -> Dict[str, float]:
    """
    metrics 리스트에서 평균을 계산
    
    Args:
        metrics_list: metrics 딕셔너리 리스트
        
    Returns:
        평균 metrics 딕셔너리
    """
    if not metrics_list:
        return {}
    
    n = len(metrics_list)
    
    avg_precision = sum(m['precision'] for m in metrics_list) / n
    avg_recall = sum(m['recall'] for m in metrics_list) / n
    avg_f1 = sum(m['f1_score'] for m in metrics_list) / n
    
    return {
        'precision': avg_precision,
        'recall': avg_recall,
        'f1_score': avg_f1,
        'num_files': n
    }


def print_results(avg_metrics: Dict[str, float], metrics_list: List[Dict[str, float]]):
    """결과를 보기 좋게 출력"""
    if not avg_metrics:
        print("❌ 계산할 데이터가 없습니다.")
        return
    
    print("=" * 60)
    print("📊 평균 Metrics 결과")
    print("=" * 60)
    print(f"분석된 파일 수: {avg_metrics['num_files']}개\n")
    
    print(f"Average Precision: {avg_metrics['precision']:.4f}")
    print(f"Average Recall:    {avg_metrics['recall']:.4f}")
    print(f"Average F1 Score:  {avg_metrics['f1_score']:.4f}")
    print("=" * 60)
    
    # 개별 파일 결과도 표시
    print("\n📋 개별 파일 Metrics:")
    print("-" * 60)
    print(f"{'#':<4} {'Precision':<12} {'Recall':<12} {'F1 Score':<12}")
    print("-" * 60)
    
    for i, m in enumerate(metrics_list, 1):
        print(f"{i:<4} {m['precision']:<12.4f} {m['recall']:<12.4f} {m['f1_score']:<12.4f}")
    print("-" * 60)


def save_results(avg_metrics: Dict[str, float], metrics_list: List[Dict[str, float]], 
                 output_file: str):
    """결과를 JSON 파일로 저장"""
    result = {
        'average_metrics': {
            'precision': avg_metrics['precision'],
            'recall': avg_metrics['recall'],
            'f1_score': avg_metrics['f1_score']
        },
        'num_files': avg_metrics['num_files'],
        'individual_metrics': metrics_list
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 결과가 '{output_file}'에 저장되었습니다.")


def main():
    if len(sys.argv) < 2:
        print("사용법: python calculate_average_metrics.py <파일패턴>")
        print("\n예시:")
        print('  python calculate_average_metrics.py "../compare_outputs/video_18_*.json"')
        print('  python calculate_average_metrics.py "../compare_outputs/gpt_video_21_*.json"')
        sys.exit(1)
    
    file_pattern = sys.argv[1]
    
    # 현재 작업 디렉토리 기준으로 상대 경로 처리
    if not os.path.isabs(file_pattern):
        file_pattern = os.path.abspath(file_pattern)
    
    print(f"🔍 파일 패턴: {file_pattern}\n")
    
    # metrics 로드
    metrics_list = load_metrics_from_files(file_pattern)
    
    if not metrics_list:
        sys.exit(1)
    
    # 평균 계산
    avg_metrics = calculate_average_metrics(metrics_list)
    
    # 결과 출력
    print_results(avg_metrics, metrics_list)
    
    # 결과 자동 저장
    # 패턴에서 출력 파일명 생성
    pattern_base = os.path.basename(file_pattern)
    # 와일드카드 패턴을 평균 결과 파일명으로 변환
    pattern_base = pattern_base.replace('*', '').replace('__', '_').replace('comparison_result.json', 'average_metrics.json')
    if not pattern_base.endswith('.json'):
        pattern_base = pattern_base.replace('.json', '') + 'average_metrics.json'
    
    output_dir = os.path.dirname(file_pattern)
    output_file = os.path.join(output_dir, pattern_base)
    
    save_results(avg_metrics, metrics_list, output_file)


if __name__ == '__main__':
    main()
