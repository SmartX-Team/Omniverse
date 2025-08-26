from enum import Enum

class CaptureMode(Enum):
    """Capture mode enumeration"""
    LOCAL = "LOCAL"           # Local file storage
    KAFKA = "KAFKA"          # Kafka streaming
    # Future modes can be added here
    # RTSP = "RTSP"          # RTSP streaming
    # S3 = "S3"              # S3 upload
    # HTTP = "HTTP"          # HTTP POST
    
    @classmethod
    def get_display_names(cls):
        """Get display names for UI"""
        return {
            cls.LOCAL: "Local Storage",
            cls.KAFKA: "Kafka Streaming",
            # cls.RTSP: "RTSP Stream",
            # cls.S3: "S3 Upload",
        }
    
    @classmethod
    def get_all_modes(cls):
        """Get all available modes for UI combo box"""
        return [mode.value for mode in cls]