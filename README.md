# Omniverse Extensions Repository

As of **25/01/20**, the repository structure has undergone a **major restructuring**.  
It now consists of two main folders at the root level:  
- **`extensions/`**: Contains Omniverse Extensions  
- **`backend/`**: Contains backend-related code or Docker configurations  
- **`ros2/`**:Contains ROS2 packages for simulation control and data publishing within Isaac Sim.

In addition, each of these folders includes a **`deprecated/`** subfolder, where older or no longer maintained items are placed. 

For any **Kubernetes (K8S) deployment YAML files** or other infrastructure-related files, please refer to our external repository at the following link [K8S Repo](https://github.com/SmartX-Team/twin-datapond).

Please be aware that backend server-related code is currently distributed across both the `backend/` folder and the K8S repository. 
When working with server components, make sure to check both locations for relevant code and configurations.

---

## Table of Contents
1. [Introduction](#introduction)
2. [Project Structure](#project-structure)
3. [Installation & Usage](#installation--usage)
4. [Contribution Guidelines](#contribution-guidelines)
5. [License](#license)
6. [Contact](#contact)

---

## Introduction

This repository serves as a central hub for various Omniverse Extensions. Embracing cloud-native microservices architecture, the GIST AI Graduate School's **NetAI Lab** develops and maintains Extensions necessary for implementing a digital twin of the AI Graduate School space. This initiative will continue to expand as part of our research on implementing and validating **Cloud-native Digital Twin Services**. The scope of this repository is indicated by the red rectangles in Fig 1.


![Github Descrpition](https://github.com/user-attachments/assets/c72c1cb9-444a-4fe0-99e1-1ca9e346ffca)


---

## Project Structure

Below is an overview of the main folders in this repository:

- **`extensions/`**  
  Contains various Omniverse Extensions (e.g., UWB Tracking, Stations Align, etc.).  
  - **`deprecated/`**: Houses older or no longer actively maintained extensions.

- **`backend/`**  
  Contains backend-related code and Docker configurations.  
  - **`deprecated/`**: Houses older or no longer actively maintained backend resources.

- **`ros2/`**
  Contains ROS2 packages for simulation control and data publishing within Isaac Sim. 


- **`docs/`**  
  Additional documentation, references, or concept diagrams.

- **`scripts/`**  
  Utility scripts for testing, building, or deployment.

- **`README.md`**  
  The main README file (this file).

---

## Installation & Usage
Each Extension has its own specific installation and usage guidelines. For detailed instructions on:
- How to install Extensions
- Configuration requirements
- Usage examples and best practices
- Troubleshooting common issues

Please refer to our [Wiki Documentation] which is regularly updated with the latest information.

---

## Contribution Guidelines

When contributing to this repository, please follow the guidelines below to keep the workflow efficient and consistent among all team members.

### Git Commit Message Convention
We use **[Bracket Keyword]** at the start of each commit message. Please use one of the following:
- **[Restructure]**: Significant changes to folder structure or naming that might break existing dependencies
- **[Update]**: Update or add functionality to an existing Extension or Docker file
- **[Refactor]**: Code improvements or restructuring without adding new features
- **[Create]**: Creation of a new Extension, Docker, or similar
- **[Remove]**: Deletion of folders/files (though direct file removal is discouraged—use `Deprecated` folder if possible)
- **[Others]**: For changes that don't fit into the above categories

#### Examples:
- `git commit -m "[Update] Improve Dockerfile efficiency for Power Info Extension"`
- `git commit -m "[Refactor] Clean up WebView extension code"`


At **GIST NetAI**, we are continuously developing and adding new extensions as part of setting up the 
