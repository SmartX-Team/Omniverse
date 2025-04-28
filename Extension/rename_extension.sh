#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuration ---
OLD_PROJECT_DIR="[NetAI_Intern]NiKI_Test_ROS"
NEW_PROJECT_DIR="GIST_Husky_IsaacSim_ROS"

OLD_EXT_DIR_REL="exts/ni.ki.test.ros"
NEW_EXT_DIR_REL="exts/gist.husky.isaacsim_ros"
NEW_EXT_PKG_REL="gist/husky/isaacsim_ros" # New package path relative to extension root

OLD_SCRIPTS_DIR_REL="Standalone_Scripts"
NEW_SCRIPTS_DIR_REL="scripts"

OLD_USD_DIR_REL="Husky_USD"
OLD_USD_FILE="Ni_KI_Husky.usd"
NEW_USD_DIR_REL="$NEW_EXT_DIR_REL/data" # Place USD inside the extension's data folder
NEW_USD_FILE="husky_model.usd"

# --- Safety Check ---
if [ ! -d "$OLD_PROJECT_DIR" ]; then
  echo "Error: Directory '$OLD_PROJECT_DIR' not found in the current path."
  echo "Please run this script from the parent directory ('~/Downloads/Omniverse/Extension')."
  exit 1
fi

echo "Starting renaming and restructuring process..."

# 1. Rename top-level project directory
echo "Renaming project directory '$OLD_PROJECT_DIR' to '$NEW_PROJECT_DIR'..."
mv "$OLD_PROJECT_DIR" "$NEW_PROJECT_DIR"
cd "$NEW_PROJECT_DIR" # Move into the new project directory for relative paths

# 2. Rename extension directory
OLD_EXT_DIR="$OLD_EXT_DIR_REL" # Path relative to project root
NEW_EXT_DIR="$NEW_EXT_DIR_REL"
if [ -d "$OLD_EXT_DIR" ]; then
  echo "Renaming extension directory '$OLD_EXT_DIR' to '$NEW_EXT_DIR'..."
  mv "$OLD_EXT_DIR" "$NEW_EXT_DIR"
else
  echo "Warning: Old extension directory '$OLD_EXT_DIR' not found. Skipping rename."
fi

# 3. Create new Python package structure
NEW_PKG_PATH="$NEW_EXT_DIR/$NEW_EXT_PKG_REL"
echo "Creating new Python package directory structure '$NEW_PKG_PATH'..."
mkdir -p "$NEW_PKG_PATH"

# 4. Move and Rename Python files
OLD_PKG_DIR_TO_REMOVE="$NEW_EXT_DIR/ni" # Old 'ni' folder relative to NEW extension dir
OLD_PKG_PATH_ABS="$OLD_PKG_DIR_TO_REMOVE/ki/test/ros" # Absolute path to old package files

if [ -d "$OLD_PKG_PATH_ABS" ]; then
  echo "Moving and renaming Python files..."
  # Move and rename individual files
  mv "$OLD_PKG_PATH_ABS/__init__.py" "$NEW_PKG_PATH/__init__.py"
  mv "$OLD_PKG_PATH_ABS/extension.py" "$NEW_PKG_PATH/extension.py"
  mv "$OLD_PKG_PATH_ABS/isaac_sensor.py" "$NEW_PKG_PATH/sensors.py"
  mv "$OLD_PKG_PATH_ABS/ros2_recivers.py" "$NEW_PKG_PATH/ros_listeners.py" # Renamed
  mv "$OLD_PKG_PATH_ABS/camera_ros_publisher.py" "$NEW_PKG_PATH/camera_publishers.py" # Renamed
  mv "$OLD_PKG_PATH_ABS/slice_of_life_adjustments.py" "$NEW_PKG_PATH/utils.py" # Renamed

  # 5. Remove old Python package structure ('ni' folder)
  echo "Removing old Python package structure '$OLD_PKG_DIR_TO_REMOVE'..."
  rm -rf "$OLD_PKG_DIR_TO_REMOVE"
