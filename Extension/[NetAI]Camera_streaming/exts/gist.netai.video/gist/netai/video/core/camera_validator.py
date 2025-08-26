# core/camera_validator.py

class CameraValidator:
    @staticmethod
    def validate_camera(stage, camera_path: str, managed_cameras: dict) -> tuple[bool, str]:
        """Enhanced camera validation"""
        
        # 1. 빈 경로 체크
        if not camera_path or camera_path.strip() == "":
            return False, "Camera path cannot be empty"
        
        # 2. 경로 형식 체크
        if not camera_path.startswith("/"):
            return False, f"Invalid path format: '{camera_path}'. Must start with '/'"
        
        # 3. 이미 관리 중인지 체크
        if camera_path in managed_cameras:
            return False, f"Camera '{camera_path}' is already being managed"
        
        # 4. Stage 체크
        if not stage:
            return False, "USD Stage is not available"
        
        # 5. Prim 존재 여부 체크
        try:
            prim = stage.GetPrimAtPath(camera_path)
            if not prim or not prim.IsValid():
                return False, f"No valid prim found at path: '{camera_path}'"
            
            # 6. Camera 타입 체크
            if prim.GetTypeName() != "Camera":
                prim_type = prim.GetTypeName()
                return False, f"Prim at '{camera_path}' is type '{prim_type}', not 'Camera'"
                
        except Exception as e:
            return False, f"Error validating camera: {e}"
        
        return True, ""