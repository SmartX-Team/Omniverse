from .extension import *
"""
NetAI UWB Real-time Tracking System for Omniverse

This package provides real-time UWB tracking capabilities with coordinate transformation
between UWB local coordinates, Omniverse 3D coordinates, and GPS coordinates.

Modules:
- config_manager: Configuration file management
- db_manager: PostgreSQL database operations
- coordinate_transformer: Coordinate system transformations
- kafka_consumer: Real-time Kafka message processing
- main_extension: Main Omniverse Extension interface
"""


# Extension entry point
def get_extension():
    """Extension factory function"""
    return NetAIUWBTrackingExtension()

__version__ = "1.0.0"
__author__ = "NetAI Research Lab"
__description__ = "Real-time UWB tracking system for Omniverse"