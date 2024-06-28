"""

--- 작성일 :2024.04.30 송인용 ---
프로젝트 특성상 시간 측정할 일이 많아서 시간 관련 작업들은 모와서 하나의 클래스로 만들어서 사용하고 있다.
지금은 작업하면서 시간 측정과 관련된 기능들이 필요하면 하나씩 구현하면서 사용하고 있는데, 나중에 Omniverse 안정화되면 
전문적으로 만들어진 time 유틸리티 코드 가져와서 사용하면 될 듯하다.

"""


import pytz
from datetime import datetime, timedelta, timezone

class TimeUtil:


    def __init__(self, timezone_offset='9'):
        """ Initialize the TimeUtil with a specific timezone offset (default is UTC-9). """
        self.timezone_offset = int(timezone_offset)


    """
    시간 구간 계산하는 함수
    DB의 timestamp는 오직 UTC-0 기준으로 저장되고 있다. 
    
    따라서 만약 현재 내가 UTC-9 지역에 있다고 파라미터를 보내면 9시간을 뺀 시간대로 계산해야한다.

    start , end 모두 파라미터로 넘어오지 않는다면 기존처럼 전체 시간대를 기준으로 계산을 진행한다.

    start 만 넘오면 end 는 현재 시간을 자동으로 입력하게 한다.

    end 만 넘어오면 start 는 end 전 전체 시간대가 파라미터로 넘어가게 한다.

    시간 구간이 필요하면 start, end 시간을 return하도록 하고 기존 우리가 작성한 쿼리에 사용하자
    
    """
    def calculate_time_bounds(self, start=None, end=None):
        """Calculate the start and end times for queries, adjusting for timezone."""
        utc_now = datetime.utcnow() 

        if start and isinstance(start, str):
            start = datetime.fromisoformat(start).replace(tzinfo=pytz.utc) - timedelta(hours=self.timezone_offset)
        elif start and isinstance(start, datetime):
            start = start.replace(tzinfo=pytz.utc) - timedelta(hours=self.timezone_offset)

        if end and isinstance(end, str):
            end = datetime.fromisoformat(end).replace(tzinfo=pytz.utc) - timedelta(hours=self.timezone_offset)
        elif end and isinstance(end, datetime):
            end = end.replace(tzinfo=pytz.utc) - timedelta(hours=self.timezone_offset)

        if start and not end:
            end = utc_now
        if end and not start:
            start = datetime.min.replace(tzinfo=pytz.utc)

        return start, end

    def get_period_bounds(self, period):
        """Calculate the start and end time for the current day, week, or month."""
        utc_now = datetime.utcnow()
        local_now = utc_now - timedelta(hours=self.timezone_offset)

        if period == 'daily':
            start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1) - timedelta(microseconds=1)
        elif period == 'weekly':
            start = local_now - timedelta(days=local_now.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(weeks=1) - timedelta(microseconds=1)
        elif period == 'monthly':
            start = local_now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            next_month = start.replace(day=28) + timedelta(days=4)
            end = next_month - timedelta(days=next_month.day)

        return start, end

    # UWB timestamp(표쥰 ISO 8601) 를 유닉스 시간으로 변경 (UTC-0 기준)
    def convert_to_unix_time(self, timestamp_str):
        # 타임스탬프 문자열을 datetime 객체로 변환
        # 'Z'는 UTC를 나타내므로 이를 datetime 객체로 변환할 때 UTC 시간대를 명시합니다.
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        # pytz를 사용하여 UTC 시간대를 명확히 설정
        utc_dt = dt.replace(tzinfo=pytz.UTC)
        # 유닉스 시간으로 변환
        unix_time = utc_dt.timestamp()
        return unix_time
    
    # Unix 시간을 datetime 객체로 변환 (UTC-0 기준)
    def convert_unix_time_to_utc_iso(self, unix_time):
        
        dt = datetime.fromtimestamp(unix_time, tz=timezone.utc)
        # datetime 객체를 ISO 8601 문자열로 변환
        utc_iso_timestamp = dt.isoformat()
        return utc_iso_timestamp
    
    # 현재 시점 시간 기준으로 start 시간과 END 시간 계싼해서 반환해줌
    # DB에는 통일된 시간으로 UTC-0 을 저장하므로 기본 시스템 UTC-9 시간을 UTC-0 으로 변환
    def calculate_utc_times(self, seconds):
    # 현재 시스템 시간을 UTC-9로 가정하고 있습니다.
        local_time = datetime.now()

        # UTC-9 시간대를 고려하여 9시간을 빼줍니다. 이렇게 하면 UTC 시간을 얻을 수 있습니다.
        start_timestamp_utc = local_time - timedelta(hours=9)

        # 종료 시간을 계산합니다. 주어진 초(seconds)와 추가적으로 0.1초를 더합니다.
        end_timestamp_utc = start_timestamp_utc + timedelta(seconds=seconds + 0.1)
        print(f"Type of start_timestamp_utc: {start_timestamp_utc}")
        print(f"Type of end_timestamp_utc: {end_timestamp_utc}")
        return start_timestamp_utc, end_timestamp_utc