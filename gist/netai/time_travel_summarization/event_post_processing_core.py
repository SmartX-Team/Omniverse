"""
Event Post-Processing Script
Processes VLM output JSON files to extract and consolidate event information.
Converts timestamps and object IDs to match core.py in-memory format.
"""

import json
import argparse
from pathlib import Path
from typing import List, Dict, Any
from collections import defaultdict


def load_json(file_path: str) -> Dict[str, Any]:
    """Load JSON file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def parse_content(content_str: str) -> List[Dict[str, List[int]]]:
    """
    Parse content string to extract timestamp and object lists.
    Supports both direct JSON and markdown code block wrapped JSON.
    
    Args:
        content_str: JSON string like '[{"HH:MM:SS": [1, 2]}, ...]'
                    or markdown wrapped: '```json\n[...]\n```'
    
    Returns:
        List of dictionaries with timestamp and object IDs
    """
    try:
        # Remove extra whitespace
        content_str = content_str.strip()
        if not content_str or content_str == "[]":
            return []
        
        # Check if content is wrapped in markdown code block
        if content_str.startswith("```"):
            # Extract JSON from markdown code block
            # Format: ```json\n[...]\n```
            lines = content_str.split('\n')
            # Remove first line (```json or ```) and last line (```)
            if len(lines) >= 3:
                json_content = '\n'.join(lines[1:-1])
            else:
                json_content = content_str
        else:
            json_content = content_str
        
        json_content = json_content.strip()
        if not json_content or json_content == "[]":
            return []
        
        parsed = json.loads(json_content)
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError as e:
        print(f"Warning: Failed to parse content: {content_str[:50]}... - {e}")
        return []


def format_timestamp_for_core(time_str: str, base_date: str = "2025-01-01") -> str:
    """
    Convert video timestamp (HH:MM:SS) to core.py CSV format (YYYY-MM-DD HH:MM:SS.000).
    
    Args:
        time_str: Time in "HH:MM:SS" format (e.g., "00:00:28")
        base_date: Base date to prepend (default: "2025-01-01")
    
    Returns:
        Timestamp in core.py CSV format: "2025-01-01 00:00:28.000"
    """
    return f"{base_date} {time_str}.000"


def format_objid_for_core(obj_num: int) -> str:
    """
    Convert object number to core.py objid format.
    
    Args:
        obj_num: Object number (e.g., 1, 2, 3)
    
    Returns:
        Object ID in core.py format: "obj001", "obj002", etc.
    """
    return f"obj{obj_num:03d}"


def consolidate_events(data: Dict[str, Any], base_date: str = "2025-01-01") -> Dict[str, List[List[str]]]:
    """
    VLM 의 chunk_responses 에서 모든 이벤트를 통합하여 정돈된 json 포맷으로 변환합니다.
    Consolidate all events from chunk_responses and convert to organized JSON format.
    
    Args:
        data: The loaded JSON data
        base_date: Base date for timestamp conversion
    
    Returns:
        Dictionary mapping timestamp to list of object ID groups
        Example: {"2025-01-01 00:00:28.000": [["obj001", "obj004"]], "2025-01-01 00:00:30.000": [["obj002", "obj004"]]}
    """
    consolidated = defaultdict(list)
    
    chunk_responses = data.get("chunk_responses", [])
    
    for chunk in chunk_responses:
        content = chunk.get("content", "")
        events = parse_content(content)
        
        for event in events:
            # Each event is like {"00:00:28": [1, 4]}
            for timestamp, obj_list in event.items():
                if obj_list:  # Only add non-empty lists
                    # Convert timestamp to core.py format
                    formatted_timestamp = format_timestamp_for_core(timestamp, base_date)
                    # Convert object IDs to core.py format
                    formatted_objids = [format_objid_for_core(obj_num) for obj_num in obj_list]
                    consolidated[formatted_timestamp].append(formatted_objids)
    
    return dict(consolidated)


def save_jsonl(events: Dict[str, List[List[str]]], output_path: str):
    """
    Save consolidated events to JSONL format with core.py compatible format.
    Each line: {"2025-01-01 00:00:28.000": [["obj001", "obj004"]]}
    
    Args:
        events: Consolidated events dictionary
        output_path: Output file path
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        for timestamp in sorted(events.keys()):
            obj_groups = events[timestamp]
            line = {timestamp: obj_groups}
            f.write(json.dumps(line, ensure_ascii=False) + '\n')
    
    print(f"Saved consolidated events to: {output_path}")


def save_summary_json(events: Dict[str, List[List[str]]], output_path: str, original_data: Dict[str, Any]):
    """
    Save a summary JSON file with metadata and consolidated events.
    
    Args:
        events: Consolidated events dictionary
        output_path: Output file path
        original_data: Original JSON data for metadata
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    summary = {
        "source_id": original_data.get("id", ""),
        "model": original_data.get("model", ""),
        "execution_time": original_data.get("execution_time", 0),
        "total_events": len(events),
        "total_timestamps": len(events),
        "events": events
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    print(f"Saved summary JSON to: {output_path}")


def print_statistics(events: Dict[str, List[List[str]]]):
    """Print statistics about the processed events."""
    total_timestamps = len(events)
    total_event_groups = sum(len(groups) for groups in events.values())
    
    print("\n=== Event Statistics ===")
    print(f"Total unique timestamps: {total_timestamps}")
    print(f"Total event groups: {total_event_groups}")
    
    if events:
        print(f"\nFirst event: {list(events.keys())[0]}")
        print(f"Last event: {list(events.keys())[-1]}")
        
        # Count object involvement
        all_objects = set()
        for groups in events.values():
            for group in groups:
                all_objects.update(group)
        print(f"Unique objects involved: {sorted(all_objects)}")


def main():
    parser = argparse.ArgumentParser(
        description="Process VLM event detection output JSON files"
    )
    parser.add_argument(
        "input_file",
        type=str,
        help="Input JSON file (e.g., video_18_20251113_232343.json)"
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="Output JSONL file path (default: input_name_processed.jsonl)"
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Also save a summary JSON file"
    )
    parser.add_argument(
        "--date",
        type=str,
        default="2025-01-01",
        help="Base date for timestamp conversion (default: 2025-01-01)"
    )
    
    args = parser.parse_args()
    
    # Load input JSON
    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        return
    
    print(f"Loading: {input_path}")
    data = load_json(str(input_path))
    
    # Process events
    print(f"Processing events with base date: {args.date}")
    events = consolidate_events(data, base_date=args.date)
    
    # Print statistics
    print_statistics(events)
    
    # Determine output path
    if args.output:
        output_path = args.output
    else:
        # Create intermediate_results directory at the same level as outputs
        output_dir = input_path.parent.parent / "intermediate_results"
        output_dir.mkdir(exist_ok=True)
        output_path = str(output_dir / f"{input_path.stem}_intermediate.jsonl")
    
    # Save JSONL
    save_jsonl(events, output_path)
    
    # Optionally save summary JSON
    if args.summary:
        summary_path = str(Path(output_path).with_suffix('.json'))
        save_summary_json(events, summary_path, data)
    
    print("\n✓ Processing complete!")


if __name__ == "__main__":
    main()
