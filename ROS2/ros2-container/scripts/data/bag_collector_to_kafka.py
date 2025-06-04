import os
import subprocess
import time
import shutil
import signal
import atexit
import threading
from datetime import datetime
from kafka import KafkaProducer
from kafka.errors import KafkaError

# Global variables for shutdown handling
shutdown_event = threading.Event()
current_process = None
producer_instance = None

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    print(f"\nReceived signal {signum}. Initiating graceful shutdown...")
    shutdown_event.set()
    
    # Terminate current recording process if running
    if current_process:
        try:
            print("Terminating recording process...")
            os.killpg(os.getpgid(current_process.pid), signal.SIGINT)
            current_process.wait(timeout=5)
        except (subprocess.TimeoutExpired, ProcessLookupError, OSError):
            try:
                os.killpg(os.getpgid(current_process.pid), signal.SIGKILL)
            except (ProcessLookupError, OSError):
                pass
    
    # Close Kafka producer
    if producer_instance:
        try:
            print("Closing Kafka producer...")
            producer_instance.flush(timeout=3)  # Force send buffered messages
            producer_instance.close(timeout=3)
        except Exception as e:
            print(f"Error closing producer: {e}")
    
    print("Shutdown complete.")

def cleanup_on_exit():
    """Final cleanup when program exits"""
    if current_process:
        try:
            os.killpg(os.getpgid(current_process.pid), signal.SIGKILL)
        except (ProcessLookupError, OSError):
            pass

# Register signal handlers and cleanup
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
atexit.register(cleanup_on_exit)

# --- Configuration ---
KAFKA_BROKER = os.environ.get('KAFKA_BROKER', '10.79.1.1:9094')
KAFKA_TOPIC = os.environ.get('KAFKA_TOPIC_BAGS', 'ros-bags-archive')
RECORD_DURATION_SECONDS = int(os.environ.get('RECORD_DURATION_SECONDS', 60))
RECORD_INTERVAL_SECONDS = int(os.environ.get('RECORD_INTERVAL_SECONDS', 10))
DEPLOYMENT_MODE = os.environ.get('DEPLOYMENT_MODE', 'isaac_sim')

DEFAULT_TOPICS = {
    'isaac_sim': [
        '/cmd_vel', '/odom/virtual', '/imu/virtual', '/tf', '/tf_static'
    ],
    'real_robot': [
        '/cmd_vel', '/odom', '/imu/data', '/tf', '/tf_static',
        '/sensors/lidar_0/points', '/sensors/camera_0/color/image_raw',
        '/platform/odom', '/platform/joint_states', '/mcu/status'
    ]
}

if os.environ.get('BAG_TOPICS'):
    BAG_TOPICS = os.environ.get('BAG_TOPICS').split()
    print(f"Using user-specified BAG_TOPICS: {BAG_TOPICS}")
else:
    BAG_TOPICS = DEFAULT_TOPICS.get(DEPLOYMENT_MODE, DEFAULT_TOPICS['isaac_sim'])
    print(f"Using default topics for {DEPLOYMENT_MODE} mode: {BAG_TOPICS}")

BASE_PATH = '/tmp/rosbags'

def main():
    """Main execution function with improved shutdown handling"""
    global producer_instance
    
    print("--- ROS2 Bag Collector to Kafka Agent Started ---")
    print(f"Kafka Broker: {KAFKA_BROKER}, Topic: {KAFKA_TOPIC}")
    print(f"Deployment Mode: {DEPLOYMENT_MODE}")
    print(f"Recording cycle: {RECORD_DURATION_SECONDS}s recording + {RECORD_INTERVAL_SECONDS}s wait")
    print(f"Recording topics: {BAG_TOPICS}")
    print("Press Ctrl+C to stop gracefully...")

    try:
        # Initialize Kafka Producer with shorter timeouts
        producer_instance = KafkaProducer(
            bootstrap_servers=KAFKA_BROKER,
            value_serializer=lambda v: v,
            acks='all',
            retries=3,  # Reduced retries for faster shutdown
            request_timeout_ms=10000,  # 10 second timeout
            max_request_size=50 * 1024 * 1024
        )
        print("Kafka Producer connection successful.")
    except KafkaError as e:
        print(f"Kafka Producer connection failed: {e}")
        return

    try:
        while not shutdown_event.is_set():
            if shutdown_event.is_set():
                break
            run_cycle(producer_instance)
            
            # Check for shutdown during wait period
            for _ in range(RECORD_INTERVAL_SECONDS):
                if shutdown_event.is_set():
                    break
                time.sleep(1)
                
    except Exception as e:
        print(f"Unexpected error: {e}")
    finally:
        print("Main loop terminated.")

