# Omniverse Extensions Repository

As of **25/01/20**, the repository structure has undergone a **major restructuring**.  
It now consists of two main folders at the root level:  
- **`extensions/`**: Contains Omniverse Extensions  
- **`backend/`**: Contains backend-related code or Docker configurations  

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

This repository serves as the centralized hub for storing and developing various Omniverse Extensions. Originally built to embrace Omniverse’s microservice philosophy, it now supports multiple teams collaborating on Extensions that enhance Digital Twin Visualization at GIST NetAI.

The Omniverse Extension embodies the philosophy of Omniverse, aiming for microservices. With the Extension Template, users can easily add the functionalities they desire to the Omniverse App. 

At **GIST NetAI**, we are continuously developing and adding new extensions as part of setting up the **Cloud-native Digital Twin Service**.

---

## Project Structure

Below is an overview of the main folders in this repository:

- **`extensions/`**  
  Contains various Omniverse Extensions (e.g., UWB Tracking, Stations Align, etc.).  
  - **`deprecated/`**: Houses older or no longer actively maintained extensions.

- **`backend/`**  
  Contains backend-related code and Docker configurations.  
  - **`deprecated/`**: Houses older or no longer actively maintained backend resources.

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
