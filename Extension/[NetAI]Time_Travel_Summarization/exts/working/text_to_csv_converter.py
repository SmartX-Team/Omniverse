import csv
import re


def text_to_csv(text, output_file, delimiter=None):
    """텍스트를 CSV로 변환"""
    
    # 구분자 자동 감지
    if delimiter is None:
        delimiters = ['\t', ',', ';', '|', ' ']
        counts = {d: text.count(d) for d in delimiters}
        delimiter = max(counts, key=counts.get)
    
    # 텍스트 파싱
    lines = [line.strip() for line in text.strip().split('\n') if line.strip()]
    
    rows = []
    for line in lines:
        if delimiter == ' ':
            row = re.split(r'\s+', line)
        else:
            row = [cell.strip() for cell in line.split(delimiter)]
        rows.append(row)
    
    # CSV 저장
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    
    print(f"✅ 변환 완료: {output_file} ({len(rows)}행)")


def file_to_csv(input_file, output_file, delimiter=None):
    """파일을 읽어서 CSV로 변환"""
    with open(input_file, 'r', encoding='utf-8') as f:
        text = f.read()
    text_to_csv(text, output_file, delimiter)


# 사용 예제
if __name__ == "__main__":
    # 예제 1: 탭 구분 데이터
    # tab_data = "이름\t나이\t직업\n홍길동\t30\t개발자\n김철수\t25\t디자이너"
    # text_to_csv(tab_data, "output1.csv")
    
    # # 예제 2: 쉼표 구분 데이터  
    # csv_data = "name,age,job\nJohn,30,Developer\nJane,25,Designer"
    # text_to_csv(csv_data, "output2.csv", ",")
    
    # 예제 3: 파일 변환
    file_to_csv("./merged_trajectory.txt", "merged_trajectory.csv")