def run_cycle(producer: KafkaProducer):
    """Single cycle with improved error handling"""
    global current_process
    
    if shutdown_event.is_set():
        return
        
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    bag_name = f"bag_{timestamp}"
    bag_path = os.path.join(BASE_PATH, bag_name)
    
    os.makedirs(BASE_PATH, exist_ok=True)
    
    record_command = [
        'ros2', 'bag', 'record', '-o', bag_path,
        '--compression-mode', 'file',
        '--compression-format', 'zstd'
    ] + BAG_TOPICS

    print(f"\n[{timestamp}] Starting recording... ({RECORD_DURATION_SECONDS}s duration)")
    
    try:
        current_process = subprocess.Popen(
            record_command, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid
        )
        
        # Sleep with interruption check
        start_time = time.time()
        while time.time() - start_time < RECORD_DURATION_SECONDS:
            if shutdown_event.is_set():
                break
            time.sleep(0.1)
        
        # Terminate recording
        if current_process and current_process.poll() is None:
            os.killpg(os.getpgid(current_process.pid), signal.SIGINT)
            
            try:
                current_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print("Force terminating recording process...")
                os.killpg(os.getpgid(current_process.pid), signal.SIGKILL)
                current_process.wait()
                
        current_process = None
        print("Recording completed.")
        
    except Exception as e:
        print(f"Error during recording: {e}")
        current_process = None
        return

    if shutdown_event.is_set():
        # Clean up bag directory if shutdown requested
        if os.path.exists(bag_path):
            shutil.rmtree(bag_path)
        return

    # Proceed with compression and transmission
    if not os.path.exists(bag_path) or not os.listdir(bag_path):
        print("Warning: No bag data recorded. Skipping.")
        if os.path.exists(bag_path):
            shutil.rmtree(bag_path)
        return

    # Compress and send (with shutdown checks)
    try:
        compressed_file_path = compress_bag(bag_path, bag_name)
        if compressed_file_path and not shutdown_event.is_set():
            send_to_kafka(producer, compressed_file_path)
    finally:
        # Always clean up
        cleanup_files(bag_path, compressed_file_path if 'compressed_file_path' in locals() else None)

def compress_bag(bag_path, bag_name):
    """Compress bag with shutdown check"""
    if shutdown_event.is_set():
        return None
        
    compressed_file_base = os.path.join(BASE_PATH, bag_name)
    print(f"Compressing to {compressed_file_base}.tar.gz...")
    
    try:
        compressed_file_path = shutil.make_archive(
            base_name=compressed_file_base,
            format='gztar',
            root_dir=BASE_PATH,
            base_dir=bag_name
        )
        print(f"Compression completed: {compressed_file_path}")
        return compressed_file_path
    except Exception as e:
        print(f"Compression error: {e}")
        return None

def send_to_kafka(producer, compressed_file_path):
    """Send to Kafka with timeout"""
    if shutdown_event.is_set():
        return
        
    try:
        with open(compressed_file_path, 'rb') as f:
            file_data = f.read()
            
        file_size_mb = len(file_data) / (1024 * 1024)
        print(f"Sending {file_size_mb:.2f} MB to Kafka...")
        
        if file_size_mb > 100:
            print(f"File too large ({file_size_mb:.2f} MB), skipping")
            return
            
        future = producer.send(
            KAFKA_TOPIC,
            key=os.path.basename(compressed_file_path).encode('utf-8'),
            value=file_data
        )
        future.get(timeout=30)  # Shorter timeout
        print("Kafka transmission successful.")
        
    except Exception as e:
        print(f"Kafka error: {e}")

def cleanup_files(bag_path, compressed_file_path):
    """Clean up files"""
    try:
        if bag_path and os.path.exists(bag_path):
            shutil.rmtree(bag_path)
        if compressed_file_path and os.path.exists(compressed_file_path):
            os.remove(compressed_file_path)
    except Exception as e:
        print(f"Cleanup error: {e}")

if __name__ == '__main__':
    main()