import json
import os
from typing import List, Dict, Optional

class PresetLoader:
    """Handle preset file loading and validation"""
    
    @staticmethod
    def load_preset(file_path: str) -> Optional[Dict]:
        """Load and validate preset JSON file"""
        if not os.path.exists(file_path):
            print(f"[Error] Preset file not found: {file_path}")
            return None
        
        if not file_path.endswith('.json'):
            print(f"[Error] Preset file must be JSON format: {file_path}")
            return None
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Validate structure
            if 'cameras' not in data:
                print("[Error] Preset file missing 'cameras' field")
                return None
            
            # Validate each camera entry
            for idx, camera in enumerate(data['cameras']):
                if 'camera_path' not in camera:
                    print(f"[Error] Camera {idx} missing required 'camera_path'")
                    return None
                
                # Set defaults for optional fields
                if 'output_dir' not in camera:
                    camera['output_dir'] = "/home/netai/Documents/traffic_captures"
                if 'capture_mode' not in camera:
                    camera['capture_mode'] = "LOCAL"
            
            print(f"[Info] Loaded preset with {len(data['cameras'])} cameras")
            return data
            
        except json.JSONDecodeError as e:
            print(f"[Error] Invalid JSON format: {e}")
            return None
        except Exception as e:
            print(f"[Error] Failed to load preset: {e}")
            return None
    
    @staticmethod
    def save_preset(cameras: List[Dict], file_path: str) -> bool:
        """Save current cameras to preset file"""
        try:
            data = {"cameras": cameras}
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"[Info] Saved preset to: {file_path}")
            return True
        except Exception as e:
            print(f"[Error] Failed to save preset: {e}")
            return False