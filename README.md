# rverflow

🔍 **Smart R Package Dependency Resolver** - A powerful command-line tool that helps you find compatible R package versions across CRAN, Bioconductor, and GitHub before installation.

## 🎯 What does this tool do?

Ever struggled with R package version conflicts? This tool solves that by:

- **🔮 Predicting compatibility**: Finds compatible R versions and package combinations before you install anything
- **🏗️ Building smart environments**: Creates conflict-free package environments across multiple repositories
- **⚡ Saving time**: Prevents the frustration of dependency hell and broken installations

## ✨ Key Features

### 📦 Multi-Repository Support
- **CRAN packages**: Fetches metadata via the crandb API
- **Bioconductor packages**: Caches release manifests with R version requirements
- **GitHub packages**: Resolves packages by parsing DESCRIPTION files

### 🧠 Smart Dependency Resolution
- Traces dependency chains (Depends, Imports, LinkingTo) to find compatible package sets
- Calculates the minimal viable R version needed
- Analyzes downgrade strategies for your current R version
- Uses intelligent backtracking algorithms to resolve conflicts

### 📊 Flexible Output
- Human-readable reports for easy understanding
- Machine-friendly JSON for automation and CI/CD
- Detailed conflict analysis and resolution suggestions

## 🚀 Quick Start

### Prerequisites
- Python 3.9 or higher
- Internet connection for fetching package metadata

### Installation

```bash
# Install in development mode
pip install -e .

# Or install dependencies manually
pip install requests>=2.31 pyyaml>=6.0
```

### Basic Usage

1. **Create a project configuration** (`project.yaml`):
```yaml
project:
  name: my-r-project
options:
  current_r: 4.2.2
  prefer_bioc_release: 3.19
  include_optional: false
targets:
  - package: dplyr
    source: cran
  - package: DESeq2
    source: bioc
    bioc_release: 3.19
  - package: r-lib/pak
    source: github
    ref: main
```

2. **Update the metadata cache**:
```bash
rverflow update-cache --config project.yaml
```

3. **Resolve your environment**:
```bash
# Basic resolution
rverflow solve project.yaml

# With custom options
rverflow solve project.yaml --lock-r 4.2.2 --prefer-bioc 3.18 --format json
```

4. **Get help**:
```bash
rverflow solve --help
```

## 📋 Configuration Reference

### Project Structure
```yaml
project:
  name: your-project-name    # Project identifier

options:
  current_r: 4.2.2          # Your current R version
  prefer_bioc_release: 3.19  # Preferred Bioconductor release
  include_optional: false    # Include optional dependencies

targets:
  - package: package-name    # Package to install
    source: cran|bioc|github # Package source
    constraint: ">=1.0.0"    # Optional version constraint
    bioc_release: 3.19       # Specific Bioconductor release
    ref: main                # GitHub branch/tag/commit
```

### Package Sources
- **`cran`**: Standard CRAN packages
- **`bioc`**: Bioconductor packages (specify `bioc_release` if needed)
- **`github`**: GitHub packages (use `owner/repo` format, specify `ref` for branch/tag/commit)

### Version Constraints
Use standard version operators:
- `>=1.0.0`: Version 1.0.0 or higher
- `==1.2.3`: Exactly version 1.2.3
- `<2.0.0`: Below version 2.0.0
- `>=1.0.0,<2.0.0`: Between 1.0.0 and 2.0.0

## 🏗️ How It Works

1. **Metadata Collection**: Fetches and caches package information from CRAN, Bioconductor, and GitHub
2. **Dependency Analysis**: Builds a complete dependency graph including transitive dependencies
3. **Conflict Detection**: Identifies version conflicts and incompatibilities
4. **Solution Finding**: Uses backtracking algorithms to find compatible package sets
5. **R Version Calculation**: Determines the minimal R version needed for all packages
6. **Report Generation**: Provides clear recommendations and conflict resolutions

## 📁 Project Structure

```
rverflow/
├── src/rverflow/              # Main package
│   ├── cli.py                # Command-line interface
│   ├── solver.py             # Dependency resolution algorithms
│   ├── models.py             # Data models and structures
│   ├── cache.py              # Metadata caching system
│   ├── fetchers.py           # Package metadata fetchers
│   ├── config.py             # Configuration management
│   └── ...
├── cache/                    # Cached package metadata
│   ├── cran/                # CRAN package cache
│   └── bioconductor/        # Bioconductor release cache
└── README.md                # This file
```

## ⚠️ Current Limitations

- **System Dependencies**: SystemRequirements are captured but not validated
- **GitHub Assumptions**: Assumes repositories have standard DESCRIPTION files
- **Algorithm Complexity**: Uses depth-first backtracking; very large dependency sets may need optimization

## 🤝 Contributing

We welcome contributions! Please feel free to:
- Report bugs or request features via GitHub issues
- Submit pull requests with improvements
- Share feedback and suggestions

## 📄 License

This project is open source. See the license file for details.

---

# rverflow (中文说明)

🔍 **智能R包依赖解析器** - 一个强大的命令行工具，帮助您在安装前找到跨CRAN、Bioconductor和GitHub的兼容R包版本。

