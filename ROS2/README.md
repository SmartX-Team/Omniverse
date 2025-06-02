# Omniverse ROS2 Repository

<div align="center">

![Omniverse](https://img.shields.io/badge/NVIDIA-Omniverse-76B900?style=for-the-badge&logo=nvidia)
![ROS2](https://img.shields.io/badge/ROS2-Humble-22314E?style=for-the-badge&logo=ros)
![Digital Twin](https://img.shields.io/badge/Digital-Twin-0078D4?style=for-the-badge&logo=microsoft)
![Docker](https://img.shields.io/badge/Docker-Container-2496ED?style=for-the-badge&logo=docker)

*Comprehensive repository for Omniverse-based Digital Twin and ROS2 integration*

</div>

## 🚀 Overview

This repository serves as the central hub for **Omniverse-based Digital Twin** development and **ROS2 integration** workflows. Our focus is on creating seamless bridges between virtual simulations and real-world robotics systems.

> **🤖 Looking for Isaac Sim 4.5 Robot Simulation Extension?**  
> Check out the **`Extension/[NetAI]GIST_Husky_IsaacSim_ROS`** folder for complete robot simulation extension code.

## 📂 Current Development Portfolio

| Component | Location | Description | Status | Key Features |
|-----------|----------|-------------|--------|--------------|
| **🤖 Husky Extension** | `Extension/[NetAI]GIST_Husky_IsaacSim_ROS/` | Isaac Sim 4.5 robot simulation extension | ![Active](https://img.shields.io/badge/Status-Active-success) | • Digital twin control<br>• Real-world sync<br>• Advanced sensors |
| **🚀 ROS2 Container** | `ROS2/ros2-container/` | **Universal UGV Control Container** - Single deployment for both Isaac Sim UGV and real ClearPath UGV with one parameter toggle | ![Active](https://img.shields.io/badge/Status-Active-success) | • **One-parameter deployment**<br>• **Auto driver activation**<br>• **Universal compatibility**<br>• Isaac Sim ↔ ClearPath UGV |
| **📊 ROS2 OTF** | `ROS2/ros2-otf/` | On-The-Fly data streaming to enterprise datalake | ![Active](https://img.shields.io/badge/Status-Active-success) | • Real-time data streaming<br>• OTF processing<br>• Datalake integration |

## 🏗️ Repository Structure

```
Omniverse/                                  # 🏠 Main Repository
├── 📁 Extension/                          # Isaac Sim Extensions
│   └── [NetAI]GIST_Husky_IsaacSim_ROS/   # 🤖 Husky Robot Simulation Extension
│       ├── .vscode/                       
│       └── exts/                          # Extension implementation
├── 📁 ROS2/                              # ROS2 Integration Components
│   ├── ros2-container/                    # 🐳 ROS2 Container Infrastructure
│   ├── ros2-lidar-aidetection/           # 🔍 LiDAR AI Detection (Not yet share)
│   ├── ros2-otf/                         # 📊 On-The-Fly Data Pipeline (But For the actual infrastructure deployment code, please refer to my other repository)
├── 📁 Backend/                           # Backend Services (Deprecated)
│   ├── deprecated/                        
│   ├── dt_server/                        
│   └── ext_comms/                        
└── 📋 README.md                          # This file
```

> **📌 Important Navigation Guide:**
> - **For Isaac Sim Robot Extensions**: Check `Extension/` folder
> - **For ROS2 Integration**: Explore `ROS2/` subfolder components
> - **Backend components** are deprecated and kept for reference only

## ✨ Key Capabilities

### 🎯 **Digital Twin Integration**
- **Bidirectional Sync**: Real-world and virtual robot coordination
- **Physics Simulation**: High-fidelity Omniverse Isaac Sim integration
- **Sensor Fusion**: Camera, LiDAR, IMU data processing (I will organize the code and share it with you soon )

### 🔄 **ROS2 Ecosystem**
- **Universal Container**: **Single deployment handles both Isaac Sim UGV and ClearPath UGV**
- **One-Parameter Magic**: Toggle between simulation and real robot with a single configuration change
- **Auto Driver Activation**: Automatically enables all necessary ClearPath drivers when switching to real mode (Ouster Lidar, Intel Realscan Depth Camera)
- **Container Ready**: Dockerized deployment for instant scalability across environments (Alreay push my docker hub)



## 🎯 Use Cases

| Scenario | Components Used | Benefits |
|----------|----------------|----------|
| **Isaac Sim Development** | Husky Extension + **Universal ROS2 Container** | Risk-free testing, **instant deployment** |
| **Real Robot Testing** | **Universal ROS2 Container** (real mode) | **One-parameter switch**, auto driver activation |
| **Simulation-to-Reality** | **Universal Container** + Husky Extension | **Seamless transition**, identical interfaces |
| **Research & Development** | Full stack integration my other Repo | Complete development environment |
| **Production Deployment** | ros2-otf + datalake(S3 compatability + OTF) | Real-time analytics, operational insights |

## 🛠️ Development Roadmap

- [ ] **Enhanced Docker file for Multi-Robot Coordination**
- [ ] **Integrated Advanced Sensor Fusion Algorithms**  
- [ ] **K8S based Cloud-Native Deployment Options**

## 🤝 Contributing

We welcome contributions from the robotics and simulation community!

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'Add amazing feature'`)
4. **Push** to the branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **GIST (Gwangju Institute of Science and Technology)** - Research foundation and institutional support my Master Course
- **NVIDIA Omniverse Team** - For the incredible simulation platform
- **Open Robotics** - For the ROS2 ecosystem
- **Contributors** - Everyone who helps make this project better

## 📞 Contact & Support

- **Maintainer**: Inyong Song   
- **Institution**: Net-AI Lab Team  GIST (Gwangju Institute of Science and Technology)
- **Issues**: Use GitHub Issues for bug reports and feature requests
- **Discussions**: Connect my email, I'll wait your Opinion

---

<div align="center">

**🌟 Star this repository if you find it useful!**

*Building the future of Digital Twin robotics, one commit at a time*

</div>