else
  echo "Warning: Old Python package path '$OLD_PKG_PATH_ABS' not found. Skipping file move and old structure removal."
fi

# 6. Rename Standalone Scripts directory
OLD_SCRIPTS_DIR="$OLD_SCRIPTS_DIR_REL"
NEW_SCRIPTS_DIR="$NEW_SCRIPTS_DIR_REL"
if [ -d "$OLD_SCRIPTS_DIR" ]; then
  echo "Renaming scripts directory '$OLD_SCRIPTS_DIR' to '$NEW_SCRIPTS_DIR'..."
  mv "$OLD_SCRIPTS_DIR" "$NEW_SCRIPTS_DIR"

  # 7. Rename files within the new scripts directory
  echo "Renaming script files..."
  # Use find for robustness, handle potential errors if files don't exist
  find "$NEW_SCRIPTS_DIR" -depth 1 -name "tank_controller_cosmo.py" -execdir mv {} tank_controller.py \; || echo "tank_controller_cosmo.py not found or rename failed."
  find "$NEW_SCRIPTS_DIR" -depth 1 -name "virtual_joystick_2.py" -execdir mv {} joystick_controller.py \; || echo "virtual_joystick_2.py not found or rename failed."
  find "$NEW_SCRIPTS_DIR" -depth 1 -name "ros2_kafka_producer.py" -execdir mv {} kafka_producer.py \; || echo "ros2_kafka_producer.py not found or rename failed."
  find "$NEW_SCRIPTS_DIR" -depth 1 -name "ros2_kafka_reader.py" -execdir mv {} kafka_reader.py \; || echo "ros2_kafka_reader.py not found or rename failed."
else
 echo "Warning: Standalone scripts directory '$OLD_SCRIPTS_DIR' not found. Skipping rename."
fi

# 8. Move and Rename Husky USD file
OLD_USD_PATH="$OLD_USD_DIR_REL/$OLD_USD_FILE"
NEW_USD_DIR="$NEW_USD_DIR_REL" # Path relative to project root
NEW_USD_PATH="$NEW_USD_DIR/$NEW_USD_FILE"

if [ -f "$OLD_USD_PATH" ]; then
  echo "Creating data directory '$NEW_USD_DIR'..."
  mkdir -p "$NEW_USD_DIR"
  echo "Moving and renaming '$OLD_USD_PATH' to '$NEW_USD_PATH'..."
  mv "$OLD_USD_PATH" "$NEW_USD_PATH"

  # 9. Remove old Husky_USD directory
  if [ -d "$OLD_USD_DIR_REL" ]; then
    echo "Removing old USD directory '$OLD_USD_DIR_REL'..."
    rm -rf "$OLD_USD_DIR_REL"
  fi
else
  echo "Warning: Old USD file '$OLD_USD_PATH' not found. Skipping move."
fi


echo "-------------------------------------------------------"
echo "Directory restructuring and file renaming complete."
echo "Please perform the following MANUAL steps:"
echo "1. Update '$NEW_EXT_DIR/config/extension.toml':"
echo "   - Set '[package].name' to 'gist.husky.isaacsim_ros'"
echo "   - Update title, description, author etc."
echo "   - Set 'python.module = \"gist.husky.isaacsim_ros\"'"
echo "2. Update Python import statements in ALL .py files inside '$NEW_PKG_PATH/' to reflect new filenames (e.g., 'from .sensors import ...')."
echo "3. (Optional) Rename class 'NiKiTestRosExtension' to 'HuskyIsaacSimRosExtension' in '$NEW_PKG_PATH/extension.py'."
echo "4. Search and replace any hardcoded paths or names referencing the old structure within the Python code."
echo "5. Write/Update README.md files (Project root, '$NEW_EXT_DIR/docs/', '$NEW_SCRIPTS_DIR/')."
echo "6. (Optional) Review and potentially merge/refactor '$NEW_PKG_PATH/ros_listeners.py' and '$NEW_PKG_PATH/camera_publishers.py' into '$NEW_PKG_PATH/ros_interface.py' or similar."
echo "-------------------------------------------------------"

exit 0