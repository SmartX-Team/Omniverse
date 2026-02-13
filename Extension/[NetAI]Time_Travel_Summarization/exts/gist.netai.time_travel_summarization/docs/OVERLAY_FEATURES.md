# Overlay Features Documentation

## Overview
The TimeTravel extension now includes VLM-friendly overlay features for visualizing object information in the viewport.

## Features

### 1. Time Display Overlay
- **Location**: Bottom-right corner of viewport
- **Style**: Dark background (0xFF1A1A1A) with green border (0xFF00FF00)
- **Content**: 
  - Date: YYYY-MM-DD format (gray text, 24px)
  - Time: HH:MM:SS format (white text, 28px, bold)
- **Toggle**: Can be turned on/off via Overlay Control window

### 2. Object ID Overlay (NEW)
- **Purpose**: Display object IDs at their 3D world positions
- **Style**: 
  - White background (0xFFFFFFFF)
  - Black text (0xFF000000)
  - 60x25px label boxes
  - Billboard rendering (always faces camera)
- **Behavior**: 
  - Automatically updates when objects move
  - Uses `omni.ui.scene` for 3D world-space rendering
  - Labels appear at the exact coordinates of TimeTravel_Objects
- **Toggle**: Can be turned on/off via Overlay Control window

## Technical Implementation

### Files Modified

#### 1. `view_overlay.py`
- **New imports**: Added `omni.ui.scene as sc` and `from pxr import Gf`
- **New attributes**:
  - `_show_object_ids`: Boolean flag for object ID visibility
  - `_scene_view`: SceneView instance for 3D rendering
  - `_label_manipulators`: Dictionary to track label objects
  
- **New methods**:
  - `_create_object_id_overlay()`: Initializes 3D scene view and attaches to viewport
  - `_update_object_id_labels()`: Creates billboard labels at object positions
  - `set_object_ids_visible(visible)`: Toggle object ID label visibility
  
- **Modified methods**:
  - `__init__()`: Added object ID overlay initialization
  - `update()`: Now updates both time display and object ID labels
  - `destroy()`: Cleans up scene view properly

#### 2. `overlay_window.py`
- **Window size**: Changed from 80px to 120px height to accommodate new checkbox
- **New UI element**: 
  - "Show Object IDs" checkbox (default: enabled)
- **New method**:
  - `_on_objid_display_changed()`: Handler for object ID toggle

## Usage

1. **Enable Extension**: Load TimeTravel extension in Omniverse
2. **Load Data**: Configure and load trajectory data
3. **Open Overlay Control**: Window appears automatically
4. **Toggle Features**:
   - Check/uncheck "Show Time Display" for time overlay
   - Check/uncheck "Show Object IDs" for object ID labels

## Object ID Display Details

### Rendering Pipeline
1. Each frame, `_update_object_id_labels()` is called
2. Gets current object positions from `TimeTravelCore.get_data_at_time()`
3. Clears previous scene and recreates all labels
4. For each object:
   - Creates transform at (x, y, z) world position
   - Adds billboard transform (faces camera)
   - Renders white rectangle background
   - Renders black text with object ID

### Performance Considerations
- Labels are recreated each frame for dynamic positioning
- Uses `sc.Screen()` for screen-space rendering context
- Billboard rendering ensures labels are always readable
- Only renders when `_show_object_ids` is True

### Visual Style
```python
# White background box
sc.Rectangle(
    width=60,
    height=25,
    color=0xFFFFFFFF,  # White
    wireframe=False
)

# Black text label
sc.Label(
    objid,
    alignment=ui.Alignment.CENTER,
    color=0xFF000000,  # Black
    size=16
)
```

## VLM Integration Benefits

### For Bird's Eye View (BEV) Capture
1. **Object Identification**: Clear white-on-black labels are easily detectable by vision models
2. **Spatial Context**: Labels appear at exact object positions, maintaining spatial relationships
3. **Temporal Context**: Time display provides frame timestamp for video analysis
4. **High Contrast**: White background with black text ensures visibility in various lighting conditions

### For Video Analysis
- Consistent label positioning across frames
- Clear association between objects and their IDs
- Time overlay provides frame-by-frame temporal reference
- Toggle capability allows clean captures when labels not needed

## Future Enhancements (Not Implemented)

Potential additions:
- Coordinate display (x, y, z) next to object IDs
- Color-coded labels based on object properties
- Adjustable label size and font
- Custom label positioning (offset from object)
- Label clustering for nearby objects
- Performance optimization for large numbers of objects

## Troubleshooting

### Labels not appearing
1. Check "Show Object IDs" is enabled in Overlay Control
2. Verify TimeTravel data is loaded and objects exist
3. Check viewport camera is not too far from objects
4. Ensure scene view initialized successfully (check logs)

### Performance issues
- Consider reducing update frequency for large object counts
- Toggle labels off when not needed
- Check console for error messages

## Dependencies
- `omni.ui`: UI framework
- `omni.ui.scene`: 3D scene rendering
- `omni.kit.viewport.utility`: Viewport access
- `pxr.Gf`: Geometric math utilities
