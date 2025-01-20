# Omniverse Extensions Repository

This folder contains all Omniverse Extensions developed by various contributors at GIST NetAI and collaborating partners. 

In addition, each of these folders includes a **`deprecated/`** subfolder, where older or no longer maintained items are placed. 


## Extension Naming Convention

While the structure and code style of each extension may be relatively free, **please follow these naming conventions for the folder**:

1. **[NetAI]**:  
   For extensions primarily developed by graduate students in the NetAI group.  
   Example folder name: `[NetAI]_UWB_Tracking`
   
2. **[NetAI_Intern]**:  
   For extensions primarily developed by NetAI interns.  
   Example folder name: `[NetAI_Intern]_WebView_Custom`
   
3. **Other Collaborations**:  
   If the extension is a collaborative project with another lab or external partner, please include a suitable tag or naming scheme that identifies the partner.  
   Example folder name: `[ABC_Lab]_SomeExtension`

> **Reason**: We use these tags to track potential continuity or maintenance concerns.  
> Intern-developed extensions (`[NetAI_Intern]`) may require additional follow-up if the intern is no longer available.

## Current Extensions

Please keep this list updated whenever a **new extension** is added or **existing extensions** are significantly modified. When you create or refactor an extension, **please add or update an entry** in this table:

| Extension Name    | Description                                                                                                              | Status  |
|-------------------|--------------------------------------------------------------------------------------------------------------------------|---------|
| **UWB Tracking**  | Real-time tracking of MobileX Stations with attached UWB Tags in Omniverse.                                             | Active  |
| **Stations Align**| Facilitates the alignment of MobileX Station Models.                                                                    | Deprecated  |
| **Power Info**    | Retrieves visibility info from the Mobile X Cluster and reflects station information in Omniverse.                      | Deprecated  |
| **WebView**       | Generates a WebView VNC screen of an operational MobileX Station for the Visualization Center in the Omniverse App.      | Deprecated  |

> **Note**: If you are adding a brand-new extension, create a subfolder following the **Extension Naming Convention** above, then add a line to this table describing its purpose and status.

## Folder Structure

Inside each extension’s folder, consider including:
- A brief **README** explaining what the extension does, how to install/enable it, and any dependencies.
- Source code for the extension (e.g., `.py` files, config files).
- Optional subfolders for organization (e.g., `assets`, `docs`, etc.).

## Maintenance & Deprecation

If an extension is no longer supported or has been replaced, please move it to a `deprecated/` folder within this directory (following the main repository structure).