## 🎯 这个工具的作用

是否曾经为R包版本冲突而苦恼？这个工具通过以下方式解决这个问题：

- **🔮 预测兼容性**: 在安装任何包之前找到兼容的R版本和包组合
- **🏗️ 构建智能环境**: 跨多个仓库创建无冲突的包环境
- **⚡ 节省时间**: 防止依赖地狱和安装失败的挫折

## ✨ 主要特性

### 📦 多仓库支持
- **CRAN包**: 通过crandb API获取元数据
- **Bioconductor包**: 缓存发布清单及R版本要求
- **GitHub包**: 通过解析DESCRIPTION文件解析包

### 🧠 智能依赖解析
- 追踪依赖链（Depends、Imports、LinkingTo）找到兼容的包集合
- 计算所需的最小可行R版本
- 分析当前R版本的降级策略
- 使用智能回溯算法解决冲突

### 📊 灵活输出
- 易于理解的人类可读报告
- 用于自动化和CI/CD的机器友好JSON
- 详细的冲突分析和解决建议

## 🚀 快速开始

### 前提条件
- Python 3.9或更高版本
- 互联网连接用于获取包元数据

### 安装

```bash
# 开发模式安装
pip install -e .

# 或手动安装依赖
pip install requests>=2.31 pyyaml>=6.0
```

### 基本使用

1. **创建项目配置** (`project.yaml`):
```yaml
project:
  name: my-r-project
options:
  current_r: 4.2.2
  prefer_bioc_release: 3.19
  include_optional: false
targets:
  - package: dplyr
    source: cran
  - package: DESeq2
    source: bioc
    bioc_release: 3.19
  - package: r-lib/pak
    source: github
    ref: main
```

2. **更新元数据缓存**:
```bash
rverflow update-cache --config project.yaml
```

3. **解析您的环境**:
```bash
# 基本解析
rverflow solve project.yaml

# 使用自定义选项
rverflow solve project.yaml --lock-r 4.2.2 --prefer-bioc 3.18 --format json
```

## 📋 配置参考

### 项目结构
```yaml
project:
  name: your-project-name    # 项目标识符

options:
  current_r: 4.2.2          # 您当前的R版本
  prefer_bioc_release: 3.19  # 首选的Bioconductor发布版本
  include_optional: false    # 包含可选依赖

targets:
  - package: package-name    # 要安装的包
    source: cran|bioc|github # 包来源
    constraint: ">=1.0.0"    # 可选版本约束
    bioc_release: 3.19       # 特定Bioconductor发布版本
    ref: main                # GitHub分支/标签/提交
```

### 包来源
- **`cran`**: 标准CRAN包
- **`bioc`**: Bioconductor包（如需要请指定`bioc_release`）
- **`github`**: GitHub包（使用`owner/repo`格式，为分支/标签/提交指定`ref`）

### 版本约束
使用标准版本操作符：
- `>=1.0.0`: 1.0.0版本或更高
- `==1.2.3`: 确切的1.2.3版本
- `<2.0.0`: 低于2.0.0版本
- `>=1.0.0,<2.0.0`: 1.0.0到2.0.0之间

## 🏗️ 工作原理

1. **元数据收集**: 从CRAN、Bioconductor和GitHub获取并缓存包信息
2. **依赖分析**: 构建包括传递依赖的完整依赖图
3. **冲突检测**: 识别版本冲突和不兼容性
4. **解决方案查找**: 使用回溯算法找到兼容的包集合
5. **R版本计算**: 确定所有包所需的最小R版本
6. **报告生成**: 提供清晰的建议和冲突解决方案

## 📁 项目结构

```
rverflow/
├── src/rverflow/              # 主包
│   ├── cli.py                # 命令行界面
│   ├── solver.py             # 依赖解析算法
│   ├── models.py             # 数据模型和结构
│   ├── cache.py              # 元数据缓存系统
│   ├── fetchers.py           # 包元数据获取器
│   ├── config.py             # 配置管理
│   └── ...
├── cache/                    # 缓存的包元数据
│   ├── cran/                # CRAN包缓存
│   └── bioconductor/        # Bioconductor发布缓存
└── README.md                # 本文件
```

## 💡 使用场景

- **🔬 科研项目**: 确保可重现的R分析环境
- **🏭 生产环境**: 在部署前验证包兼容性
- **🚀 CI/CD流水线**: 自动化R环境配置和验证
- **📦 包开发**: 测试包的依赖兼容性
- **👥 团队协作**: 统一团队的R环境配置

## ⚠️ 当前限制

- **系统依赖**: 捕获SystemRequirements但不验证
- **GitHub假设**: 假设仓库具有标准DESCRIPTION文件
- **算法复杂性**: 使用深度优先回溯；非常大的依赖集可能需要优化

## 🤝 贡献

欢迎贡献！请随时：
- 通过GitHub issues报告错误或请求功能
- 提交改进的pull request
- 分享反馈和建议

## 📄 许可证

本项目是开源的。详情请参阅许可证文件。
