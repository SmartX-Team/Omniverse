import json
import os
from typing import Dict, Any, Optional

class ConfigManager:
    """설정 파일 관리 클래스"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Args:
            config_path: 설정 파일 경로. None이면 기본 경로 사용
        """
        if config_path is None:
            # 현재 모듈과 같은 디렉토리의 config.json 사용
            current_dir = os.path.dirname(os.path.abspath(__file__))
            self.config_path = os.path.join(current_dir, "config.json")
        else:
            self.config_path = config_path
        
        self._config = None
        self.load_config()
    
    def load_config(self) -> bool:
        """설정 파일 로드"""
        try:
            print(f"Loading config from: {self.config_path}")
            with open(self.config_path, 'r', encoding='utf-8') as file:
                self._config = json.load(file)
            print("Successfully loaded config file")
            return True
        except FileNotFoundError:
            print(f"Config file not found at: {self.config_path}")
            self._create_default_config()
            return False
        except json.JSONDecodeError as e:
            print(f"Error parsing config file: {e}")
            return False
        except Exception as e:
            print(f"Error loading config file: {e}")
            return False
    
    def _create_default_config(self):
        """기본 설정 파일 생성"""
        default_config = {
            "postgres": {
                "db_name": "uwb_tracking",
                "db_user": "postgres",
                "db_password": "password",
                "db_host": "localhost",
                "db_port": 5432
            },
            "kafka": {
                "bootstrap_servers": "210.125.85.62:9094",
                "topic_name": "omniverse-uwb",
                "group_id": "netai-uwb-group"
            },
            "uwb": {
                "default_space_id": 1,
                "update_interval": 300,
                "coordinate_precision": 2
            },
            "omniverse": {
                "default_y_height": 90.0,
                "special_heights": {
                    "15": 105.0
                }
            }
        }
        
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as file:
                json.dump(default_config, file, indent=4, ensure_ascii=False)
            self._config = default_config
            print(f"Created default config file at: {self.config_path}")
        except Exception as e:
            print(f"Error creating default config file: {e}")
            self._config = default_config
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        점 표기법으로 설정값 조회
        
        Args:
            key_path: "postgres.db_name" 형태의 키 경로
            default: 키가 없을 때 반환할 기본값
        
        Returns:
            설정값 또는 기본값
        """
        if self._config is None:
            return default
        
        keys = key_path.split('.')
        value = self._config
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    def get_postgres_config(self) -> Dict[str, Any]:
        """PostgreSQL 설정 반환"""
        postgres_config = self.get("postgres", {})
        
        # psycopg2 표준 매개변수명으로 변환
        return {
            'database': postgres_config.get('db_name'),
            'user': postgres_config.get('db_user'), 
            'password': postgres_config.get('db_password'),
            'host': postgres_config.get('db_host'),
            'port': postgres_config.get('db_port')
        }
    def get_kafka_config(self) -> Dict[str, Any]:
        """Kafka 설정 반환"""
        return self.get("kafka", {})
    
    def get_uwb_config(self) -> Dict[str, Any]:
        """UWB 관련 설정 반환"""
        return self.get("uwb", {})
    
    def get_omniverse_config(self) -> Dict[str, Any]:
        """Omniverse 관련 설정 반환"""
        return self.get("omniverse", {})
    
    def set(self, key_path: str, value: Any) -> bool:
        """
        점 표기법으로 설정값 변경
        
        Args:
            key_path: "postgres.db_name" 형태의 키 경로
            value: 설정할 값
        
        Returns:
            성공 여부
        """
        if self._config is None:
            return False
        
        keys = key_path.split('.')
        target = self._config
        
        try:
            # 마지막 키 전까지 이동
            for key in keys[:-1]:
                if key not in target:
                    target[key] = {}
                target = target[key]
            
            # 마지막 키에 값 설정
            target[keys[-1]] = value
            return True
        except Exception as e:
            print(f"Error setting config value: {e}")
            return False
    
    def save_config(self) -> bool:
        """현재 설정을 파일에 저장"""
        if self._config is None:
            return False
        
        try:
            with open(self.config_path, 'w', encoding='utf-8') as file:
                json.dump(self._config, file, indent=4, ensure_ascii=False)
            print(f"Config saved to: {self.config_path}")
            return True
        except Exception as e:
            print(f"Error saving config file: {e}")
            return False
    
    def reload_config(self) -> bool:
        """설정 파일 다시 로드"""
        return self.load_config()
    
    @property
    def config(self) -> Dict[str, Any]:
        """전체 설정 딕셔너리 반환"""
        return self._config or {}

# 전역 설정 관리자 인스턴스
_config_manager = None

def get_config_manager() -> ConfigManager:
    """전역 설정 관리자 인스턴스 반환"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager